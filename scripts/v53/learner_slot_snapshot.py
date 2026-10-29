"""Portable learner snapshot bytes and recorded original identity observations.

This layer deliberately reports PARTIAL. It does not establish native consensus,
select a current head, authorize deletion, or qualify force/process-death traces.
Original paths are data and are never opened. A full history reader must bind
these observations to its original plans, selectors and independently replayed
source histories before making any qualification claim.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from . import context_evidence as e

f, need = e.f, e.need
ROOTS = {'operation', 'replica', 'initial-typed', 'seed', 'seed-typed', 'slots', 'slot-typed'}
COUNTS = dict(GENERATION=2, SOURCE=6, LEARNER=1, JOURNAL=1, CATALOG=1,
              MISC=1, APPLICATION=7, CONTROL=256, WAITER=64)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, maximum):
    need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1,
         'learner snapshot regular member')
    need(path.stat().st_size <= maximum, 'learner snapshot member capacity')
    with path.open('rb') as stream:
        value = stream.read(maximum + 1)
    need(len(value) <= maximum, 'learner snapshot member capacity')
    return value


def original_path(value):
    need(type(value) is str and '\0' not in value and len(value.encode()) <= 4096,
         'learner snapshot original path')
    path = PurePosixPath(value)
    need(path.is_absolute() and value != '/' and str(path) == value
         and '..' not in path.parts, 'learner snapshot original path')
    return path


def member_path(value):
    need(type(value) is str and value and '\0' not in value and len(value.encode()) <= 4096,
         'learner snapshot relative member')
    path = PurePosixPath(value)
    need(not path.is_absolute() and str(path) == value and '..' not in path.parts
         and len(path.parts) <= 4, 'learner snapshot relative member')
    return path


def resource_usage(value):
    need(type(value) is dict and set(value) == {'counts', 'leases', 'metadata', 'staging', 'queued'},
         'learner snapshot resource shape')
    counts = value['counts']
    need(type(counts) is dict and set(counts) <= set(COUNTS)
         and all(type(v) is int and 0 < v <= COUNTS[k] for k, v in counts.items()),
         'learner snapshot resource counts')
    need(type(value['leases']) is int and value['leases'] == sum(counts.values()),
         'learner snapshot resource leases')
    for name, maximum in [('metadata', 384 * e.MIB), ('staging', 512 * e.MIB), ('queued', 64 * e.MIB)]:
        need(type(value[name]) is int and 0 <= value[name] <= maximum,
             'learner snapshot resource bytes')
    return value


@dataclass(frozen=True)
class Snapshot:
    identities: dict
    files: dict
    resources: dict

    def fingerprints(self, root, names):
        """Rebuild the decision fingerprint from verified copied bytes and the
        recorded original identity, not this archive copy's new inode."""
        need(root in self.identities and len(names) == len(set(names)), 'learner snapshot fingerprint roots/paths')
        members = self.identities[root]['members']
        need(set(names) <= set(members), 'learner snapshot fingerprint roots/paths')
        return [dict(path=name, sha256=digest(f.canonical(members[name]))) for name in sorted(names)]


def read(root, *, roots=ROOTS, required=frozenset(('operation','replica','seed'))):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'learner snapshot directory')
    need(type(roots) in (set, frozenset) and roots and all(type(v) is str and re.fullmatch('[a-z][a-z-]*', v) for v in roots),
         'learner snapshot declared roots')
    need(type(required) in (set, frozenset) and required <= roots, 'learner snapshot declared required roots')
    identities = e.parse(regular(root / 'original-identities.json', e.MIB))
    need(type(identities) is dict and set(identities) == roots, 'learner snapshot original roots')
    resources = resource_usage(e.parse(regular(root / 'resources.json', 4096)))
    present = set(); paths = []; keys = set(); files = {}; count = total = 0
    for name in sorted(roots):
        row = identities[name]
        need(type(row) is dict and set(row) == {'path', 'present', 'members'}
             and type(row['present']) is bool and type(row['members']) is dict,
             'learner snapshot identity row')
        path = original_path(row['path'])
        need(all(path != p and path not in p.parents and p not in path.parents for p in paths),
             'learner snapshot overlapping original roots')
        paths.append(path); members = row['members']; count += len(members)
        need(count <= 256, 'learner snapshot inventory capacity')
        if not row['present']:
            need(not members, 'learner snapshot absent root has members'); files[name] = {}; continue
        present.add(name)
        need('.' in members and type(members['.']) is dict and members['.'].get('directory') is True,
             'learner snapshot original root directory')
        copied = root / name
        need(copied.is_dir() and not copied.is_symlink(), 'learner snapshot copied root')
        observed = {'.'}; pending = [copied]
        while pending:
            parent = pending.pop()
            for child in parent.iterdir():
                relative = child.relative_to(copied).as_posix(); observed.add(relative)
                need(len(observed) <= len(members) and not child.is_symlink(), 'learner snapshot copied inventory')
                need(child.is_dir() or child.is_file(), 'learner snapshot regular member')
                if child.is_dir(): pending.append(child)
        need(observed == set(members), 'learner snapshot copied inventory')
        data = {}
        for relative, identity in sorted(members.items()):
            member_path(relative)
            need(type(identity) is dict and type(identity.get('key')) is str
                 and identity['key'].strip() and len(identity['key'].encode()) <= 4096,
                 'learner snapshot original inode')
            need(identity['key'] not in keys, 'learner snapshot original inode alias'); keys.add(identity['key'])
            file = copied if relative == '.' else copied / relative
            if identity.get('directory') is True:
                need(set(identity) == {'key', 'directory'} and file.is_dir(), 'learner snapshot directory identity')
                data[relative] = None
            else:
                need(set(identity) == {'key', 'bytes', 'sha256'} and type(identity['bytes']) is int
                     and 0 <= identity['bytes'] <= 64 * e.MIB and type(identity['sha256']) is str
                     and re.fullmatch('[0-9a-f]{64}', identity['sha256']) is not None,
                     'learner snapshot file identity')
                raw = regular(file, 64 * e.MIB); total += len(raw)
                need(total <= 512 * e.MIB, 'learner snapshot total capacity')
                need(len(raw) == identity['bytes'] and digest(raw) == identity['sha256'], 'learner snapshot original bytes')
                data[relative] = raw
        files[name] = data
    need(required <= present, 'learner snapshot required roots')
    need({p.name for p in root.iterdir()} == present | {'original-identities.json', 'resources.json'},
         'learner snapshot exact layout')
    return Snapshot(identities, files, resources)


def validate(root):
    snapshot = read(root)
    return dict(status='PARTIAL', scope='copied-bytes-and-recorded-original-identities',
                members=sum(len(v) for v in snapshot.files.values()),
                selectedHeadQualified=False, nativeHistoryQualified=False,
                processDeathQualified=False, phase3Complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(validate(args.root), sort_keys=True))
