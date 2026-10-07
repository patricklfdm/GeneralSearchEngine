"""Bounded provider HTTP with renewable credentials; generic live API is read-only."""
from dataclasses import dataclass, field
import http.client
from http.client import HTTPSConnection
import math
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from . import performance_model as m


@dataclass(frozen=True)
class AccessToken:
    value: str = field(repr=False)
    usable_until: float


class ApiError(RuntimeError):
    def __init__(self, status, method):
        self.status, self.method = status, method
        # No response, headers, URL query or credential appears in retained errors.
        super().__init__(f'provider {method} returned HTTP {status}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('provider redirect forbidden')


class Network:
    offline = False
    def __init__(self):
        self.connections = {}; self.lock = threading.Lock()
        self.opened = 0; self.reused = 0

    def close(self):
        with self.lock:
            for connection, _ in self.connections.values(): connection.close()
            self.connections.clear()

    def __del__(self):
        # Short-lived read/cleanup APIs also own this transport. Native Runner
        # scopes close explicitly; release remaining sockets on other API exit.
        try: self.close()
        except Exception: pass

    def send(self, method, url, headers, body, timeout, maximum):
        parsed = urllib.parse.urlsplit(url)
        # Preserve the existing proxy behavior. Direct GCP traffic reuses one
        # verified TLS connection per origin; no response/authority is cached.
        # OIDC/STS/impersonation also use Network, with their own exact endpoint
        # admission. Keep those exchanges on the existing unpooled transport.
        if (parsed.scheme != 'https' or parsed.netloc not in ('compute.googleapis.com', 'storage.googleapis.com') or
                parsed.fragment or urllib.request.getproxies().get('https') and not urllib.request.proxy_bypass(parsed.hostname)):
            return self._unpooled(method, url, headers, body, timeout, maximum)
        end = time.monotonic()+timeout
        with self.lock:
            host = parsed.netloc; now = time.monotonic()
            previous = self.connections.pop(host, None)
            # Mutations always start with a fresh connection. A failed exchange
            # is never automatically replayed, including on a reused GET socket.
            if previous is not None and (method != 'GET' or now-previous[1] >= 10):
                previous[0].close(); previous = None
            connection = previous[0] if previous else None
            try:
                left = end-time.monotonic()
                m.need(left > 0, 'provider transport deadline')
                if connection is None:
                    connection = HTTPSConnection(host, timeout=left); self.opened += 1
                else:
                    self.reused += 1; connection.timeout = left
                    if connection.sock is not None: connection.sock.settimeout(left)
                connection.request(method, urllib.parse.urlunsplit(('', '', parsed.path or '/', parsed.query, '')),
                                   body=body, headers=headers)
                with connection.getresponse() as response:
                    status = response.status
                    data = response.read(maximum+1)
                    m.need(time.monotonic() <= end, 'provider transport late response')
                    if 300 <= status < 400: raise ValueError('provider redirect forbidden')
                    if len(data) <= maximum and response.length not in (None,0):
                        raise http.client.IncompleteRead(b'')
                    if len(data) <= maximum and not response.will_close and connection.sock is not None:
                        self.connections[host] = (connection, time.monotonic()); connection = None
                    return status, data if 200 <= status < 300 else b''
            except (http.client.HTTPException, OSError):
                raise ConnectionError('provider transport interrupted; original operation remains unresolved') from None
            finally:
                if connection is not None: connection.close()

    @staticmethod
    def _unpooled(method, url, headers, body, timeout, maximum):
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                return response.status, response.read(maximum+1)
        except urllib.error.HTTPError as error:
            try: return error.code, b''
            finally: error.close()
        except (urllib.error.URLError, OSError):
            raise ConnectionError('provider transport interrupted; original operation remains unresolved') from None


def credential(timeout):
    result = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, timeout=timeout)
    m.need(result.returncode == 0 and result.stdout.strip(), 'provider credential unavailable')
    return result.stdout.decode().strip()


class Api:
    def __init__(self, *, transport=None, tokens=credential, clock=time.monotonic):
        self.transport = transport if transport is not None else Network()
        self.tokens, self.clock = tokens, clock
        self.token, self.expires = None, 0

    @property
    def offline(self): return self.transport.offline is True

    def authorize(self, method, url, body):
        m.need(method == 'GET' or self.offline, 'live provider mutation disabled pending paid admission')

    def call(self, method, url, body=None, *, deadline, raw=False, maximum=16 << 20):
        parsed = urllib.parse.urlsplit(url)
        m.need(parsed.scheme == 'https' and parsed.netloc in ('compute.googleapis.com', 'storage.googleapis.com') and
               not parsed.fragment and not parsed.username, 'provider endpoint')
        m.need(method in ('GET', 'POST', 'DELETE'), 'provider method')
        self.authorize(method, url, body)
        m.need(type(maximum) is int and 0 < maximum <= 16 << 20, 'provider response bound')
        payload = body if isinstance(body, bytes) else m.canonical(body) if body is not None else None
        for attempt in range(2):
            remaining = deadline-self.clock()
            m.need(remaining > 0, 'provider original deadline')
            if self.token is None or self.clock() >= self.expires:
                credential_value = self.tokens(min(30, remaining))
                if isinstance(credential_value, AccessToken):
                    usable = credential_value.usable_until
                    m.need(type(usable) in (int,float) and math.isfinite(usable) and usable > self.clock(), 'provider credential expired')
                    token, expires = credential_value.value, min(usable, self.clock()+2400)
                else:
                    token, expires = credential_value, self.clock()+2400
                m.need(isinstance(token, str) and token and all(33 <= ord(c) <= 126 for c in token), 'provider credential shape')
                self.token, self.expires = token, expires
            remaining = deadline-self.clock()
            m.need(remaining > 0, 'provider original deadline')
            headers = {'Authorization': 'Bearer '+self.token,
                       'Content-Type': 'application/octet-stream' if isinstance(body, bytes) else 'application/json'}
            status, data = self.transport.send(method, url, headers, payload, min(30, remaining), maximum)
            m.need(self.clock() <= deadline, 'provider late response')
            if status == 401:
                self.token, self.expires = None, 0
                # A mutation is submitted once. Even an explicit authentication
                # response is retained for operation reconciliation, never replayed.
                if method == 'GET' and attempt == 0: continue
            if not 200 <= status < 300: raise ApiError(status, method)
            m.need(isinstance(data, bytes) and len(data) <= maximum, 'provider response size/type')
            return data if raw else m.strict_json(data) if data else {}
