"""Physical and process-observation checks for a whole-group carried restart.

This component returns PARTIAL: original TCP transfer/state replay and final
source-bound cohort admission are separate, still required obligations.
"""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from . import native_carried_recovery_evidence as physical
from . import node_process_evidence as process
from . import discovered_selection_evidence as selection
from . import native_retirement_evidence as retirement

b, c, d, e, f, need = physical.b, physical.c, physical.d, physical.e, physical.f, physical.need
NODES, CUTS = physical.NODES, physical.CUTS


def read(path):
    return json.loads(b.t.plans.read(path, 32*e.MIB))


def exact(actual, expected, reason):
    need(f.canonical(actual) == f.canonical(expected), reason)


def inventory(root):
    selection.inventory(root)
    names = {'original-plan.gsbp', 'original-application.image', 'initial', 'calls.json',
        'entry-1.gsr', 'payload-1.bin', 'carried-kind.txt', 'carried-phase.txt', 'old-applied',
        'before-network', 'at-cut', 'before-reopen', 'after-close', 'events.json', 'wire.json',
        'ready.gsr', 'process', 'life-2-ready'}
    names |= {'round-1-'+v for v in ('prepared','selected','installed','settled')}
    names |= {'slot-1-'+v for v in ('accepted','proved','certified')}
    names |= {f'life-{life}-{v}' for life in (1,2) for v in ('opened','installed-1','installed-1.gsr')}
    names |= {f'life-2-{v}-{slot}' for v in ('applied','published') for slot in (1,2)}
    b.selection.layout(root, names, 'native carried process inventory')
    b.selection.layout(root/'process', {'spec.json','result.json'} |
        {f'life-{i}.{s}' for i in (1,2) for s in ('jsonl','stderr')}, 'native carried child inventory')
    need((root/'carried-kind.txt').read_bytes() == b'DATA' and
         (root/'carried-phase.txt').read_bytes() == b'APPLIED', 'native carried original markers')


def children(result, *, kind='DATA'):
    need(kind in ('DATA','INTENT','FINAL'), 'native carried exact command kind')
    need(type(result) is dict and set(result) == {'status','producerPassed','phase3Complete','mode','cut',
        'oldPhase','carriedKind','children','clientCalls','powerLoss'} and result['mode'] in ('halt','kill')
        and result['cut'] in CUTS, 'native carried producer scope')
    expected = dict(result, status='PARTIAL', producerPassed=True, phase3Complete=False,
                    oldPhase='APPLIED' if kind=='DATA' else 'ACCEPTED', carriedKind=kind, clientCalls=0, powerLoss=False)
    exact(result, expected, 'native carried producer scope')
    rows = result['children']
    need(type(rows) is list and len(rows) == 2 and all(type(v) is dict for v in rows), 'native carried child pair')
    need(all(type(v.get('pid')) is int and v['pid'] > 0 for v in rows) and rows[0]['pid'] != rows[1]['pid'],
         'native carried fresh child identities')
    for life, row in enumerate(rows, 1):
        expected = dict(life=life, pid=row['pid'], opened=True,
            started=dict(life=life,pid=row['pid'],mode=result['mode'],cut=result['cut']),
            exit=(73 if result['mode']=='halt' else 137) if life==1 else 0)
        if life == 1:
            expected.update(allLocksHeldBeforeDeath=True, allLocksReleasedAfterDeath=True)
        else:
            closed = row.get('closed')
            need(type(closed) is dict and type(closed.get('elapsedNanos')) is int and closed['elapsedNanos'] > 0,
                 'native carried measured successor lifetime')
            expected['closed'] = dict(life=2,elapsedNanos=closed['elapsedNanos'],clientCalls=0)
        exact(row, expected, 'native carried exact death and close')
    return rows


def configuration(root):
    plan = b.t.plans.decode((root/'original-plan.gsbp').read_bytes(),
                           (root/'original-application.image').read_bytes(), details=True)
    paths = [v['path'] for v in plan['plan']['descriptor']['paths']]
    spec = read(root/'process/spec.json')
    need(type(spec) is dict and set(spec) == {'nodes'} and type(spec['nodes']) is list and len(spec['nodes']) == 3,
         'native carried original disk paths')
    scratch = []
    for i, row in enumerate(spec['nodes']):
        need(type(row) is dict and set(row) == {'replica','application','scratch'} and
             row['replica'] == paths[1+2*i] and row['application'] == paths[2+2*i] and type(row['scratch']) is str,
             'native carried original disk paths')
        path = PurePosixPath(row['scratch'])
        need(path.is_absolute() and '..' not in path.parts and str(path) == row['scratch'] and
             all(not path.is_relative_to(v) and not PurePosixPath(v).is_relative_to(path) for v in paths+scratch),
             'native carried disjoint scratch')
        scratch.append(row['scratch'])


def observations(root, result, rows):
    events, wire, counts, lifetimes = [], [], [], []
    for life, row in enumerate(rows, 1):
        need((root/f'process/life-{life}.stderr').read_bytes() == b'', 'native carried child stderr')
        messages = process.transcript(root/f'process/life-{life}.jsonl')
        exact(messages[0], dict(action='started',value=row['started']), 'native carried original child start')
        ending = dict(action='cut',value=dict(name=result['cut'],mode=result['mode'],pid=row['pid'])) if life==1 else dict(action='closed',value=row['closed'])
        exact(messages[-1], ending, 'native carried child terminal boundary')
        actual, snapshots, opened, ready = [], [], 0, 0
        for message in messages[1:-1]:
            action, value = message['action'], message['value']
            if action == 'event':
                unnumbered = type(value) is dict and value.get('event') in ('FUTURE_QUORUM_COMPLETE','PUBLICATION_SEND_BOUNDARY')
                need(type(value) is dict and value.get('node') in NODES and type(value.get('event')) is str and
                     ((unnumbered and 'incarnation' not in value and life==2) or
                      (not unnumbered and type(value.get('incarnation')) is int and value['incarnation']==life)),
                     'native carried event lifetime')
                actual.append(value)
            elif action == 'response':
                need(type(value) is dict and set(value)=={'event','wire'} and type(value['wire']) is dict and
                     set(value['wire'])=={'request','response','withheld'} and value['wire']['withheld'] is False,
                     'native carried response shape')
                request, response = [base64.b64decode(value['wire'][k],validate=True) for k in ('request','response')]
                event = value['event']
                need(type(event) is dict and event.get('node') in NODES, 'native carried response owner')
                exact(event,dict(node=event['node'],incarnation=life,event='WIRE_RESPONSE',
                    request=e.digest(request),response=e.digest(response)), 'native carried response digest')
                actual.append(event); wire.append(value['wire'])
            elif action == 'opened':
                exact(value,life,'native carried opened lifetime'); opened += 1
                opens = [v for v in actual if v['event']=='NODE_OPEN']
                need([v['node'] for v in opens] == list(NODES) and actual[-1] == opens[-1]
                     and not any(v['event'].startswith(('ROUND_','NETWORK_')) for v in actual),
                     'native carried all owners open before campaign')
                for v in opens:
                    need(set(v)=={'node','incarnation','event','counts'} and type(v['counts']) is dict and
                         all(type(k) is str and type(n) is int and n>=0 for k,n in v['counts'].items()),
                         'native carried observed resource counts')
            elif action == 'installed':
                exact(value,dict(life=life,number=1,bytes=base64.b64encode(
                    (root/f'life-{life}-installed-1.gsr').read_bytes()).decode()), 'native carried installed observation')
                need(opened == 1 and actual[-1]['event']=='ROUND_INSTALLED', 'native carried installed boundary')
                snapshots.append(f'life-{life}-installed-1')
            elif action == 'snapshot':
                need(type(value) is str, 'native carried snapshot name'); snapshots.append(value)
            elif action == 'ready':
                need(life==2 and ready==0 and snapshots and snapshots[-1]=='life-2-ready', 'native carried readiness lifetime')
                exact(value,base64.b64encode((root/'ready.gsr').read_bytes()).decode(),'native carried readiness observation')
                ready += 1
            else: raise ValueError('native carried unexpected child action')
        expected = [f'life-{life}-installed-1']
        if life==2: expected += [f'life-2-{kind}-{slot}' for slot in (1,2) for kind in ('applied','published')]+['life-2-ready']
        need(opened==1 and ready==life-1 and snapshots==expected, 'native carried exact child snapshots')
        need([v['node'] for v in actual if v['event']=='NODE_OPEN']==list(NODES), 'native carried unique owner opens')
        events.extend(actual); lifetimes.append(actual); counts.append(len(messages))
        if life==1: events.append(dict(event='GROUP_CRASH',incarnation=1))
    exact(read(root/'events.json'),events,'native carried merged lifetime events')
    exact(read(root/'wire.json'),wire,'native carried complete response inventory')
    return lifetimes, counts


def ordered(names, expected, reason):
    # Each required milestone occurs exactly once in this bounded operation.
    need([v for v in names if v in expected] == expected, reason)


def vote_order(names, phase, *, renamed=False):
    expected = [phase+'_'+v for v in ('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
        'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED')]
    if not renamed: expected += [phase+'_PARENT_FORCED',phase+'_BEFORE_RETURN']
    observed = [v for v in names if v.startswith(phase+'_') and v not in
                (phase+'_ACTIVE_FORCED',phase+'_ACTIVE_PARENT_FORCED',phase+'_ACK_BEFORE_RETURN')]
    need(observed==expected,'native carried exact '+phase+' force prefix')


def cleanup_order(names, files, *, interrupted=False):
    if 'applied-end' not in files:
        need(not any(v.startswith(('STAGED_','SUPERSEDED_','NATIVE_RETIREMENT_')) for v in names),
             'native carried unexpected cleanup')
        return
    marker = retirement.authority(files)
    _, expected = physical.staging.cleanup(files,marker)
    retirement.order(names, [] if interrupted else expected, True)


def original_forces(root):
    calls = read(root/'calls.json')
    need(type(calls) is list and len(calls)<256 and all(type(v) is dict and set(v)=={'node','operation','events'}
         and v['node'] in NODES and type(v['operation']) is str and type(v['events']) is list
         and all(type(s) is str for s in v['events']) for v in calls), 'native carried original calls')
    for operation, phase in (('accept-1','ACCEPT'),('proof-1','PROOF'),('certificate-1','CERTIFICATE'),('old-apply',None)):
        rows = [v for v in calls if v['operation']==operation]
        need([v['node'] for v in rows]==list(NODES), 'native carried original phased owners')
        for row in rows:
            if phase:
                names=row['events']
                if phase=='ACCEPT':
                    # The original fixture invokes the same acceptance twice;
                    # the second returns the existing vote without a new write.
                    need(names[-2:]==['ACCEPT_BEFORE_RETURN']*2,'native carried original idempotent accept')
                    names=names[:-1]
                vote_order(names,phase)
            else: retirement.native.native_order(row['events'],1)


def rounds(root, lives):
    original = (root/'entry-1.gsr').read_bytes()
    boundaries = []
    for life, events in enumerate(lives,1):
        found = [(i,v) for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
        expected = ['ROUND_INSTALLED','ROUND_SLOT_BEGIN'] if life==1 else [
            'ROUND_INSTALLED','ROUND_SLOT_BEGIN','ROUND_SLOT_COMPLETE','ROUND_SLOT_BEGIN','ROUND_SLOT_COMPLETE','ROUND_BEFORE_READY']
        need([v['event'] for _,v in found]==expected, 'native carried round lifecycle')
        raw = []
        for _, row in found:
            need(set(row)=={'node','incarnation','event','record','bytes'} and row['node']=='node-1',
                 'native carried round owner')
            value = base64.b64decode(row['bytes'],validate=True)
            need(e.digest(value)==row['record'], 'native carried round digest'); raw.append(value)
        selected_raw = (root/f'life-{life}-installed-1.gsr').read_bytes()
        selected = f.decode(selected_raw,'records','SELECTED')
        need(raw[0]==selected_raw and raw[1]==original and selected['nextEntry']==e.digest(original)
             and selected['ballot']!=f.decode(original,'records','ENTRY')['origin'], 'native carried original round entry')
        if life==2:
            entry = f.decode(raw[3],'records','ENTRY')
            need(entry==dict(f.decode(original,'records','ENTRY'),index=2,previous=e.digest(original),
                 origin=selected['ballot'],kind='BARRIER',payload=e.digest(b'')), 'native carried fresh barrier')
            for slot, at in ((1,2),(2,4)):
                files=c.inventory(root/f'life-2-published-{slot}/node-1');prefix,_,packet=c.current(files)
                applied=c.inventory(root/f'life-2-applied-{slot}/node-1');own=d.future.identity(files)
                ack=f.decode(raw[at],'wire','PUBLISH_ACK')
                exact(ack,dict(root=selected['root'],view=selected['view'],ballot=selected['ballot'],sender=own,recipient=own,
                    trace=ack['trace'],sequence=1,payload=dict(certificate=e.digest(applied['applied-end/certificate.gsr']),
                    selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),
                    generation=e.digest(files[prefix+'generation.gsr']))),'native carried original completion')
                need(e.digest(raw[2*slot-1])==packet['capsule']['cut']['entry'],'native carried published original entry')
            need(raw[-1]==raw[-2] and (root/'ready.gsr').read_bytes()==raw[-1], 'native carried barrier readiness')
        boundaries.append([i for i,_ in found])
    return boundaries


def force_order(root, lives, boundaries, point):
    # All three owners die. Cold local transfer must finish before each NODE_OPEN;
    # no recovered vote can supply a new PROOF, application ACK or publication.
    interrupted=[v['event'] for v in lives[0][boundaries[0][1]+1:] if v['node']=='node-1']
    need(interrupted and interrupted[-1]==point,'native carried exact storage cut')
    if point!='APPLY_ACK_DIRECTORY_FORCED':
        need(not any(v.startswith(('CERTIFICATE_VALIDATED','APPLY_','PUBLICATION_')) for v in interrupted),
             'native carried interrupted application absent')
    for node in NODES:
        for life, events in enumerate(lives,1):
            stop=next(i for i,v in enumerate(events) if v['node']==node and v['event']=='NODE_OPEN')
            names=[v['event'] for v in events[:stop] if v['node']==node]
            files=c.inventory(root/('before-network' if life==1 else 'before-reopen')/node)
            frames,phases=physical.pending(files)
            transferred=frames['SELECTOR']!=files['selector.gsr']
            active=phases[-1] if phases else 'ACCEPT'
            pair=[active+'_ACTIVE_FORCED',active+'_ACTIVE_PARENT_FORCED']
            need([v for v in names if v in pair]==pair*(2 if transferred and 'applied-end' in files else 1),
                 'native carried cold vote force')
            if transferred:
                end=names.index('ACCEPT_VALIDATED');cleanup_order(names[:end],files)
                vote_order(names[end:],'ACCEPT')
            need(not any(v.startswith(('PROOF_VALIDATED','CERTIFICATE_VALIDATED','APPLY_','PUBLICATION_')) for v in names),
                 'native carried cold acceptance only')
    for life, (events, indices) in enumerate(zip(lives,boundaries),1):
        selected=f.decode((root/f'life-{life}-installed-1.gsr').read_bytes(),'records','SELECTED')
        voters=tuple(v['voter'] for v in selected['sources'])
        segments=[(indices[1],len(events),1)] if life==1 else [(indices[1],indices[2],1),(indices[3],indices[4],2)]
        for start,stop,slot in segments:
            for node in voters:
                names=[v['event'] for v in events[start+1:stop] if v['node']==node]
                if life==1 and point==CUTS[0]:
                    if node=='node-1':
                        cleanup_order(names,c.inventory(root/'life-1-installed-1'/node),interrupted=True)
                        need(names[-1]==point,'native carried exact storage cut')
                    else: need(not names,'native carried peer before interrupted cleanup')
                    continue
                if life==1 and point=='ACCEPT_RENAMED' and node!='node-1':
                    need(not names,'native carried peer before interrupted accept');continue
                if slot==1:
                    end=names.index('ACCEPT_VALIDATED')
                    cleanup_order(names[:end],c.inventory(root/f'life-{life}-installed-1'/node))
                vote_order(names,'ACCEPT',renamed=life==1 and point=='ACCEPT_RENAMED')
                if life==1 and point=='ACCEPT_RENAMED': continue
                if life==1 and point=='PROOF_RENAMED' and node!='node-1':
                    need(not any(v.startswith(('PROOF_','CERTIFICATE_VALIDATED','APPLY_')) for v in names),
                         'native carried peer proof not dispatched');continue
                vote_order(names,'PROOF',renamed=life==1 and point=='PROOF_RENAMED')
                floor=names.index('FLOOR_PARENT_FORCED');accept=names.index('ACCEPT_PARENT_FORCED');proof=names.index('PROOF_VALIDATED')
                if slot==1: need(accept<floor<proof,'native carried transferred vote before floor')
                if life==1 and point=='PROOF_RENAMED': continue
                if life==1 and node!='node-1':
                    need(not any(v.startswith(('CERTIFICATE_VALIDATED','APPLY_','PUBLICATION_')) for v in names),
                         'native carried peer application not dispatched');continue
                vote_order(names,'CERTIFICATE')
                application=['NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED','APPLY_ACK_DIRECTORY_FORCED']
                if life==2: application += ['APPLY_BEFORE_RETURN','PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN']
                # Publication ACK can be replayed on the wire; retain its first
                # actual completion without treating duplicates as applications.
                canonical=names[:names.index('PUBLICATION_ACK_BEFORE_RETURN')+1] if life==2 else names
                ordered(canonical,application,'native carried application/publication order')
                if life==1: need(names[-1]==point,'native carried exact storage cut')


def validate(root):
    root=Path(root);inventory(root)
    result=read(root/'process/result.json')
    need(type(result) is dict, 'native carried producer scope');point=result.get('cut')
    # Storage is independently reduced before process success claims are read.
    reduced=physical.physical(root,point)
    configuration(root);rows=children(result);original_forces(root)
    lives,counts=observations(root,result,rows);boundaries=rounds(root,lives)
    force_order(root,lives,boundaries,point)
    return dict(status='PARTIAL',scope='native-carried-whole-group-physical-and-process',
        componentChecks='PASS',originalFirst=True,mode=result['mode'],cut=point,
        freshGroupJvms=2,survivingOriginalOwners=0,childMessages=counts,clientCalls=0,
        physical=reduced,processObservations=True,fullWireReplay=False,
        processHistoryQualified=False,cohortAdmitted=False,powerLoss=False,phase3Complete=False)


NEGATIVES = {
    'unexpected-file': 'context selection native carried process inventory inventory',
    'wrong-marker': 'native carried original markers',
    'changed-entry': 'carried original entry/payload',
    'changed-payload': 'carried original entry/payload',
    'changed-old-certificate': 'admitted exact old-applied: node-1',
    'changed-source': 'admitted exact life-1-installed-1: node-1',
    'changed-interrupted-vote': 'admitted exact at-cut: node-1',
    'changed-cold-vote': 'admitted exact life-2-opened: node-1',
    'changed-final-selector': 'admitted exact after-close: node-1',
    'claimed-complete': 'native carried producer scope',
    'reused-pid': 'native carried fresh child identities',
    'wrong-exit': 'native carried exact death and close',
    'missing-lock-probe': 'native carried exact death and close',
    'invented-client-retry': 'native carried exact death and close',
    'wrong-disk': 'native carried original disk paths',
    'shared-scratch': 'native carried disjoint scratch',
    'child-error': 'native carried child stderr',
    'truncated-transcript': 'node process complete bounded transcript',
    'missing-child-send': 'native carried merged lifetime events',
    'missing-wire-response': 'native carried complete response inventory',
    'changed-response-digest': 'native carried response digest',
    'missing-group-crash': 'native carried merged lifetime events',
    'wrong-event-lifetime': 'native carried event lifetime',
    'missing-original-force': 'native carried exact PROOF force prefix',
    'missing-cold-force': 'native carried cold vote force',
    'invented-cold-ack': 'native carried cold acceptance only',
    'missing-accept-force': 'native carried exact ACCEPT force prefix',
    'missing-application-force': 'native carried application/publication order',
    'missing-retirement-force': 'native retirement exact force/delete order',
    'changed-carried-round': 'native carried original round entry',
    'missing-fresh-barrier': 'native carried round lifecycle',
    'stale-readiness': 'native carried barrier readiness',
}


def negative_cases(point):
    need(point in CUTS,'native carried declared negative cut')
    cases=dict(NEGATIVES)
    if point in ('ACCEPT_RENAMED','PROOF_RENAMED'):
        cases['invented-rename-parent-force']='native carried exact storage cut'
    return cases


def write_messages(path, messages):
    path.write_bytes(b'\n'.join(f.canonical(v) for v in messages)+b'\n')


def rewrite_lives(root, edit):
    """Change both retained views, so ordering negatives cannot pass on mismatch."""
    lives=[process.transcript(root/f'process/life-{i}.jsonl') for i in (1,2)]
    edit(lives)
    events=[];wire=[]
    for life,messages in enumerate(lives,1):
        write_messages(root/f'process/life-{life}.jsonl',messages)
        for m in messages:
            if m['action']=='event':events.append(m['value'])
            elif m['action']=='response':events.append(m['value']['event']);wire.append(m['value']['wire'])
        if life==1:events.append(dict(event='GROUP_CRASH',incarnation=1))
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wire))


def mutate(root, name):
    files={'changed-entry':'entry-1.gsr','changed-payload':'payload-1.bin',
        'changed-old-certificate':'old-applied/node-1/applied-end/certificate.gsr',
        'changed-interrupted-vote':'at-cut/node-1/pending.accept',
        'changed-cold-vote':'life-2-opened/node-1/pending.accept',
        'changed-final-selector':'after-close/node-1/selector.gsr'}
    if name in files:(root/files[name]).write_bytes(b'changed');return
    if name=='unexpected-file':(root/'unexpected.txt').write_text('extra');return
    if name=='wrong-marker':(root/'carried-kind.txt').write_text('BARRIER');return
    if name=='changed-source':
        path=root/'life-1-installed-1/node-1';files=c.inventory(path)
        _,members,_=c.current(files);basis=f.decode(members['basis.gsr'],'records','BASIS')
        (path/'sources'/basis['basisId']/'source.gscp').write_bytes(b'changed');return
    if name in ('claimed-complete','reused-pid','wrong-exit','missing-lock-probe','invented-client-retry'):
        path=root/'process/result.json';r=read(path)
        if name=='claimed-complete':r['phase3Complete']=True
        elif name=='reused-pid':r['children'][1]['pid']=r['children'][0]['pid']
        elif name=='wrong-exit':r['children'][0]['exit']=0
        elif name=='missing-lock-probe':del r['children'][0]['allLocksReleasedAfterDeath']
        else:r['children'][1]['closed']['clientCalls']=1
        path.write_bytes(f.canonical(r));return
    if name in ('wrong-disk','shared-scratch'):
        path=root/'process/spec.json';r=read(path)
        if name=='wrong-disk':r['nodes'][0]['replica']+='-copy'
        else:r['nodes'][1]['scratch']=r['nodes'][0]['scratch']
        path.write_bytes(f.canonical(r));return
    if name=='child-error':(root/'process/life-2.stderr').write_text('failure\n');return
    if name=='truncated-transcript':
        path=root/'process/life-1.jsonl';path.write_bytes(path.read_bytes()[:-1]);return
    if name in ('missing-child-send','changed-response-digest'):
        path=root/'process/life-1.jsonl';messages=process.transcript(path)
        if name=='missing-child-send':messages.remove(next(v for v in messages if v['action']=='event' and v['value']['event']=='NETWORK_SEND'))
        else:next(v for v in messages if v['action']=='response')['value']['event']['response']='0'*64
        write_messages(path,messages);return
    if name in ('missing-wire-response','missing-group-crash'):
        path=root/('wire.json' if name=='missing-wire-response' else 'events.json');r=read(path)
        if name=='missing-wire-response':r.pop()
        else:r.remove(next(v for v in r if v['event']=='GROUP_CRASH'))
        path.write_bytes(f.canonical(r));return
    if name=='missing-original-force':
        path=root/'calls.json';r=read(path)
        next(v for v in r if v['operation']=='proof-1' and v['node']=='node-1')['events'].remove('PROOF_PARENT_FORCED')
        path.write_bytes(f.canonical(r));return
    def edit(lives):
        def event(messages, label):
            return next(v for v in messages if v['action']=='event' and v['value']['node']=='node-1' and v['value']['event']==label)
        second=lives[1]
        if name=='wrong-event-lifetime':event(second,'NODE_OPEN')['value']['incarnation']=1
        elif name=='missing-cold-force':
            v=next(v for v in second if v['action']=='event' and v['value']['node']=='node-1' and
                   v['value']['event'] in ('ACCEPT_ACTIVE_PARENT_FORCED','PROOF_ACTIVE_PARENT_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED'))
            second.remove(v)
        elif name=='invented-cold-ack':second.insert(second.index(event(second,'NODE_OPEN')),
            dict(action='event',value=dict(node='node-1',incarnation=2,event='APPLY_ACK_DIRECTORY_FORCED')))
        elif name in ('missing-accept-force','missing-application-force'):
            start=second.index(event(second,'ROUND_SLOT_BEGIN'))
            label='ACCEPT_PARENT_FORCED' if name=='missing-accept-force' else 'APPLY_ACK_DIRECTORY_FORCED'
            second.remove(event(second[start:],label))
        elif name=='missing-retirement-force':
            for messages in lives:
                found=[v for v in messages if v['action']=='event' and v['value']['node']=='node-1' and v['value']['event']=='SUPERSEDED_END_AUTHORITY_FORCED']
                if found:messages.remove(found[0]);break
            else:raise ValueError('native carried mutation requires original retirement')
        elif name=='changed-carried-round':
            row=event(second,'ROUND_SLOT_BEGIN')['value'];body=f.decode(base64.b64decode(row['bytes']),'records','ENTRY')
            body['origin']['counter']+=1;raw=f.encode('records','ENTRY',body)
            row.update(bytes=base64.b64encode(raw).decode(),record=e.digest(raw))
        elif name=='missing-fresh-barrier':
            rows=[v for v in second if v['action']=='event' and v['value']['event']=='ROUND_SLOT_BEGIN'];second.remove(rows[-1])
        elif name=='stale-readiness':
            row=event(second,'ROUND_SLOT_COMPLETE')['value'];raw=base64.b64decode(row['bytes'])
            event(second,'ROUND_BEFORE_READY')['value'].update(bytes=row['bytes'],record=row['record'])
            next(v for v in second if v['action']=='ready')['value']=row['bytes'];(root/'ready.gsr').write_bytes(raw)
        elif name=='invented-rename-parent-force':
            point=read(root/'process/result.json')['cut'];need(point in ('ACCEPT_RENAMED','PROOF_RENAMED'),'native carried rename mutation scope')
            lives[0].insert(-1,dict(action='event',value=dict(node='node-1',incarnation=1,event=point.replace('RENAMED','PARENT_FORCED'))))
        else:raise ValueError('unknown native carried process mutation '+name)
    rewrite_lives(root,edit)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in negative_cases(original['cut']).items():
        with tempfile.TemporaryDirectory(prefix='v53-native-carried-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'native carried unrelated negative '+name+': '+str(error))
            else:raise ValueError('native carried accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
