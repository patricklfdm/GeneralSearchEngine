"""Current build coordinates and the closed historical V5.1 evidence versions."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ('5.1.0-SNAPSHOT', '5.1.0')
MODULES = ('general-search-engine', 'general-search-engine-replication')


def current(root=ROOT):
    version = ET.parse(root/'pom.xml').getroot().findtext('{http://maven.apache.org/POM/4.0.0}version')
    if version not in VERSIONS:
        raise ValueError('V5.1 preparation version')
    return version


def check_manifest(raw, version):
    lines = raw.decode('utf-8').replace('\r', '').splitlines()
    if [line for line in lines if line.startswith('Implementation-Version: ')] != ['Implementation-Version: '+version]:
        raise ValueError('stale artifact version')


def candidate_pair(names):
    """Replay historical bytes, but never mix release/snapshot or artifact roles."""
    if len(names) != 2 or not any(set(names) == {f'{module}-{version}.jar' for module in MODULES}
                                 for version in VERSIONS):
        raise ValueError('wrong candidate version or artifact pair')
