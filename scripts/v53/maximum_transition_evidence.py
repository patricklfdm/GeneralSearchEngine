"""Same-original image pressure, receive refusal, admitted REMOVE and continuation.

The small diagnostic cannot qualify maximum bytes. Neither mode proves an online
controller, admitted learner, full metadata pressure or the final-source cohort.
"""
import argparse
import copy
import json
import struct
import uuid
from pathlib import Path
from . import maximum_application_evidence as maximum
from . import admitted_cross_view_evidence as q
from .offline_fixture_image import application, image_members, uncheck
from .retirement_source_process_evidence import same, read
from .selected_prefix_evidence import prefix

e, c, b, t, selection = q.e, q.c, q.b, q.t, q.selection
SMALL = [(7, 'original'), (2, '你好')]
MODES = ('maximum', 'diagnostic')
NEGATIVE_NAMES = ('wrong-reason', 'foreign-packet', 'packet-digest', 'packet-bytes', 'retained-scratch',
                  'missing-authority', 'changed-authority', 'duplicate-authority', 'missing-close',
                  'reordered-states', 'eighth-image', 'borrowed-source-category', 'uncharged-packet',
                  'uncharged-records', 'leaked-close', 'boolean-leases')
CRITICAL = {
    'accept': ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_BEFORE_RETURN', 'ACCEPT_BEFORE_RETURN'],
    'proof': ['PROOF_CANDIDATE_FORCED', 'PROOF_PARENT_FORCED', 'PROOF_BEFORE_RETURN'],
    'certificate': ['CERTIFICATE_CANDIDATE_FORCED', 'CERTIFICATE_PARENT_FORCED', 'CERTIFICATE_BEFORE_RETURN'],
    'apply': ['APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN', 'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'],
    'publish': ['PUBLICATION_SELECTOR_FORCED', 'PUBLICATION_BEFORE_RETURN', 'PUBLICATION_BEFORE_RETURN'],
    'prepare': ['PROMISE_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN'],
    'select': ['SELECTED_FORCED', 'SELECTED_BEFORE_RETURN'],
    'install': ['INSTALL_SELECTOR_FORCED', 'INSTALL_BEFORE_RETURN'],
    'removed-adopt': ['ADOPTION_INSTALL_VALIDATED', 'PROMISE_FORCED', 'ADOPTION_INSTALL_FENCED',
                      'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'ADOPTION_INSTALL_BEFORE_RETURN'],
    'removed-refusal': [],
}


def source(root, mode):
    e.need(mode in MODES, 'maximum transition mode')
    if mode == 'maximum':
        image, extra = maximum.source(root)
        return image, extra, maximum.documents(extra)
    image = t.plans.read(root / 'source.image', maximum.MAXIMUM)
    application(image, maximum.HISTORY, 41, SMALL)
    members = image_members(image); backup = c.inventory(root / 'source-backup')
    e.need(set(members) == set(backup), 'maximum transition backup inventory')
    for name in ('gse-backup-checkpoint', 'gse-backup-metadata'):
        e.need(members[name] == backup[name], 'maximum transition backup payload')
    raw = backup['gse-backup-manifest']; uncheck(raw, 160, 'maximum transition manifest')
    prefix = len(members['gse-backup-manifest']) - 16
    e.need(len(raw) == len(members['gse-backup-manifest']) + 32 and
           raw[:prefix] == members['gse-backup-manifest'][:prefix], 'maximum transition manifest binding')
    stamp, size = struct.unpack('>qI', raw[prefix:prefix + 12]); request = raw[prefix + 12:-4]
    e.need(stamp >= 0 and size == len(request) == 32 and all(v in b'0123456789abcdef' for v in request),
           'maximum transition request identity')
    return image, -1, SMALL


class Walk(q.Walk):
    def installed_packet(self, members, packet, root_record):
        # Current selection keeps the independently derived typed closure. The
        # shared historical reader retains its original default unchanged.
        return c.packet_bytes(packet['capsule'], prefix(packet, root_record), packet['images'])

    def required_anchors(self):
        anchors = {}
        def add(anchor):
            index = anchor['cut']['index']
            e.need(index not in anchors or anchors[index] == anchor, 'maximum transition conflicting retained anchor')
            anchors[index] = anchor
        # The removed voter did not join the new campaign. Its retained source
        # is not an obligation of the publishing survivor's generation.
        for name, raw in self.group[self.active[0]].items():
            if name.startswith('sources/') and name.endswith('/source.gscp'):
                add(c.anchor(c.p.decode(raw)['capsule']))
        if self.first:
            add(self.first['parent']); add(self.first['end'])
        return [anchors[index] for index in sorted(anchors)]

    def adoption_ancestry(self, files, members, packet):
        cuts = {}
        for name, raw in files.items():
            if name.startswith('sources/') and name.endswith('/source.gscp'):
                cut = c.p.decode(raw)['capsule']['cut']; index = cut['index']
                e.need(index not in cuts or cuts[index] == cut, 'maximum transition conflicting adoption source')
                cuts[index] = cut
        return b''.join(q.retained_campaign_ancestry(members, packet, cuts[index]) for index in sorted(cuts))


def start(root, image, docs):
    w = Walk.__new__(Walk); w.root = root
    w.required = {'original-plan.gsbp', 'original-application.image', 'initial', 'calls.json', 'observations.json'}
    w.required |= {'round-1-' + s for s in ('prepared', 'selected', 'installed', 'settled')}
    original = b.original(root, 5, True); record = e.f.decode(original['node-1']['root.gsr'], 'records', 'ROOT')
    projected = t.plans.read(root / 'original-application.image', maximum.MAXIMUM)
    plan = t.plans.decode((root / 'original-plan.gsbp').read_bytes(), projected, details=True,
                          size=5, source='VERIFIED_DURABLE_BACKUP')
    backup = c.inventory(root.parent / 'source-backup')
    same(plan['plan']['descriptor']['sourceInventory'],
         [dict(path=n, kind=1, size=len(v), sha256=e.digest(v)) for n, v in sorted(backup.items())],
         'maximum transition source admission')
    history = record['historyId']
    e.need(history != maximum.HISTORY and uuid.UUID(history).version == 4 and record['baseSequence'] == 41,
           'maximum transition fresh history')
    e.need(len(image) == len(projected), 'maximum transition projected extent')
    application(projected, history, 41, docs)
    w.group = b.campaign(root, original, 1); w.active = sorted(w.group); w.slot = 0; w.counter = 2
    w.first = None; w.observed = set(); w.phases = {}; w.documents = docs; w.history = history
    for label in ('prepare-1', 'select-1', 'install-1'): w.phase(label, w.active)
    return w, projected


def call_order():
    """Independent exact calls, including reads used to construct the REMOVE request."""
    names = [f'node-{n}' for n in range(1, 6)]; active = names; calls = []
    def one(label): calls.append(('node-1', label))
    def many(label, nodes): calls.extend((n, label) for n in nodes)
    def campaign(number, nodes, prefix='campaign'):
        one(f'allocate-{number}')
        for phase in ('prepare', 'select', 'install'): many(f'{phase}-{number}', nodes)
        for phase in ('copy', 'maintain'): many(f'{prefix}-{number}-settled-{phase}', nodes)
    def publish(slot, nodes):
        one('publication-original-ancestry'); one('inspect-context')
        for phase in ('accept', 'proof', 'certificate', 'apply', 'publish'): many(f'{phase}-{slot}', nodes)
        for phase in ('copy', 'maintain'): many(f'slot-{slot}-settled-{phase}', nodes)
    campaign(1, active, 'round'); publish(1, active); campaign(3, active)
    one('inspect-context')  # expected authority in REMOVE request
    for slot in range(2, 6): publish(slot, active)
    one('inspect-context')  # frozen descriptor
    publish(6, active); one('inspect-context')  # joint view assertion
    active = names[:-1]; campaign(4, active); publish(7, active); one('inspect-context')
    one('removal-source-1'); calls.extend([('node-5', 'removed-adopt-1'), ('node-5', 'removed-refusal-1')])
    campaign(5, active); publish(8, active); publish(9, active); publish(10, active); campaign(6, active)
    many('inspect-maximum-transition', active)
    return calls


def calls(rows, phases):
    expected = call_order()
    e.need(type(rows) is list and len(rows) == len(expected), 'maximum transition complete call inventory')
    for row, (node, operation) in zip(rows, expected):
        e.exact(row, 'node operation events')
        e.need((row['node'], row['operation']) == (node, operation) and type(row['events']) is list and
               0 < len(row['events']) <= 4096 and all(type(v) is str for v in row['events']), 'maximum transition call order')
    for label, nodes in phases.items():
        selected = [v for v in rows if v['operation'] == label]
        e.need([v['node'] for v in selected] == nodes, 'maximum transition force owners')
        required = CRITICAL[label.rsplit('-', 1)[0]]
        for row in selected:
            e.need([v for v in row['events'] if v in set(required)] == required, 'maximum transition force order')
            if label.startswith('removed-refusal-'):
                e.need(not any(v.startswith(('PROMISE_', 'BASIS_', 'SELECTED_')) for v in row['events']),
                       'maximum transition removed grant')


def publication(root, image, docs):
    w, projected = start(root, image, docs)
    w.publish('BARRIER'); w.campaign()
    installed = {n: c.inventory(root / 'campaign-3-installed' / n) for n in w.active}
    expected, floor_events = maximum.peak_plan(installed); del installed
    members, packet, cap, state = w.state(); survivors = w.active[:-1]
    identities = {v['node']: v for v in state['identities']}
    request = dict(root=cap['root'], expected=e.authority(cap['root'], cap['cut']['view']), number=1,
                   kind='REMOVE', target=[identities[n] for n in survivors])
    w.publish('RESERVE', dict(request=request)); w.publish('PREPARE', dict(number=1, revision=1))
    w.publish('READY', dict(number=1, receipt=None)); w.publish('SEAL', dict(number=1))
    operation = w.state()[3]['results'][-1]
    w.publish('INTENT', dict(sealed={k: operation[k] for k in ('request', 'prepared', 'receipt')})); w.campaign(survivors)
    w.publish('FINAL', dict(binding=operation['binding']), survivors); w.active = survivors; w.removed(1, 'node-5')
    w.campaign(); w.publish('BARRIER'); w.publish('RETIRE', dict(through=1)); w.publish('BARRIER'); w.campaign()
    for node in w.active:
        _, final, packet = c.current(w.group[node]); cap = packet['capsule']
        e.need(cap['cut']['index'] == 10 and cap['cut']['view']['generation'] == 1 and
               final[cap['application'] + '.image'] == projected, 'maximum transition final stable bytes')
    observed = read(root / 'observations.json')
    e.need(len(observed) == len(w.observed) and {e.f.canonical(v) for v in observed} == w.observed,
           'maximum transition original observations')
    rows = read(root / 'calls.json'); calls(rows, w.phases); selection.layout(root, w.required, 'maximum transition publication')
    return expected, floor_events, projected, rows


def usage(files, extent):
    images = {n: len(v) for n, v in files.items() if n.endswith('.image')}
    e.need(len(images) == 7 and set(images.values()) == {extent}, 'maximum transition seven images')
    sources = sum(len(v) for n, v in files.items() if v is not None and not n.endswith('.image') and
                  (n.startswith('sources/') or (n.startswith('floor-copies/') and n.count('/') == 2)))
    generations = sum(len(v) for n, v in files.items() if v is not None and n.startswith('generations/') and not n.endswith('.image'))
    result = dict(metadata=34*e.MIB + sources + generations, staging=7*extent + sources, queued=0, leases=16,
                  counts=dict(GENERATION=2, SOURCE=5, APPLICATION=7, JOURNAL=1, MISC=1))
    e.need(result['metadata'] <= 384*e.MIB and result['staging'] <= 512*e.MIB, 'maximum transition shared bounds')
    return result


def receiver(value, files, extent):
    e.exact(value, 'schema reason packet packetSha256 packetBytes authorityBefore authorityAfter states scratchAbsent')
    packet_name = sorted(n for n in files if n.startswith('generations/') and n.endswith('/source.gscp'))[0]
    packet = files[packet_name]; decoded = c.p.decode(packet)
    e.need(set(decoded['images'].values()) == {extent}, 'maximum transition receiver image binding')
    before = usage(files, extent); refused = copy.deepcopy(before)
    refused.update(metadata=before['metadata'] + len(packet), staging=before['staging'] + len(packet), queued=4096, leases=18)
    refused['counts'].update(LEARNER=1, CONTROL=1)
    hashes = [dict(path=n, sha256=e.digest(v)) for n, v in sorted(files.items()) if v is not None]
    same(value, dict(schema='gse-v53-maximum-receiver-v1', reason='resource ownership/count', packet=packet_name,
                     packetSha256=e.digest(packet), packetBytes=len(packet), authorityBefore=hashes, authorityAfter=hashes,
                     states=[dict(stage='before', usage=before), dict(stage='refused', usage=refused), dict(stage='closed', usage=before)],
                     scratchAbsent=True), 'maximum transition exact receiver refusal')
    return packet


def peak(root, expected, events, rows, extent):
    e.need(c.inventory(root / 'seven-image-floor') == expected, 'maximum transition original peak files')
    budget = usage(expected, extent); images = []
    for name in sorted(n for n in expected if n.endswith('.image')):
        path = root / 'seven-image-floor' / name
        e.need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, 'maximum transition image alias')
        images.append(dict(path=name, bytes=extent, links=1))
    same(read(root / 'peak.json'), dict(node='node-1', operation='campaign-3-settled-maintain', event='FLOOR_BEFORE_RETURN',
                                      metadata=budget['metadata'], staging=budget['staging'], leases=16, images=images),
         'maximum transition peak accounting')
    selected = [v for v in rows if v['node'] == 'node-1' and v['operation'] == 'campaign-3-settled-maintain']
    e.need(len(selected) == 1 and [v for v in selected[0]['events'] if v in set(events)] == events,
           'maximum transition floor force order')
    packet = receiver(read(root / 'receiver.json'), expected, extent)
    e.need(c.inventory(root / 'receiver-refused') == {'source.gscp': packet}, 'maximum transition refused physical files')
    return budget


def receipt(value, mode, extent, extra):
    same(value, dict(schema='gse-v53-maximum-transition-v1', status='PASS' if mode == 'maximum' else 'DIAGNOSTIC',
                     mode=mode, imageBytes=extent, finalValueBytes=extra, slots=10, voters=4, generation=1,
                     peakImages=7, publicRuntime=False, phase3Complete=False), 'maximum transition receipt')


def _validate(root, mode):
    root = Path(root); e.need(mode in MODES, 'maximum transition mode')
    layout = {'source.image', 'source-backup', 'publication', 'seven-image-floor', 'peak.json', 'typed-final',
              'receipt.json', 'receiver.json', 'receiver-refused'}
    if mode == 'maximum': layout.add('calibration.image')
    selection.layout(root, layout, 'maximum transition')
    image, extra, docs = source(root, mode); expected, events, projected, rows = publication(root / 'publication', image, docs)
    budget = peak(root, expected, events, rows, len(image)); b.typed_image(root / 'typed-final', projected)
    receipt(read(root / 'receipt.json'), mode, len(image), extra)
    return dict(status='PASS' if mode == 'maximum' else 'DIAGNOSTIC', mode=mode, imageBytes=len(image), peak=budget,
                slots=10, removalComplete=True, publicRuntime=False, maximumBytes=mode == 'maximum',
                admittedLearner=False, fullMetadataPressure=False, phase3Complete=False), expected


def validate(root, mode='maximum'):
    return _validate(root, mode)[0]


def receiver_negatives(original, files, extent):
    receiver(original, files, extent)  # Unmodified component must pass first.
    changes = []
    def change(name, edit):
        value = copy.deepcopy(original); edit(value); changes.append((name, value))
    change('wrong-reason', lambda v: v.update(reason='shared staging capacity'))
    change('foreign-packet', lambda v: v.update(packet='sources/foreign/source.gscp'))
    change('packet-digest', lambda v: v.update(packetSha256='00'*32))
    change('packet-bytes', lambda v: v.update(packetBytes=v['packetBytes']+1))
    change('retained-scratch', lambda v: v.update(scratchAbsent=False))
    change('missing-authority', lambda v: v['authorityBefore'].pop())
    change('changed-authority', lambda v: v['authorityAfter'][0].update(sha256='ff'*32))
    change('duplicate-authority', lambda v: v['authorityAfter'].append(v['authorityAfter'][0]))
    change('missing-close', lambda v: v['states'].pop())
    change('reordered-states', lambda v: v['states'].reverse())
    change('eighth-image', lambda v: v['states'][1]['usage']['counts'].update(APPLICATION=8))
    change('borrowed-source-category', lambda v: v['states'][1]['usage']['counts'].update(SOURCE=6))
    change('uncharged-packet', lambda v: v['states'][1]['usage'].update(staging=v['states'][0]['usage']['staging']))
    change('uncharged-records', lambda v: v['states'][1]['usage'].update(queued=0))
    change('leaked-close', lambda v: v['states'][2]['usage'].update(leases=17))
    change('boolean-leases', lambda v: v['states'][0]['usage'].update(leases=True))
    e.need(tuple(name for name, _ in changes) == NEGATIVE_NAMES, 'maximum transition negative catalogue')
    result = []
    for name, value in changes:
        try: receiver(value, files, extent)
        except ValueError as error:
            e.need(str(error) == 'maximum transition exact receiver refusal', 'maximum transition unrelated negative: '+name)
        else: raise ValueError('maximum transition accepted mutation: '+name)
        result.append(dict(case=name, status='REJECTED', reason='maximum transition exact receiver refusal'))
    return result


def qualify(root, mode='maximum'):
    result, expected = _validate(root, mode)  # Entire original before any mutation.
    original = read(Path(root) / 'receiver.json')
    negatives = receiver_negatives(original, expected, result['imageBytes'])
    return dict(result, negativeCases=negatives, negativeScope='original-first-receiver-components')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.qualify else validate)(
        args.root, 'diagnostic' if args.diagnostic else 'maximum'), sort_keys=True))
