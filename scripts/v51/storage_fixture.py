"""Independent test-only sealed root-ledger fixture, not public bootstrap or V4 backup."""
import base64
import hashlib
import json
from pathlib import Path

from . import format_encoder as enc
from .fixtures import fixture_receipt


def b64(raw): return base64.b64encode(raw).decode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def create(root):
    root = Path(root).resolve()
    samples = json.loads((enc.CATALOG.parent / 'format-fixtures.json').read_text())['storage']
    manifest, genesis = [base64.b64decode(samples[k]) for k in ('MANIFEST', 'GENESIS')]
    mdigest = manifest[16:48].hex()
    plan = json.loads(base64.b64decode(samples['PLAN'])[48:])
    plan['operationPath'] = str(root / 'operation')
    targets = []
    for ordinal in range(1, 4):
        node = f'node-{ordinal}'
        files = {'replica.lock': b'', 'manifest.gsr': manifest, 'genesis.gsr': genesis,
                 'node.gsr': enc.encode('NODE', dict(manifestDigest=mdigest, node=node, origin='BOOTSTRAP')),
                 'storage-ready.gsr': enc.encode('READY', dict(manifestDigest=mdigest, node=node, genesisDigest=genesis[16:48].hex()))}
        for name, kind in [('promises.gsr', 4), ('accepted.gsr', 24), ('proofs.gsr', 6)]:
            files[name] = enc.encode('JOURNAL', dict(manifestDigest=mdigest, node=node, recordKind=kind))
        files['promises.gsr'] += enc.encode('PROMISE', dict(manifestDigest=mdigest, epoch=1, proposer=None, incarnation='00000000-0000-0000-0000-000000000000'))
        t = plan['targets'][ordinal - 1]
        t.update(authorityPath=str(root / node), materializationPath=str(root / f'app-{ordinal}'),
                 files=[dict(path=n, size=len(v), sha256=sha(v)) for n, v in sorted(files.items())])
        targets.append(files)
    plan_raw = enc.encode('PLAN', plan)
    preps = [enc.encode('PREPARED', dict(node=t['node'], manifestDigest=mdigest, planDigest=plan_raw[16:48].hex(),
                                        inventoryDigest=sha(enc.canonical(t['files'])))) for t in plan['targets']]
    receipt = enc.encode('RECEIPT', dict(plan=b64(plan_raw), preparations=list(map(b64, preps))))
    for i, files in enumerate(targets, 1):
        directory = root / f'node-{i}'; directory.mkdir()
        files.update({'bootstrap-prepared.gsr': preps[i - 1], 'bootstrap-seal.gsr': enc.encode('SEAL', dict(node=f'node-{i}', receipt=b64(receipt)))})
        for name, contents in files.items(): (directory / name).write_bytes(contents)
    return records(manifest)


def records(manifest, epoch=2, payload=b'one'):
    digest = manifest[16:48].hex(); incarnation = '11111111-1111-1111-1111-111111111111'
    ballot = dict(manifestDigest=digest, epoch=epoch, proposer=f'node-{(epoch-2)%3+1}', incarnation=incarnation)
    entry = enc.encode('ENTRY', dict(manifestDigest=digest, originEpoch=2, originIncarnation=incarnation,
            index=1, operation=1, previousEpoch=1, previousIndex=0, previousDigest=digest, payload=b64(payload), payloadDigest=sha(payload)))
    accepted = enc.encode('ACCEPT', dict(ballot, entry=b64(entry), entryDigest=entry[16:48].hex()))
    receipts = [dict(voter=n, digest=fixture_receipt('ACCEPT_ACK', digest, n, epoch, ballot['proposer'], incarnation, 1, entry[16:48].hex())) for n in ('node-1', 'node-2')]
    proof = enc.encode('PROOF', dict(ballot, index=1, entryDigest=entry[16:48].hex(), previousDigest=digest, receipts=receipts))
    return {'PROMISE': enc.encode('PROMISE', ballot), 'ACCEPT': accepted, 'PROOF': proof}
