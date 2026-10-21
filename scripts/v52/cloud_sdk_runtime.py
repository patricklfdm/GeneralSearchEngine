"""Local SDK startup check and the minimal environment shared by IAP channels.

No credential lookup, network command, resource or ledger operation. Derive the
library directory from the running Python's relocated prefix, never ambient
LD_LIBRARY_PATH or sysconfig's potentially stale compile-time LIBDIR.
"""
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from scripts.v51 import guest_transport as transport
from .evidence import strict

CHECK_SECONDS = 30
CODES = frozenset('EXECUTABLE_UNAVAILABLE PYTHON_ENVIRONMENT PYTHON_START_FAILED SDK_START_FAILED '
                  'PYTHON_TIMEOUT SDK_TIMEOUT PYTHON_RESPONSE SDK_RESPONSE'.split())


class SdkError(ValueError):
    def __init__(self, reason):
        if reason not in CODES: raise ValueError('unknown SDK diagnostic')
        self.code = 'V52_SDK_'+reason
        super().__init__(self.code)


def public_failure(value):
    code = value.get('sdkCode') if type(value) is dict else None
    return dict(sdkCode=code) if type(code) is str and code in {'V52_SDK_'+v for v in CODES} else {}


def failure(error):
    return dict(sdkCode=error.code) if type(error) is SdkError else {}


def executable():
    value = shutil.which('gcloud')
    if value is None: raise SdkError('EXECUTABLE_UNAVAILABLE')
    path = Path(value).resolve()
    if not path.is_file() or not os.access(path, os.X_OK): raise SdkError('EXECUTABLE_UNAVAILABLE')
    return str(path)


def environment(config):
    python = Path(sys.executable); prefix = Path(sys.base_prefix)
    if not python.is_absolute() or not python.is_file() or not prefix.is_absolute():
        raise SdkError('PYTHON_ENVIRONMENT')
    library = prefix.resolve()/'lib'
    if not library.is_dir() or any(c in str(library) for c in ':\n\r\0'):
        raise SdkError('PYTHON_ENVIRONMENT')
    return dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', CLOUDSDK_CONFIG=str(config),
        CLOUDSDK_CORE_DISABLE_PROMPTS='1', CLOUDSDK_CORE_DISABLE_USAGE_REPORTING='true',
        CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK='true', CLOUDSDK_CORE_DISABLE_FILE_LOGGING='true',
        CLOUDSDK_PYTHON=sys.executable, CLOUDSDK_PYTHON_SITEPACKAGES='0', LD_LIBRARY_PATH=str(library))


def _run(args, env, deadline, phase):
    try: return transport.process(args, b'', deadline, maximum=65536, env=env)
    except TimeoutError: raise SdkError(phase+'_TIMEOUT') from None
    except (OSError, transport.ProcessError): raise SdkError(phase+'_START_FAILED') from None
    except ValueError: raise SdkError(phase+'_RESPONSE') from None


def check():
    """Check one SDK under its actual isolated environment before acquisition."""
    sdk = executable(); deadline = time.monotonic()+CHECK_SECONDS
    with tempfile.TemporaryDirectory(prefix='gse-v52-sdk-check-') as directory:
        env = environment(directory)
        marker = b'V52_SDK_PYTHON_OK\n'
        raw = _run([sys.executable, '-I', '-S', '-c', 'print("V52_SDK_PYTHON_OK")'], env, deadline, 'PYTHON')
        if raw != marker: raise SdkError('PYTHON_RESPONSE')
        raw = _run([sdk, 'version', '--format=json', '--quiet'], env, deadline, 'SDK')
        try:
            value = strict(raw); version = value['Google Cloud SDK']
            if type(version) is not str or re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', version) is None:
                raise ValueError('version')
        except (ValueError, TypeError, KeyError): raise SdkError('SDK_RESPONSE') from None
    return dict(schema='gse-v52-sdk-runtime-v1', status='PASS', pythonVersion=sys.version.split()[0],
        sdkVersion=version, credentialEnvironmentInherited=False, cloudOperationExecuted=False)
