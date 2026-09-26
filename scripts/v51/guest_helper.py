"""Delivered volume helper startup check. Native privileged writes remain closed."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.v51 import guest_volume

if __name__ == '__main__':
    # The trusted receiver authenticates every file before reaching this import.
    # No caller-supplied command or backend is accepted by the executable helper.
    if len(sys.argv) != 1: raise ValueError('helper takes no write commands')
    if guest_volume.Linux.offline is not False: raise ValueError('native volume backend scope')
    print('{"status":"PASS","nativeWritesEnabled":false}')
