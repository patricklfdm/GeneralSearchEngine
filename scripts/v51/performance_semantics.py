"""Read-only comparison of rich workload observations and actual V4 backup bytes.

No timings or automatic protocol success can be inferred from this qualification.
"""
import struct
import re
from pathlib import Path
from . import performance_model as model, performance_plan as plan
from .storage_inspector import inventory
from scripts.v43 import derived_format_v12 as backup

MEMBER_BYTES = 64 << 20


def read(path):
    path = Path(path)
    model.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= MEMBER_BYTES, 'semantic member bound/type')
    return model.strict_json(path.read_bytes())


def state_observation(observed, wanted):
    model.need(set(observed) == {'sequence', 'indexCount', 'documents'}, 'semantic state fields')
    expected = dict(sequence=wanted.sequence, indexCount=len(wanted.indexes), documents=list(wanted.documents.values()))
    model.need(model.canonical(observed) == model.canonical(expected), 'rich observed application differs')


def bytes_member(path):
    path = Path(path)
    model.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= MEMBER_BYTES, 'rich binary member bound/type')
    return path.read_bytes()


def descriptors(cursor, count):
    model.need(0 <= count <= 4, 'rich descriptor count')
    values = [(cursor.unpack('>B')[0], cursor.string(1024), cursor.string(128, True)) for _ in range(count)]
    kinds = {1: 'equality', 2: 'range', 3: 'prefix', 4: 'text'}
    model.need(all(kind in kinds for kind, _, _ in values), 'rich index kind')
    indexes = [dict(field=name, kind=kinds[kind], analyzer=analyzer) for kind, name, analyzer in values]
    model.need(len({v['field'] for v in indexes}) == count and all(v in model.INDEXES for v in indexes), 'rich index definition/duplicate')
    return indexes


def metadata(path):
    cursor = backup.uncheck(bytes_member(path), 64, 'rich metadata')
    magic, major, minor, most, least = cursor.unpack('>QhhQQ')
    family = cursor.string(128)
    length, = cursor.unpack('>I')
    profile, digest = cursor.take(length), cursor.take(32)
    model.need((magic, major, minor, family) == (backup.METADATA_MAGIC, 1, 2, 'gse-durable') and
               profile == backup.profile_bytes() and digest == backup.profile_digest(), 'rich metadata profile')
    identity = [cursor.string(128) for _ in range(3)]
    bounds = cursor.unpack('>iiiiiqqqi')
    model.need(identity == ['performance-store', 'semantic-schema', 'semantic-codec'] and
               bounds[:-1] == (1, 1024, 4096, 16, 1024, 32 << 20, 128 << 20, 4 << 20), 'rich metadata application/bounds')
    indexes = descriptors(cursor, bounds[-1])
    model.need(indexes == [model.INDEXES[i] for i in (3, 1, 2, 0)], 'rich source index order')
    cursor.finish()
    return dict(history=(most, least), profile=digest, indexes=indexes)


def checkpoint(data, wanted, meta):
    cursor = backup.uncheck(data, 88, 'rich checkpoint')
    magic, major, minor, most, least = cursor.unpack('>QhhQQ')
    model.need((magic, major, minor) == (backup.CHECKPOINT_MAGIC, 1, 2) and
               (most, least) == meta['history'] and cursor.take(32) == meta['profile'], 'rich checkpoint identity')
    sequence, next_doc, live, count = cursor.unpack('>qiii')
    indexes = descriptors(cursor, count)
    model.need(sorted(indexes, key=lambda v: v['field']) == wanted.indexes and sequence == wanted.sequence, 'rich checkpoint indexes/sequence')
    slots, = cursor.unpack('>i')
    model.need(0 <= slots <= 1024 and slots == next_doc, 'rich checkpoint slot bound')
    documents = {}
    for _ in range(slots):
        state, = cursor.unpack('>B')
        model.need(state in (0, 1), 'rich checkpoint slot state')
        if state == 0:
            continue
        size, = cursor.unpack('>i')
        model.need(size == 4, 'rich checkpoint key size')
        key, = struct.unpack('>i', cursor.take(size))
        size, = cursor.unpack('>i')
        model.need(0 <= size <= 256, 'rich checkpoint document size')
        doc = model.decode_document(cursor.take(size))
        model.need(key == doc[0] and key not in documents, 'rich checkpoint document/key identity')
        documents[key] = doc
    cursor.finish()
    model.need(live == len(documents) and list(documents.items()) == list(wanted.documents.items()), 'rich checkpoint ordered documents')
    return dict(sequence=sequence, documents=len(documents), slots=slots, indexes=indexes, sha256=model.sha(data))


def source_backup(directory, wanted):
    directory = Path(directory)
    members = inventory(directory)
    names = ['gse-backup-checkpoint', 'gse-backup-metadata', 'gse-backup-manifest']
    model.need(set(members) == set(names) and max(v['size'] for v in members.values()) <= MEMBER_BYTES, 'rich backup inventory/size')
    payloads = {name: bytes_member(directory / name) for name in names[:2]}
    meta = metadata(directory / 'gse-backup-metadata')
    report = checkpoint(payloads['gse-backup-checkpoint'], wanted, meta)
    model.need(report['indexes'] == meta['indexes'], 'rich source backup index order')
    cursor = backup.uncheck(bytes_member(directory / 'gse-backup-manifest'), 160, 'rich backup manifest')
    magic, major, minor = cursor.unpack('>Qhh')
    family, source = cursor.string(128), cursor.string(128)
    source_major, source_minor = cursor.unpack('>hh')
    model.need((magic, major, minor, family, source, source_major, source_minor) ==
               (backup.BACKUP_MAGIC, 1, 2, 'gse-backup', 'gse-durable', 1, 2) and cursor.take(32) == meta['profile'], 'rich backup format/profile')
    most, least, sequence = cursor.unpack('>QQq')
    model.need((most, least) == meta['history'] and sequence == wanted.sequence, 'rich backup history/sequence')
    identity = [cursor.string(128) for _ in range(3)]
    version, count = cursor.unpack('>iI')
    model.need(identity == ['performance-store', 'semantic-schema', 'semantic-codec'] and version == 1 and count == 2, 'rich backup identity/members')
    for name in names[:2]:
        actual, size, digest = cursor.string(128), cursor.unpack('>Q')[0], cursor.take(32)
        model.need(actual == name and size == len(payloads[name]) and digest.hex() == model.sha(payloads[name]), 'rich backup member binding')
    digest = cursor.take(32)
    model.need(digest.hex() == model.sha(backup._backup_preimage(payloads, meta['profile'], meta['history'], sequence, *identity, version)), 'rich backup content identity')
    model.need(cursor.unpack('>q')[0] >= 0, 'rich backup creation time')
    cursor.string(256, True)
    cursor.finish()
    return dict(report, contentIdentity='gse-backup-v3-' + digest.hex())


def selected_checkpoint(directory, wanted):
    directory = Path(directory)
    meta = metadata(directory / 'gse-metadata')
    cursor = backup.uncheck(bytes_member(directory / 'gse-checkpoint-manifest'), 88, 'rich selector')
    magic, major, minor, most, least = cursor.unpack('>QhhQQ')
    model.need((magic, major, minor) == (backup.CHECKPOINT_MANIFEST_MAGIC, 1, 2) and
               (most, least) == meta['history'] and cursor.take(32) == meta['profile'], 'rich checkpoint selector identity')
    sequence, size, crc = cursor.unpack('>qqI')
    name = cursor.string(256)
    model.need(re.fullmatch(r'gse-checkpoint-[0-9]{20}-[0-9a-f]{32}\.chk', name), 'rich checkpoint selector path')
    generation, first_sequence = cursor.unpack('>qq')
    cursor.finish()
    data = bytes_member(directory / name)
    model.need(sequence == wanted.sequence and size == len(data) and struct.unpack('>I', data[-4:])[0] == crc and
               generation > 1 and first_sequence == sequence + 1, 'rich checkpoint selector boundary')
    report = checkpoint(data, wanted, meta)
    model.need(report['indexes'] == [model.INDEXES[i] for i in (3, 2, 0, 1)], 'rich recreated index order')
    return report


def validate_calls(rows, admitted_plan):
    expected = model.expected(admitted_plan)
    wanted = expected['rows']
    model.need(len(rows) == len(wanted), 'rich call count')
    state = model.initial(admitted_plan)
    for row, call, expected_row in zip(rows, model.program(admitted_plan), wanted):
        model.need(row.get('outcome') == 'SUCCESS', 'rich hidden failed outcome')
        fields = ('ordinal', 'window', 'cycle', 'operation', 'keys', 'payloadSha256', 'answer', 'answerSha256', 'beforeSequence', 'afterSequence')
        model.need(set(row) == {*fields, 'outcome', 'state'} and
                   model.canonical({k: row[k] for k in fields}) == model.canonical({k: expected_row[k] for k in fields}),
                   'rich operation/answer/order differs')
        if call['operation'] in model.OP_IDS:
            state.apply(model.OP_IDS[call['operation']], call['payload'])
        state_observation(row['state'], state)
    return state


def validate(root, admitted_plan, expected_core, process):
    root = Path(root)
    plan.validate(admitted_plan)
    identity = read(root / 'identity.json')
    control = next(v for v in admitted_plan['publishedControls']['artifacts'] if v['version'] == '4.4.0')
    model.need(identity['execution'] == 'published-v4.4-rich-semantics-only' and identity['performanceMeasured'] is False,
               'rich execution provenance')
    model.need(identity['coreSource'] == str(Path(expected_core).resolve()) and identity['coreSha256'] == control['sha256']
               and identity['coreSha256'] == model.sha(Path(expected_core).read_bytes()), 'rich loaded control identity')
    model.need(identity['pid'] == process['pid'] and process['exitCode'] == 0 and
               identity['javaMajor'] == 21 and str(identity['javaRuntime']).startswith('21.') and bool(identity['javaVendor']) and
               identity['jvmArguments'] == admitted_plan['jvmArguments'], 'rich process/toolchain identity')
    model.need(identity['planFileSha256'] == model.sha((root.parent / 'plan.json').read_bytes()), 'rich plan file identity')
    args = process['args']
    model.need(args[:6] == ['java', *admitted_plan['jvmArguments'], '-cp'] and
               args[6].split(':') == [str(Path(expected_core).resolve()), str(root.parent / 'classes-published-v44')],
               'rich isolated classpath')
    initial = model.initial(admitted_plan)
    state_observation(read(root / 'initial.json'), initial)
    tape = root / 'calls.jsonl'
    model.need(tape.stat().st_size <= MEMBER_BYTES and not tape.is_symlink(), 'rich call tape bound/type')
    raw = tape.read_bytes()
    model.need(raw.endswith(b'\n'), 'partial rich call tape')
    rows = [model.strict_json(line) for line in raw.splitlines()]
    state = validate_calls(rows, admitted_plan)
    source = source_backup(root / 'source', initial)
    final_checkpoint = selected_checkpoint(root / 'store', state)
    observed = inventory(root / 'source')
    model.need(observed == read(root / 'source-before.json') == read(root / 'source-after.json'), 'rich source changed')
    state_observation(read(root / 'final.json'), state)
    state_observation(read(root / 'reopened.json'), state)
    state_observation(read(root / 'restored.json'), initial)
    return dict(status='PASS', execution='published-v4.4-rich-semantics-only', calls=len(rows),
                finalSequence=state.sequence, documents=len(state.documents), sourceBackup=source,
                finalCheckpoint=final_checkpoint, performanceMeasured=False, automaticRuntimeExecuted=False)
