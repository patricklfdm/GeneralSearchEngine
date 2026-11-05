"""Compose original-content bindings for every observed export allocation.

Bindings are emitted in memory only after the independent session/direct/probe
readers succeed on the same admitted native input. A binding map or this helper
alone is not original content authority or whole-runtime qualification.
"""
from collections import Counter
import hashlib
import json

from . import session_export_evidence as exports

need = exports.need
SCOPES = ('session', 'direct', 'probe')
FIELDS = {'node', 'owner', 'scope', 'role', 'binding', 'bytes', 'start', 'end'}


def proof(node, owner, scope, role, binding, size, life):
    return dict(node=node, owner=owner, scope=scope, role=role, binding=binding,
                bytes=size, start=life['start'], end=life['end'])


def publish(target, proofs):
    """A failed or conflicting reader cannot publish a partial successful set."""
    if target is None: return
    need(type(target) is dict and type(proofs) is list, 'export coverage binding collection')
    incoming = {}
    for value in proofs:
        need(type(value) is dict and set(value) == FIELDS and
             all(type(value[k]) is str and value[k] for k in ('node', 'owner', 'scope', 'role', 'binding')) and
             value['scope'] in SCOPES and value['role'] in exports.ROLES and len(value['binding']) == 64 and
             all(c in '0123456789abcdef' for c in value['binding']) and
             type(value['bytes']) is int and value['bytes'] > 0 and
             type(value['start']) is int and type(value['end']) is int and 0 < value['start'] < value['end'],
             'export coverage exact content binding')
        key = value['node'], value['owner']
        need(key not in target and key not in incoming, 'export coverage duplicate allocation proof')
        incoming[key] = dict(value)
    target.update(incoming)


def replay(traces, closes, bindings):
    inventory = exports.replay(traces, closes)
    account = exports.close.replay(traces, closes, export_ownership=True)
    wanted = {}; ownership = {}; sizes = {}; roles = Counter(); scopes = Counter()
    for node, owner in account['owners'].items():
        for session in owner['exportAttachments'].values():
            for name in session['children']: ownership[node, name] = 'session'
        for name in owner['directExports']: ownership[node, name] = 'direct'
        for name, call in owner['probeExports'].items():
            for child in (name, *call['acquired']['children']): ownership[node, child] = 'probe'
        for name, life in owner['lifetimes'].items():
            role = exports.kind(name)
            if role is None: continue
            key = node, name; wanted[key] = life; roles[role] += 1
            original = [v for v in traces[node]['changes'][life['start']]['added'] if v['owner'] == name]
            need(len(original) == 1 and original[0]['unit'] == 'CONTROL' and not original[0]['claimSource'],
                 'export coverage original reservation')
            sizes[key] = original[0]['bytes']
    need(type(bindings) is dict and bindings and set(bindings) == set(wanted),
         'export coverage complete original allocation set')
    validated = {}; publish(validated, list(bindings.values()))
    need(validated == bindings, 'export coverage exact allocation keys')
    for key, value in bindings.items():
        node, name = key; life = wanted[key]
        need(key in ownership and value['scope'] == ownership[key], 'export coverage original ownership scope')
        need(value['role'] == exports.kind(name) and name.startswith(value['role']+'-'+value['binding']+'-'),
             'export coverage original content identity')
        need(value['bytes'] == sizes[key] and (value['start'], value['end']) == (life['start'], life['end']),
             'export coverage original extent and lifetime')
        scopes[value['scope']] += 1
    encoded = json.dumps([bindings[key] for key in sorted(bindings)], sort_keys=True, separators=(',', ':')).encode()
    return dict(status='PASS', scope='complete-observed-export-allocation-content-and-ownership',
                allocations=len(bindings), byScope=dict(sorted(scopes.items())), byRole=dict(sorted(roles.items())),
                otherControlAllocations=sum(len(v['lifetimes']) for v in account['owners'].values())-len(bindings),
                allocationBindingsSha256=hashlib.sha256(encoded).hexdigest(), exportInventory=inventory,
                allObservedExportAllocationsQualified=True, unclaimedAllocations=[],
                failedConstructorExportsQualified=False, allExportFailurePathsQualified=False,
                wholeRuntimeResourcesQualified=False, phase3Complete=False)
