"""Derive same-cut observations from independently replayed original copies.

The enclosing reader must first derive the supplied inventories from bootstrap,
votes and publication. Inventory consistency alone is not historical authority;
network transfer and force ordering are checked by that enclosing reader.
"""
import base64
import copy
from . import peer_confirmation_evidence as confirmation
from . import round_storage_evidence as c

f, r, need = confirmation.f, confirmation.r, confirmation.need


def _observed(before, identity, generation, *, defer_renewal=False):
    """Expected ledger bytes; generation must come from original replay."""
    state = r.decode(before); plan = copy.deepcopy(state['plan']); confirmation.plan(plan)
    point = confirmation.confirmation(base64.b64encode(generation).decode(), state['root'], identity)
    need(point['cut']['view'] == plan['view'], 'observed copy original view')
    row = next((v for v in plan['peers'] if v['identity'] == identity), None)
    need(row is not None, 'observed copy permanent identity')
    at = point['cut']['index']; old = row['possible']
    # Genesis has no earlier obligation to discharge. An old observation must
    # not replace newer knowledge or invent a ledger write.
    if at == 0 or at < old[0]['cut']['index']: return before
    for value in old:
        need(value['cut']['index'] != at or value == point, 'observed copy conflicting endpoint')
    renewals = {v['cut']['index']: v for v in row.get('renewals', [])}
    for value in old:
        if value['cut']['index'] < at:
            need(value['cut']['index'] not in renewals or renewals[value['cut']['index']] == value,
                 'observed copy conflicting renewal')
            renewals[value['cut']['index']] = value
    # Explicit maintenance semantics only: preserve the entire original ledger,
    # including revision and any later target. Never discard debt to make room.
    if defer_renewal and len(renewals) > 2: return before
    proof = base64.b64encode(generation).decode()
    if 'confirmation' in row and confirmation.confirmation(row['confirmation'], state['root'], identity) == point:
        # The previous proof was already derived by the enclosing original
        # replay; an equivalent later manifest does not rewrite its bytes.
        proof = row['confirmation']
    row['possible'] = [point] + [v for v in old if v['cut']['index'] > at]
    row['confirmation'] = proof
    if renewals: row['renewals'] = [renewals[i] for i in sorted(renewals)]
    else: row.pop('renewals', None)
    confirmation.plan(plan)
    if plan == state['plan']: return before
    need(state['revision'] < 2**63-2, 'observed copy revision exhausted')
    return r.frame(dict(state, revision=state['revision']+1, previous=r.sha(before), plan=plan))


def observe_same_cut(before, local_files, original_files, *, defer_renewal=False):
    """Only complete exact-current original copies can enter this projection."""
    _, _, local = c.current(local_files)
    prefix, _, packet = c.current(original_files)
    identity = f.decode(original_files['node.gsr'], 'records', 'NODE')['identity']
    owner = f.decode(local_files['node.gsr'], 'records', 'NODE')['identity']
    state = r.decode(before); generation = original_files[prefix+'generation.gsr']
    need(state['owner'] == owner and state['root'] == local['capsule']['root'] == packet['capsule']['root']
         and state['plan']['view'] == local['capsule']['cut']['view']
         and c.anchor(local['capsule']) == c.anchor(packet['capsule']), 'observed copy exact current original')
    return _observed(before, identity, generation, defer_renewal=defer_renewal)
