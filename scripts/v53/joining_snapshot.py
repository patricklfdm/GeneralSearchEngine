"""Read actual joining custody snapshots without opening recorded original paths.

This inventory layer is a prerequisite to history replay, never proof of native
initialization, a forced majority, publication, or a successful process recovery.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from . import learner_slot_snapshot as s

need, f, MIB = s.need, s.f, s.e.MIB
ROOTS = frozenset(('custody', 'initialTyped', 'intent', 'materialization', 'nativeOwner',
                  'operation', 'pendingIntent', 'placement', 'replica', 'retirement',
                  'slotTyped', 'slots', 'successor', 'successorTyped', 'voterStage'))
REQUIRED = frozenset(('custody', 'nativeOwner', 'operation', 'placement', 'replica', 'retirement'))
PLACED = REQUIRED - {'nativeOwner', 'retirement'}


def path_binding(row):
    need(type(row) is dict and set(row) == {'path','parentRealPath','parentFileKey','fileStoreName','fileStoreType'},
         'joining snapshot path binding')
    path, parent = s.original_path(row['path']), s.original_path(row['parentRealPath'])
    need(path.parent == parent and all(type(row[k]) is str and row[k].strip() and len(row[k].encode()) <= 4096
         for k in ('parentFileKey','fileStoreName','fileStoreType')), 'joining snapshot path binding')
    return path


def relative(value):
    # Custody walks at most eight levels, unlike the earlier slot inventory.
    from pathlib import PurePosixPath
    need(type(value) is str and value and '\0' not in value and len(value.encode()) <= 4096,
         'joining snapshot member path')
    p = PurePosixPath(value)
    need(not p.is_absolute() and str(p) == value and '..' not in p.parts and len(p.parts) <= 8,
         'joining snapshot member path')
    return p


def checked_file(path, identity):
    data = s.regular(path, 64 * MIB)
    need(len(data) == identity['size'] and s.digest(data) == identity['sha256'], 'joining snapshot original bytes')
    return data


@dataclass(frozen=True)
class Snapshot:
    root: Path
    identities: dict
    total_bytes: int

    def member(self, family, name):
        need(family in self.identities and self.identities[family]['present'], 'joining snapshot absent family')
        rows = {v['name']:v['identity'] for v in self.identities[family]['files']}
        need(name in rows and 'directory' not in rows[name], 'joining snapshot missing file')
        path = self.root / family
        for part in relative(name).parts:
            need(path.is_dir() and not path.is_symlink(), 'joining snapshot copied parent')
            path = path / part
        return checked_file(path, rows[name])


def read(root, *, stage='native'):
    need(stage in ('placed', 'native'), 'joining snapshot declared stage')
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'joining snapshot directory')
    raw = s.regular(root/'inventory.json', MIB); rows = s.e.parse(raw)
    need(type(rows) is list and len(rows) == len(ROOTS) and all(type(v) is dict for v in rows),
         'joining snapshot roots')
    need([v.get('name') for v in rows] == sorted(ROOTS), 'joining snapshot roots')
    need(raw == f.canonical(rows), 'joining snapshot canonical inventory')
    present=set(); paths=[]; keys=set(); count=total=0
    for row in rows:
        name=row['name']
        need(type(row.get('present')) is bool and set(row) == {'name','path','present'} | ({'files'} if row.get('present') else set()),
             'joining snapshot root shape')
        path=path_binding(row['path'])
        need(all(path != p and path not in p.parents and p not in path.parents for p in paths), 'joining snapshot overlapping roots')
        paths.append(path)
        if not row['present']:continue
        present.add(name); entries=row['files']
        need(type(entries) is list and entries and all(type(v) is dict and set(v)=={'name','identity'} for v in entries),
             'joining snapshot member rows')
        count+=len(entries);need(count<=512, 'joining snapshot inventory capacity')
        names=[v['name'] for v in entries]
        need(all(type(v) is str for v in names) and names==sorted(set(names)) and names[0]=='.', 'joining snapshot ordered members')
        copied=root/name;need(copied.is_dir() and not copied.is_symlink(), 'joining snapshot copied root')
        observed={'.'};pending=[copied]
        while pending:
            for child in pending.pop().iterdir():
                need(not child.is_symlink() and (child.is_file() or child.is_dir()), 'joining snapshot copied member')
                observed.add(child.relative_to(copied).as_posix())
                need(len(observed)<=len(entries), 'joining snapshot copied inventory')
                if child.is_dir():pending.append(child)
        need(observed==set(names), 'joining snapshot copied inventory')
        for entry in entries:
            name=entry['name'];relative(name);identity=entry['identity']
            need(type(identity) is dict and type(identity.get('key')) is str and identity['key'].strip()
                 and len(identity['key'].encode())<=4096, 'joining snapshot original key')
            need(identity['key'] not in keys, 'joining snapshot original inode alias');keys.add(identity['key'])
            file=copied if name=='.' else copied/name
            if 'directory' in identity:
                need(identity=={'key':identity['key'],'directory':True} and file.is_dir(), 'joining snapshot directory identity')
            else:
                need(name!='.' and set(identity)=={'key','size','sha256'} and type(identity['size']) is int and 0<=identity['size']<=64*MIB
                     and type(identity['sha256']) is str and re.fullmatch('[0-9a-f]{64}',identity['sha256']), 'joining snapshot file identity')
                total+=identity['size'];need(total<=384*MIB+7*64*MIB, 'joining snapshot extent')
                checked_file(file,identity)
    need((PLACED if stage=='placed' else REQUIRED)<=present, 'joining snapshot required roots')
    if stage=='placed':need(not present & {'nativeOwner','retirement'}, 'joining snapshot premature native roots')
    need({p.name for p in root.iterdir()}==present|{'inventory.json'}, 'joining snapshot layout')
    return Snapshot(root,{v['name']:v for v in rows},total)


def validate(root, *, stage='native'):
    snapshot=read(root,stage=stage)
    return dict(status='PARTIAL',scope='joining-original-inventory',stage=stage,roots=len(snapshot.identities),
                members=sum(len(v.get('files',[])) for v in snapshot.identities.values()),bytes=snapshot.total_bytes,
                nativeHistoryQualified=False,initializationQualified=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--stage',choices=('placed','native'),default='native');args=parser.parse_args()
    print(json.dumps(validate(args.root,stage=args.stage),sort_keys=True))
