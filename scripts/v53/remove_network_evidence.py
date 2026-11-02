"""REMOVE original attempted transport, grants, installation and slot ACKs.

First derive every physical snapshot. Complete byte-transfer causality and
original durable replies do not yet establish every export's temporal authority,
all maintenance callbacks, or a process-fault matrix.
"""
import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import transition_round_evidence as original
from . import joining_transcript as transcript
from . import joining_network_evidence as shared
from . import joining_phase_evidence as phase
from . import joining_history_run as collection
from . import joining_profile_network_evidence as profile_network

c,d,e,f,need=original.c,original.d,original.e,original.f,original.need
sha=e.digest


class History:
    """Only constructed after the original physical/lifecycle gate passes."""
    joining=None

    def __init__(self,root,profile):
        self.root=Path(root);self.old=tuple('node-'+str(i+1) for i in range(int(profile[0])))
        self.phases=[];self.states=[None];self.applied={};self.published={};self.installed={}
        for ordinal in range(1,4):
            index=ordinal+4;selected=(self.root/f'selected-{ordinal}.gsr').read_bytes()
            selection=f.decode(selected,'records','SELECTED');voters=[v['voter'] for v in selection['sources']]
            for node in voters:
                self.installed[ordinal,node]=c.inventory(self.root/f'installed-{ordinal}'/node)
                self.applied[ordinal,node]=c.inventory(self.root/f'applied-{index}'/node)
                self.published[ordinal,node]=c.inventory(self.root/f'published-{index}'/node)
            end=self.applied[ordinal,'node-1'];certificate=end['applied-end/certificate.gsr']
            cert=f.decode(certificate,'records','CERTIFICATE');proof=f.encode('records','PROOF',{k:v for k,v in cert.items() if k!='proofs'})
            accept=f.encode('records','ACCEPT',{k:v for k,v in cert.items() if k not in ('proofs','accepts')})
            self.phases.append(dict(SELECTED=selected,ENTRY=(self.root/f'native-entry-{index}.gsr').read_bytes(),
                ACCEPT=accept,PROOF=proof,CERTIFICATE=certificate))
            packet=c.current(self.published[ordinal,'node-1'])[2]
            self.states.append(f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG'))

    def owner(self,stage,index,node):return (self.applied if stage=='applied' else self.published)[index,node]

    def future_lower(self,index,target):
        state=d.s.r.decode(self.applied[index,'node-1'][d.s.FILE])
        return next(v['possible'][0] for v in state['plan']['peers'] if v['identity']['node']==target)


def activations(events,rows,history):
    used=set();grants=installations=0;prior=-1;capture_callbacks=set();journal_bounds=[]
    for ordinal,parts in enumerate(history.phases,1):
        raw=parts['SELECTED'];selected=f.decode(raw,'records','SELECTED');digest=sha(raw)
        voters=[v['voter'] for v in selected['sources']];proposer=selected['ballot']['proposer']
        ends=[i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED' and v['record']==digest]
        need(len(ends)==1 and prior<ends[0],'REMOVE network activation lifetime');end=ends[0]
        positions={};members={};grant_returns={}
        for node in voters:
            files=history.installed[ordinal,node];members[node]=c.current(files)[1];own=members[node]
            need(own['selected.gsr']==raw,'REMOVE network original selection')
            basis=f.decode(own['basis.gsr'],'records','BASIS')
            need(dict(voter=node,basisId=basis['basisId'],basisDigest=sha(own['basis.gsr'])) in selected['sources'],
                 'REMOVE network original selected basis')
            def positions_of(point):return [i for i,v in enumerate(events) if prior<i<end and v['node']==node and v['event']==point]
            starts,returns,selections=positions_of('CURRENT_BEFORE_CAPTURE'),positions_of('GRANT_BEFORE_RETURN'),positions_of('SELECTED_FORCED')
            need(len(starts)==len(returns)==len(selections)==1 and starts[0]<returns[0]<selections[0],
                 'REMOVE network complete original grants')
            packet=c.p.decode(files['sources/'+basis['basisId']+'/source.gscp'])
            try:
                bound=shared.grant_capture_order(events,node,None,starts[0],returns[0],packet)
            except ValueError as error:
                raise ValueError('REMOVE network durable grant order') from error
            need(not capture_callbacks.intersection(bound),'REMOVE network reused grant capture callback')
            capture_callbacks.update(bound)
            positions[node]=(starts[0],returns[0],selections[0]);grant_returns[node]=returns[0];grants+=1
        prepare=[];propagation=[];promises=[]
        for row in rows:
            if row['kind'] not in ('PREPARE','SELECTED') or row['request']['ballot']!=selected['ballot']:continue
            q,a=row['request'],row['response'];node=q['recipient']['node'];own=members.get(node)
            need(q['sender']['node']==proposer and node in voters and node!=proposer and q['view']==selected['view'] and
                 q['sequence']==voters.index(node)+(len(voters)-1 if row['kind']=='SELECTED' else 0),
                 'REMOVE network activation authority')
            if row['kind']=='PREPARE':
                need(row['answer']=='PROMISE' and q['payload']==dict(promise=sha(members[proposer]['promise.gsr'])) and
                     a['payload']==dict(basis=sha(own['basis.gsr'])),'REMOVE network prepare authority')
                start,returned,forced=positions[node]
                need(grant_returns[proposer]<row['sent']<row['received']<start<returned<row['offered']<row['delivered']<positions[proposer][2],
                     'REMOVE network grant before delivered promise')
                prepare.append(node);promises.append(row['delivered'])
            else:
                need(row['answer']=='INSTALL_ACK' and q['payload']==dict(selection=digest) and
                     a['payload']==dict(selection=digest,cut=selected['cut']),'REMOVE network installation authority')
                need(positions[proposer][2]<row['sent']<row['received']<positions[node][2]<row['offered']<row['delivered']<end,
                     'REMOVE network selected propagation order')
                shared.install.interval(events,node,None,row['received'],row['offered'],own,
                    ['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],'REMOVE network durable installation order')
                propagation.append(row);installations+=1
            used.add(row['offered'])
        need(sorted(prepare)==sorted(v for v in voters if v!=proposer) and
             sorted(v['request']['recipient']['node'] for v in propagation)==sorted(prepare),'REMOVE network complete peer activation')
        shared.proposer_forces(events,proposer,None,positions[proposer][2],end,propagation,members[proposer])
        for node in voters:
            if node==proposer:
                lower=max([*grant_returns.values(),*promises]);upper=min(v['sent'] for v in propagation)
            else:
                reply=next(v for v in propagation if v['request']['recipient']['node']==node)
                lower,upper=reply['received'],reply['offered']
            journal_bounds.append(dict(node=node,scope=None,selection=digest,forced=positions[node][2],lower=lower,upper=upper))
        prior=end
    need(used=={v['offered'] for v in rows if v['kind'] in ('PREPARE','SELECTED')},'REMOVE network unbound activation')
    need(sum(v['event']=='GRANT_BEFORE_RETURN' for v in events)==grants and
         sum(v['event']=='SELECTED_FORCED' for v in events)==grants,'REMOVE network unexplained grant/selection')
    need(capture_callbacks=={i for i,v in enumerate(events) if shared.capture_callback(v['event'])},
         'REMOVE network unbound grant capture callback')
    shared.selection_journal.validate(events,journal_bounds)
    return dict(originalGrants=grants,boundInstallReplies=installations,proposerInstallations=len(history.phases))


def statuses(rows,history,physical):
    count=0
    for row in rows:
        if row['kind']!='STATUS_PROBE':continue
        q,a=row['request'],row['response'];node=q['recipient']['node']
        prior=c.current(c.inventory(history.root/'before-network'/node))[2]['capsule']['cut']
        possibilities=[];since=-1
        for ordinal in range(1,4):
            if (ordinal,node) not in physical:continue
            times=physical[ordinal,node]
            if since<=row['offered'] and row['received']<=times['PUBLICATION_BEFORE_RETURN']:possibilities.append(prior)
            since=times['PUBLICATION_SELECTOR_FORCED']
            prior=c.current(history.published[ordinal,node])[2]['capsule']['cut']
        if since<=row['offered']:possibilities.append(prior)
        need(row['answer']=='STATUS' and set(q['payload'])=={'nonce'} and
             a['payload']==dict(nonce=q['payload']['nonce'],cut=a['payload'].get('cut'),ready=False) and
             a['payload']['cut'] in possibilities,'REMOVE network original status window')
        count+=1
    return dict(boundStatusReplies=count)


def future_request_matches(kind,q,selected,intent):
    proposer=selected['ballot']['proposer'];node=q['recipient']['node']
    peers=sorted(set(selected['cut']['view']['old']+selected['cut']['view']['new'])-{proposer})
    # The local durable vote is sequence 1; each remote voter receives its own
    # sequence in the producer's sorted governing-voter order.
    return (kind=='FUTURE_RETENTION_INTENT' and q['payload']==intent and q['ballot']==selected['ballot'] and
        q['view']==selected['view'] and q['sender']['node']==proposer and node in peers and
        q['sequence']==peers.index(node)+2)


def bounded_attempts(events):
    # Count sends, including success after failure. Separate success/failure
    # counters would incorrectly permit three of each for one request.
    need(all(count<=3 for count in Counter(v['request'] for v in events if v['event'] in transcript.SENDS).values()),
         'REMOVE network bounded total attempts')


def failed_controls(root,events,failed,history,rows=(),physical=None):
    diagnostics=collection.read_json(Path(root),'failures.json',collection.EVENT_BYTES)
    need(all(type(v) is dict and set(v)=={'node','kind','request','failure'} and
             type(v['failure']) is str and 0<len(v['failure'])<=8192 for v in diagnostics),'REMOVE network failure diagnostic shape')
    expected=Counter((v['recipient'],v['kind'],v['requestHash']) for v in failed if v['serverFailed'] is not None)
    need(Counter((v['node'],v['kind'],v['request']) for v in diagnostics)==expected,'REMOVE network complete failure diagnostics')
    need(all(count<=3 for count in Counter(v['requestHash'] for v in failed).values()),'REMOVE network bounded failed attempts')
    for value in failed:
        kind,q=transcript.wire(events[value['sent']]['bytes']);matched=False
        for ordinal,parts in enumerate(history.phases,1):
            selected=f.decode(parts['SELECTED'],'records','SELECTED')
            parent=c.anchor(c.current(history.applied[ordinal,'node-1'])[2]['capsule'])
            upper=c.anchor(c.current(history.published[ordinal,'node-1'])[2]['capsule'])
            voters=[v['voter'] for v in selected['sources']]
            for target in voters[1:]:
                identity=d.future.identity(history.applied[ordinal,target])
                intent=dict(selection=sha(parts['SELECTED']),certificate=sha(parts['CERTIFICATE']),peer=identity,
                    lower=history.future_lower(ordinal,target),parent=parent,upper=upper)
                if future_request_matches(kind,q,selected,intent):
                    successes=[r for r in rows if r['kind']==kind and r['request']['payload']==intent]
                    applied=max(physical[ordinal,node]['APPLY_BEFORE_RETURN'] for node in voters)
                    published=min(physical[ordinal,node]['PUBLICATION_VALIDATED'] for node in voters)
                    need(successes and all(r['request']['trace']==q['trace'] for r in successes) and
                         applied<value['sent']<published,'REMOVE network failed control quorum lifetime')
                    matched=True
        need(matched,'REMOVE network unbound failed control')
    return dict(boundFailedControls=len(failed))


def network(root,profile):
    history=History(root,profile)
    identities={n:d.future.identity(c.inventory(Path(root)/'before-network'/n)) for n in history.old}
    root_id=f.decode(history.phases[0]['SELECTED'],'records','SELECTED')['root']
    events=collection.read_json(Path(root),'events.json',collection.EVENT_BYTES)
    wires=collection.read_json(Path(root),'wire.json',collection.WIRE_BYTES)
    failed=[];rows=transcript.causal(events,wires,identities,root_id,failed=failed)
    bounded_attempts(events)
    need(all(v['kind'] in {'PREPARE','SELECTED','STATUS_PROBE','CHUNK','TRANSFER_COMMIT','ACCEPT','PROOF','APPLY','PUBLISH','FUTURE_RETENTION_INTENT'}
             for v in rows),'REMOVE network unknown exchange')
    result=transcript.transfers(rows)
    result.update(activations(events,rows,history))
    physical=phase.blocks(events,history)
    result.update(phase.phase_replay(events,rows,history,physical))
    result.update(statuses(rows,history,physical))
    result.update(failed_controls(root,events,failed,history,rows,physical))
    response_less=[v for v in failed if not v['withheldResponse']]
    result.update(wireExchanges=len(rows),sentRequests=len(rows)+len(response_less),
        receivedRequests=len(rows)+sum(v['received'] is not None for v in response_less),
        deliveredResponses=sum(v['delivered'] is not None for v in rows),failedAttempts=len(failed),
        terminalObservations=sum(1+(v['serverFailed'] is not None) for v in failed))
    shared.initial_current.validate(events,history.old)
    shared.current_lifecycle.remove(events,history.phases,history.old)
    return result


def validate(root,profile):
    need(profile in original.PROFILES,'REMOVE network profile');root=Path(root);before=collection.inventory(root)
    physical=original.validate(root,profile);result=network(root,profile)
    need(collection.inventory(root)==before,'REMOVE network original changed')
    return dict(status='PARTIAL',profile=profile,physical=physical,network=result,observedAttemptsQualified=True,
        durableActivationAndSlotACKsQualified=True,completeExportAuthorityQualified=False,
        maintenanceCompositionQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={k:v for k,v in shared.NEGATIVES.items() if k not in ('wrong-server-lifetime','wrong-client-lifetime') and
           k not in shared.current_lifecycle.JOINING_NEGATIVES}
NEGATIVES.update({k:v.replace('joining network','REMOVE network') for k,v in shared.GRANT_NEGATIVES.items()})
NEGATIVES.update({k:v.replace('joining network','REMOVE network') for k,v in shared.install.NEGATIVES.items()
                  if k.startswith('install-remote-')})
NEGATIVES.update({
    'missing-grant-force':'REMOVE network durable grant order',
    'early-promise':'REMOVE network grant before delivered promise',
    'wrong-promise-authority':'REMOVE network prepare authority',
    'wrong-prepare-view':'REMOVE network activation authority',
    'early-selection':'REMOVE network grant before delivered promise',
    'early-propagation':'REMOVE network selected propagation order',
    'missing-install-image-force':'REMOVE network durable installation order',
    'wrong-install-cut':'REMOVE network installation authority',
    'proposer-image-force':'joining network proposer complete installation order',
    'proposer-before-ack':'joining network proposer installation after ACKs',
    'wrong-status-cut':'REMOVE network original status window',
    'failure-diagnostic-missing':'REMOVE network complete failure diagnostics',
    'failed-control-unbound':'REMOVE network unbound failed control',
    'failed-control-sequence':'REMOVE network unbound failed control',
    'prepare-sequence':'REMOVE network activation authority',
    'selected-sequence':'REMOVE network activation authority',
    'failed-control-trace':'REMOVE network failed control quorum lifetime',
    'failed-control-over-attempts':'REMOVE network bounded total attempts',
})
NEGATIVES.update(profile_network.TERMINAL_NEGATIVES)
# These three one-slot control/edge publications have no extra parent/ancestor
# statement writes. The original applied member inventory still enforces that.
NEGATIVES.update({k:v for k,v in phase.slot_storage.NEGATIVES.items() if k not in ('slot-apply-parent-written','slot-apply-ancestor-written')})


def mutate(root,name):
    root=Path(root)
    if name in phase.slot_storage.NEGATIVES:
        events=d.read(root/'events.json');phase.slot_storage.mutate(events,name);(root/'events.json').write_bytes(f.canonical(events));return
    if name in shared.NEGATIVES or name in profile_network.TERMINAL_NEGATIVES:
        profile_network.mutate(root,name);return
    events=d.read(root/'events.json');wires=d.read(root/'wire.json');diagnostics=d.read(root/'failures.json')
    if name=='proposer-image-force':
        events.remove(next(v for v in events if v['node']=='node-1' and v['event']=='INSTALL_IMAGE_FORCED'))
    elif name=='proposer-before-ack':
        row=next(v for v in events if v['node']=='node-1' and v['event']=='INSTALL_RESERVED');events.remove(row)
        at=next(i for i,v in enumerate(events) if v['node']=='node-1' and v['event']=='NETWORK_RECEIVED' and v['kind']=='INSTALL_ACK')
        events.insert(at,row)
    elif name=='wrong-status-cut':
        row=next(v for v in wires if transcript.wire(v['request'])[0]=='STATUS_PROBE');kind,value=transcript.wire(row['response'])
        old=sha(base64.b64decode(row['response']));value['payload']['cut']['index']=999
        raw=f.encode('wire',kind,value);row['response']=base64.b64encode(raw).decode()
        for event in events:
            if event.get('response')==old:event['response']=sha(raw)
    elif name=='failure-diagnostic-missing':diagnostics.pop(0)
    elif name in ('prepare-sequence','selected-sequence'):
        row=next(v for v in wires if transcript.wire(v['request'])[0]==name.split('-')[0].upper())
        for side in ('request','response'):
            kind,value=transcript.wire(row[side]);old=sha(base64.b64decode(row[side]));value['sequence']+=1
            raw=f.encode('wire',kind,value);row[side]=base64.b64encode(raw).decode()
            for event in events:
                if event.get(side)==old:
                    event[side]=sha(raw)
                    if side=='request' and event['event'] in transcript.SENDS:event['bytes']=row[side]
    elif name=='failed-control-over-attempts':
        pair=profile_network.terminal_pair(root);need(pair is not None,'REMOVE negative requires original failure')
        caller=events[pair[1]];digest=caller['request']
        sends=[i for i,v in enumerate(events) if v['event'] in transcript.SENDS and v['request']==digest]
        first=sends[0];upper=next((i for i in sends if i>first),len(events))
        positions=[i for i in range(first,upper) if events[i].get('request')==digest]
        duplicate=[dict(events[i]) for i in positions]
        extra=4-len(sends);need(extra>0,'REMOVE negative original attempt bound')
        # Append a fully paired terminal attempt, so it reaches the bound
        # check rather than being rejected as an incomplete/overlapping retry.
        events.extend(duplicate*extra)
        diagnostic=next(v for v in diagnostics if v['request']==digest)
        diagnostics.extend(dict(diagnostic) for _ in range(extra))
    elif name in ('failed-control-unbound','failed-control-sequence','failed-control-trace'):
        terminal=next(v for v in events if v['event']=='NETWORK_ATTEMPT_FAILED' and v['direction']=='OUTBOUND')
        old=terminal['request'];send=next(v for v in events if v['event'] in transcript.SENDS and v['request']==old)
        kind,value=transcript.wire(send['bytes'])
        if name=='failed-control-unbound':value['payload']['certificate']='f'*64
        elif name=='failed-control-sequence':value['sequence']+=1
        else:value['trace']='00000000-0000-0000-0000-000000000001'
        raw=f.encode('wire',kind,value)
        for event in events:
            if event.get('request')==old:
                event['request']=sha(raw)
                if event['event'] in transcript.SENDS:event['bytes']=base64.b64encode(raw).decode()
        for row in diagnostics:
            if row['request']==old:row['request']=sha(raw)
    else:raise ValueError('REMOVE unknown network mutation: '+name)
    for name,values in [('events',events),('wire',wires),('failures',diagnostics)]:
        (root/(name+'.json')).write_bytes(f.canonical(values))


def qualify(root,profile):
    root=Path(root);passed=validate(root,profile);before=collection.inventory(root);outcomes=[]
    observation={'events.json','wire.json','failures.json'}
    physical={k:v for k,v in before['files'].items() if k not in observation}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-remove-network-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in observation}==physical and before['directories']==after['directories'],
                 'REMOVE network negative changed physical input')
            try:network(changed,profile)
            except ValueError as error:need(str(error)==reason,'REMOVE unrelated network negative: '+name+': '+str(error))
            else:raise ValueError('REMOVE network mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(profile=profile,case=name,completed=len(outcomes),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'REMOVE network negative changed original')
    return dict(original=passed,negatives=outcomes)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=original.PROFILES)
    p.add_argument('--qualify',action='store_true')
    a=p.parse_args();print(json.dumps((qualify if a.qualify else validate)(a.root,a.profile),sort_keys=True))
