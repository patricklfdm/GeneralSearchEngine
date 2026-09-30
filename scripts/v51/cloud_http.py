"""Bounded provider HTTP with renewable credentials. Live mutations remain disabled."""
from dataclasses import dataclass, field
import math
import subprocess
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
    def send(self, method, url, headers, body, timeout, maximum):
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

    def call(self, method, url, body=None, *, deadline, raw=False, maximum=16 << 20):
        parsed = urllib.parse.urlsplit(url)
        m.need(parsed.scheme == 'https' and parsed.netloc in ('compute.googleapis.com', 'storage.googleapis.com') and
               not parsed.fragment and not parsed.username, 'provider endpoint')
        m.need(method in ('GET', 'POST', 'DELETE'), 'provider method')
        m.need(method == 'GET' or self.offline, 'live provider mutation disabled pending paid admission')
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
