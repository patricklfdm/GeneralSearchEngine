"""Typed current-prefix closure; inputs must come from the independent original replay.

This derives a NEW packet's roots, never deletes a retained source. Callers add
exact owned tails, frozen future obligations and newly derived selected retention.
The earlier readers keep their original default derivation for historical archives.
"""
from . import format_fixture as f


def prefix(packet, root_record):
    def need(value, message):
        if not value: raise ValueError(message)
    def digest(raw):
        import hashlib
        return hashlib.sha256(raw).hexdigest()
    root = f.decode(root_record, 'records', 'ROOT')
    cap, objects = packet['capsule'], packet['objects']
    need(objects.get(digest(root_record)) == root_record, 'reachable exact original ROOT')
    need(cap['initial'] == root['genesis'], 'reachable exact original GENESIS')
    wanted = {digest(root_record), root['genesis'], cap['catalog']}
    for item in cap['items']:
        wanted.add(item['statement']); wanted.update(item['endorsements'])
        if item['kind'] == 'MEMBERSHIP':
            wanted.update((item['descriptor'], item['certificate']))
            cert = f.decode(objects[item['certificate']], 'records', 'CERTIFICATE')
            proof = {k:v for k,v in cert.items() if k != 'proofs'}
            accept = {k:v for k,v in proof.items() if k != 'accepts'}
            wanted.update((digest(f.encode('records', 'PROOF', proof)), digest(f.encode('records', 'ACCEPT', accept)), cert['entry']))
            entry = f.decode(objects[cert['entry']], 'records', 'ENTRY')
            wanted.add(entry['payload'])
        else:
            need(item['kind'] == 'RANGE', 'reachable typed capsule item')
    need(wanted <= objects.keys(), 'reachable original object absent')
    need(all(digest(objects[h]) == h for h in wanted), 'reachable original object digest')
    return {h:objects[h] for h in sorted(wanted)}
