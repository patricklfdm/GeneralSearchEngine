"""Reviewed current regression builds, separate from published evidence allowlists."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ('5.1.0-SNAPSHOT', '5.1.0', '5.2.0-SNAPSHOT', '5.3.0-SNAPSHOT')
MODULES = ('general-search-engine', 'general-search-engine-replication')


def current(root=ROOT):
    value = ET.parse(root / 'pom.xml').getroot().findtext('{*}version')
    if value not in VERSIONS:
        raise ValueError('unreviewed current build coordinate')
    return value


def regression_pair(names, source_inventory, root=ROOT):
    """New-coordinate regression only when bound to this checkout's exact POM bytes."""
    expected = {f'{module}-{current(root)}.jar' for module in MODULES}
    if len(names) != 2 or set(names) != expected or source_inventory.get('pom.xml') != hashlib.sha256((root/'pom.xml').read_bytes()).hexdigest():
        raise ValueError('wrong candidate version or source-bound regression pair')
