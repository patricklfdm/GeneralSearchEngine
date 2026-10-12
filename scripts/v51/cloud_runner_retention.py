"""Pack native v4 metadata without dropping paths, hashes or read-back checks."""
from pathlib import Path
from . import remote_collection as parts, remote_command as c, performance_model as m


def pack(root, rows, binding):
    root=Path(root).absolute();root.mkdir(mode=0o700)
    source=root/'files';source.mkdir(mode=0o700)
    members={};total=0
    for name,data in rows:
        parts.safe_name(name)
        m.need(name!=parts.INDEX and name not in members and type(data) is bytes,'metadata duplicate/type')
        total+=len(data)
        m.need(len(members)<parts.LIMITS['files']-1 and len(data)<=parts.LIMITS['memberBytes'] and
               total<=parts.LIMITS['expandedBytes'],'metadata file/byte bound')
        members[name]=dict(bytes=len(data),sha256=m.sha(data))
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    m.need(members,'metadata empty inventory')
    manifest=parts.pack(source,root/'parts',binding)
    # Replay exactly what will be uploaded, including every original path/hash.
    verified=parts.unpack(root/'parts',root/'verified',binding,expected_members=members)
    c.write_once(root/'receipt.json',dict(status='PASS',bindingSha256=binding,**{
        key:verified[key] for key in ('files','expandedBytes','compressedBytes')}))
    for part in manifest['parts']:
        yield 'metadata/'+part['name'],(root/'parts'/part['name']).read_bytes()
    yield 'metadata/parts.json',(root/'parts/parts.json').read_bytes()
