"""Loopback TLS fixture for cleanup qualification, never a production transport.

The real urllib Network, certificate checks, HTTP framing and redirect handler
run unchanged. Only connection routing/trust is replaced, inside this fixture.
There is no environment/CLI route from production to this socket substitution.
"""
from contextlib import ExitStack, redirect_stdout
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import io
import os
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit
import urllib.request
from . import cloud_cleanup_auth_fake as auth, cloud_cleanup_entry as entry
from . import cloud_cleanup_entry_qualification as entries, cloud_cleanup_qualification as retained
from . import cloud_native_authority as n, performance_model as m

HOSTS = ('pipelines.actions.githubusercontent.com', 'sts.googleapis.com', 'iamcredentials.googleapis.com',
         'compute.googleapis.com', 'storage.googleapis.com')


class Clock:
    def wall(self): return int(time.time())
    def sleep(self, seconds):
        if seconds: time.sleep(seconds)


class Fixture:
    def __init__(self, state, trigger='manual', fault=None):
        self.state, self.fault = state, fault
        self.invocation = entries.fixture(state['configuration'], trigger)
        v = self.invocation
        self.binding = entry.identity(v['configuration'], v['env'], trigger=trigger, source=v['source'], checkout=v['checkout'])
        self.env, self.descriptor = auth.inputs(self.binding, v['env'])
        _, self.http, _, _ = retained.restore(state)
        self.issuer = auth.Issuer(self.binding, Clock())
        self.provider = auth.Provider(self.http)
        self.requests, self.errors, self.used_faults = [], [], set()
        self.forbidden_routes = []

    def reply(self, method, host, path, headers, body):
        stage = 'sts' if host == HOSTS[1] else 'impersonation' if host == HOSTS[2] else 'oidc' if host == HOSTS[0] else 'provider'
        self.requests.append(dict(stage=stage, host=host, method=method))
        fault = self.fault
        if fault == 'redirect-'+stage:
            return 307, b'', {'Location':'https://untrusted.invalid/steal'}, False
        if fault == 'deny-'+stage: return 403, b'private issuer/provider error', {}, False
        if fault == 'oversized-'+stage: return 200, b'x'*((129 << 10) if stage != 'provider' else (17 << 20)), {}, False
        if fault == 'invalid-json-'+stage: return 200, b'{private-invalid', {}, False
        url = 'https://'+host+path
        if stage != 'provider':
            keep = {k:headers[k] for k in ('Authorization','Content-Type') if k in headers}
            # urllib adds a default form content type only when there is a body.
            status, raw = self.issuer.send(method, url, keep, body, 30, 128 << 10)
        else:
            if fault == 'get-401' and method == 'GET' and fault not in self.used_faults:
                self.used_faults.add(fault); return 401, b'private-401', {}, False
            if fault == 'mutation-401' and method == 'DELETE' and host == 'compute.googleapis.com':
                return 401, b'private-401', {}, False
            if fault == 'lease-cas' and method == 'POST' and fault not in self.used_faults:
                self.used_faults.add(fault); retained.rewrite(self.http, n.LEASE, lambda value:None)
            status, raw = self.provider.send(method, url, dict(headers), body, 30, 16 << 20)
            if fault == 'malformed-resource' and method == 'GET' and status == 200 and raw and host == 'compute.googleapis.com':
                value = m.strict_json(raw)
                if 'sizeGb' in value:
                    value['sizeGb'] = auth.ACCOUNT_SECRET
                    raw = m.canonical(value)
            if fault == 'lost-delete' and method == 'DELETE' and host == 'compute.googleapis.com' and fault not in self.used_faults:
                self.used_faults.add(fault); return status, raw, {}, True
        return status, raw, {}, False

    def __enter__(self):
        self.stack = ExitStack()
        try:
            tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='v51-cleanup-tls-')))
            cert, key = tmp/'cert.pem', tmp/'key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                '-subj','/CN=v51-cleanup-loopback','-addext','subjectAltName='+','.join('DNS:'+host for host in (('localhost',) if self.fault == 'tls-hostname' else HOSTS)),
                '-keyout',str(key),'-out',str(cert)], check=True, capture_output=True, timeout=15)
            fixture = self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def request(self):
                    try:
                        size = int(self.headers.get('Content-Length','0'))
                        m.need(0 <= size <= 8 << 20, 'fixture request bound')
                        body = self.rfile.read(size) if size else None
                        status, raw, headers, drop = fixture.reply(self.command,self.headers['Host'],self.path,self.headers,body)
                        if drop:
                            self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                        self.send_response(status)
                        self.send_header('Content-Length',str(len(raw)))
                        for k,v in headers.items(): self.send_header(k,v)
                        self.end_headers(); self.wfile.write(raw)
                    except (BrokenPipeError, ConnectionResetError, ssl.SSLError): pass
                    except Exception as error:
                        fixture.errors.append(type(error).__name__)
                        self.send_error(500)
                do_GET = do_POST = do_DELETE = request
            server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
            server.daemon_threads = True
            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); server_context.load_cert_chain(cert,key)
            server.socket = server_context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            def stop(): server.shutdown(); server.server_close(); thread.join(timeout=3)
            self.stack.callback(stop)
            trust = ssl.create_default_context(cafile=None if self.fault == 'tls-untrusted' else str(cert))
            class Connection(HTTPSConnection):
                def connect(self):
                    allowed = self.host in HOSTS and self.port == 443 and not self._tunnel_host
                    if not allowed: fixture.forbidden_routes.append(self.host)
                    m.need(allowed, 'non-loopback fixture route')
                    sock = socket.create_connection(server.server_address, timeout=self.timeout)
                    self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
            class HandlerTLS(urllib.request.HTTPSHandler):
                def https_open(self, request):
                    return self.do_open(Connection, request, context=trust)
            build = urllib.request.build_opener
            def opener(*handlers): return build(urllib.request.ProxyHandler({}), HandlerTLS(), *handlers)
            self.stack.enter_context(patch.object(urllib.request,'build_opener',side_effect=opener))
            descriptor = tmp/'descriptor.json'; descriptor.write_bytes(m.canonical(self.descriptor)); descriptor.chmod(0o600)
            self.env['GOOGLE_GHA_CREDS_PATH'] = str(descriptor)
            self.config_path = tmp/'config.json'; self.config_path.write_bytes(m.canonical(self.invocation['configuration']))
            collect = entry.collect_run
            def observe(binding):
                return collect(binding, get=lambda path:self.invocation['observation'])
            self.stack.enter_context(patch.object(entry,'collect_run',side_effect=observe))
            return self
        except BaseException:
            self.stack.close(); raise

    def __exit__(self, *args): return self.stack.__exit__(*args)

    def run(self, output):
        v = self.invocation
        return entry.execute_network(v['configuration'], self.env, output, trigger=v['trigger'],source=v['source'],checkout=v['checkout'])


    def run_cli(self, output):
        v = self.invocation; stdout = io.StringIO()
        with patch.object(entry.preflight, 'CONFIG', self.config_path), patch.dict(os.environ, self.env, clear=True), \
             patch.object(entry.subprocess, 'check_output', return_value=v['source']+'\n'), redirect_stdout(stdout):
            code = entry.main(['reconcile', '--trigger', v['trigger'], '--source', v['source'], '--output', str(output)])
        (Path(output)/'entry.stdout').write_text(stdout.getvalue())
        return code
