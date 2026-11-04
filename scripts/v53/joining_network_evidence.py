"""One original healthy ADD: transport causality, transfers and durable ACKs.

Run the complete derived-state reader first. Observed wire bytes do not create
authority; permanent identities do not imply a peer was eligible at every cut.
This gate does not yet qualify every export's temporal authority or process cuts.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_retirement_replay as physical
from . import joining_phase_evidence as phase
from . import joining_install_storage as install
from . import selection_journal_evidence as selection_journal
from . import initial_current_evidence as initial_current
from . import current_lifecycle_evidence as current_lifecycle
from .joining_transcript import causal, transfers, SENDS, READS

p, s, f, disk, need, sha = physical.p, physical.s, physical.f, physical.disk, physical.need, physical.sha
wire = phase.exchange.d.transfer.t.wire


def interval(events, node, lower, upper, names, reason, scope=None):
    rows = [row for at,row in enumerate(events) if lower < at < upper and row.get('node') == node and row.get('event') in names]
    need([row['event'] for row in rows] == names and all(row.get('scope') == scope for row in rows), reason)


def capture_callback(point):
    return point.startswith(('CAPTURE_INTENT_', 'SOURCE_PACKET_', 'SOURCE_IMAGE_', 'BASIS_')) or point in (
        'SOURCE_BEFORE_CREATE', 'SOURCE_CREATED', 'SOURCE_FILES_DIRECTORY_FORCED', 'SOURCE_DIRECTORY_FORCED')


def grant_capture_order(events, node, scope, lower, upper, packet):
    # The ordinary capture writer first persists PROMISE and its exact recovery
    # intent, then the packet/images, then BASIS, then deletion of that intent.
    # Original packet bytes have already been checked by captures.collect.
    promise = ['PROMISE_BEFORE_WRITE', 'PROMISE_WRITTEN', 'PROMISE_FORCED']
    names = promise + ['CAPTURE_INTENT_'+v for v in (
        'CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED', 'PARENT_FORCED')]
    names += ['SOURCE_BEFORE_CREATE', 'SOURCE_CREATED']
    names += ['SOURCE_PACKET_'+v for v in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')]
    names += ['SOURCE_IMAGE_'+v for v in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')]*len(packet['images'])
    names += ['SOURCE_FILES_DIRECTORY_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_BEFORE_WRITE',
              'BASIS_PREFIX_WRITTEN', 'BASIS_WRITTEN', 'BASIS_FORCED', 'CAPTURE_INTENT_DELETED', 'CAPTURE_INTENT_CLEARED']
    actual = [(at, row) for at, row in enumerate(events) if lower < at < upper and row.get('node') == node and
              (capture_callback(row['event']) or row['event'] in promise)]
    need([row['event'] for _, row in actual] == names and all(
        row == dict(node=node, event=row['event'], **({'scope': scope} if scope else {})) for _, row in actual),
        'joining network durable grant order')
    return {at for at, row in actual if capture_callback(row['event'])}


def grants(root, events, rows):
    """The physical reader already compared all captured grants to derivation."""
    captures = p.captures.collect(root, events); by_key = {}; by_basis = {}; used = set(); callbacks = set()
    for capture in captures:
        node = capture['node']; files = disk.inventory(Path(root)/capture['capture']/'replica')
        journal = disk.journal(files['grants.gsr'], capture['root'], node)
        promise, basis = journal[-2][1], journal[-1][1]
        scope = None if capture['scope'] == 'network-owner' else capture['scope']
        starts = [at for at,row in enumerate(events[:capture['returnEvent']]) if row.get('node') == node and
                  row.get('scope') == scope and row.get('event') == 'CURRENT_BEFORE_CAPTURE']
        need(starts, 'joining network grant start absent'); start = starts[-1]
        packet = disk.p.decode(files['sources/'+capture['basisId']+'/source.gscp'])
        bound = grant_capture_order(events, node, scope, start, capture['returnEvent'], packet)
        need(not callbacks.intersection(bound), 'joining network reused grant capture callback'); callbacks.update(bound)
        key = node, f.canonical(capture['ballot'])
        need(key not in by_key and capture['basisSha256'] not in by_basis,'joining network duplicate grant')
        value = dict(capture, start=start, promise=sha(promise), basis=sha(basis), view=journal[-1][2]['view'])
        by_key[key] = value; by_basis[value['basis']] = value
    need(callbacks == {at for at, row in enumerate(events) if capture_callback(row['event'])},
         'joining network unbound grant capture callback')
    for row in rows:
        if row['kind'] != 'PREPARE': continue
        q, a = row['request'], row['response']; key = q['sender']['node'], f.canonical(q['ballot'])
        peer_key = q['recipient']['node'], f.canonical(q['ballot'])
        need(row['answer'] == 'PROMISE' and key in by_key and peer_key in by_key, 'joining network original prepare grant')
        own, peer = by_key[key], by_key[peer_key]
        need(q['payload'] == dict(promise=own['promise']) and a['payload'] == dict(basis=peer['basis']) and
             q['view'] == own['view'] == peer['view'],
             'joining network prepare authority')
        need(peer_key not in used and own['capturedEvent'] < row['sent'] and
             row['received'] < peer['start'] < peer['returnEvent'] < peer['capturedEvent'] < row['offered'],
             'joining network force before promise reply')
        used.add(peer_key)
    # The joining initializer's own grant is local. Every other non-proposer
    # grant is issued by one observed PREPARE, not an unexplained extra grant.
    required = {key for key,v in by_key.items() if v['node'] != v['ballot']['proposer']}
    need(used == required, 'joining network unbound peer grant')
    return dict(forcedGrants=len(captures), boundPromiseReplies=len(used)), by_basis


def proposer_forces(events,node,scope,selected_at,upper,replies,members):
    """Local installation follows every selected peer's original delivered ACK."""
    need(replies and all(type(v.get('delivered')) is int for v in replies),
         'joining network proposer delivered ACKs')
    interval(events,node,selected_at,min(v['sent'] for v in replies),
             ['SELECTED_BEFORE_RETURN'],'joining network proposer selection return',scope)
    names=install.sequence(members)
    points=[at for at,v in enumerate(events) if selected_at<at<upper and v.get('node')==node and v['event'] in names]
    need(points and min(points)>max(v['delivered'] for v in replies),
         'joining network proposer installation after ACKs')
    install.interval(events,node,scope,selected_at,upper,members,['SELECTED_BEFORE_RETURN'],
                     'joining network proposer complete installation order')


def installations(root, events, rows, replay, bases, *, recovery=None):
    selections = {sha(parts['SELECTED']): f.decode(parts['SELECTED'],'records','SELECTED') for parts in replay.phases}
    recovery_digest = None
    if recovery is not None:
        # Only the same-view wrapper supplies this already physically derived
        # selection. Ordinary profile readers keep their exact selection set.
        selected = f.decode(recovery,'records','SELECTED',replay.root)
        need(selected['root'] == replay.root and selected['cut'] == replay.states[11]['cut'] and
             selected['view'] == s.catalog.authority(replay.root,selected['cut']['view']) and
             selected['ballot']['proposer'] == replay.joining and selected['nextEntry'] is None and
             replay.joining in [v['voter'] for v in selected['sources']], 'joining network recovery selection')
        recovery_digest = sha(recovery)
        need(recovery_digest not in selections,'joining network duplicate recovery selection')
        selections[recovery_digest] = selected
    forced = {}; count = 0; used = set()
    labels = {0:'installed',2:'installed-2',4:'installed-3',6:'installed-4',9:'continuation-installed-9',10:'continuation-installed-10'}
    for node in {source['voter'] for selected in selections.values() for source in selected['sources']}:
        expected = [(h,v) for h,v in selections.items() if node in [source['voter'] for source in v['sources']]]
        actual = [(at,v) for at,v in enumerate(events) if v.get('node') == node and v['event'] == 'SELECTED_FORCED']
        need(len(expected) == len(actual),'joining network complete selection forces')
        for (digest,selected),(at,event) in zip(expected,actual):
            need(event.get('scope') == ('continuation-owner' if node == replay.joining else None),
                 'joining network selection lifetime')
            forced[node,digest] = at
            for source in selected['sources']:
                grant = bases.get(source['basisDigest'])
                need(grant is not None and grant['node'] == source['voter'] and grant['basisId'] == source['basisId'] and
                     grant['ballot'] == selected['ballot'] and grant['capturedEvent'] < at,
                     'joining network selection before original grants')
                if node == selected['ballot']['proposer'] and source['voter'] != node:
                    replies = [v for v in rows if v['kind'] == 'PREPARE' and v['request']['sender']['node'] == node and
                               v['response']['payload'] == dict(basis=source['basisDigest'])]
                    need(len(replies) == 1 and replies[0]['delivered'] < at,
                         'joining network selection before delivered promises')
    for row in rows:
        if row['kind'] != 'SELECTED': continue
        q, a = row['request'], row['response']; digest = q['payload']['selection']; selected = selections.get(digest)
        need(selected is not None and row['answer'] == 'INSTALL_ACK' and q['payload'] == dict(selection=digest) and
             q['ballot'] == selected['ballot'] and q['view'] == selected['view'] and
             q['sender']['node'] == selected['ballot']['proposer'] and
             q['recipient']['node'] in [v['voter'] for v in selected['sources']] and
             a['payload'] == dict(selection=digest, cut=selected['cut']), 'joining network installation authority')
        node = q['recipient']['node']; scope = 'continuation-owner' if node == replay.joining else None
        need((node,digest) not in used and forced[q['sender']['node'],digest] < row['sent'] and
             row['received'] < forced[node,digest] < row['offered'], 'joining network selected propagation order')
        used.add((node,digest))
        cut = selected['cut']['index']
        if digest == recovery_digest:
            directory = Path(root)/'same-view-installed'/node
        else:
            need(cut in labels,'joining network known installation snapshot')
            directory = Path(root)/(f'joining-installed-{cut}/replica' if node == replay.joining else labels[cut]+'/'+node)
        # Every snapshot is first compared against independent derivation by
        # physical.validate. Its exact members determine all required writes.
        _,members,packet = disk.current(disk.inventory(directory))
        need(sha(members['selected.gsr']) == digest,'joining network installed selection bytes')
        install.interval(events,node,scope,row['received'],row['offered'],members,
                         ['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],'joining network durable installation order')
        count += 1
    need(used == {(node,h) for (node,h) in forced if node != selections[h]['ballot']['proposer']},
         'joining network missing selected propagation')
    need(sum(v['event']=='SELECTED_FORCED' for v in events)==len(forced),'joining network unbound selection force')
    local_count=0
    for digest,selected in selections.items():
        if digest==recovery_digest:continue  # separately bounded by cold reopen below
        node=selected['ballot']['proposer'];scope='continuation-owner' if node==replay.joining else None
        selected_at=forced[node,digest];cut=selected['cut']['index']
        replies=[v for v in rows if v['kind']=='SELECTED' and v['request']['payload']==dict(selection=digest)]
        boundaries=[at for at,v in enumerate(events) if at>selected_at and v.get('node')==node and v['event']=='ACCEPT_VALIDATED']
        need(boundaries,'joining network proposer next slot boundary')
        need(cut in labels,'joining network known installation snapshot')
        directory=Path(root)/(f'joining-installed-{cut}/replica' if node==replay.joining else labels[cut]+'/'+node)
        members=disk.current(disk.inventory(directory))[1]
        need(sha(members['selected.gsr'])==digest,'joining network proposer installed selection bytes')
        proposer_forces(events,node,scope,selected_at,min(boundaries),replies,members);local_count+=1
    result = dict(boundInstallReplies=count, forcedSelections=len(forced),proposerLocalInstallations=local_count)
    if recovery_digest is not None:
        node = replay.joining; scope = 'continuation-owner'
        replies = [v for v in rows if v['kind']=='SELECTED' and v['request']['payload']==dict(selection=recovery_digest)]
        need(replies and all(type(v.get('delivered')) is int for v in replies),'joining network recovery delivered ACKs')
        interval(events,node,forced[node,recovery_digest],min(v['sent'] for v in replies),
                 ['SELECTED_BEFORE_RETURN'],'joining network recovery local selection return',scope)
        cold = [at for at,v in enumerate(events) if v.get('node')==node and v.get('scope')=='stable-cold-owner' and
                v['event']=='CURRENT_VALIDATED']
        need(len(cold)==1,'joining network recovery cold boundary')
        members = disk.current(disk.inventory(Path(root)/'joining-after-final-recovery'/'replica'))[1]
        need(sha(members['selected.gsr'])==recovery_digest,'joining network recovery local selection bytes')
        names = install.sequence(members)
        local_events = [at for at,v in enumerate(events) if forced[node,recovery_digest] < at < cold[0] and
                        v.get('node')==node and v['event'] in names]
        need(local_events and min(local_events)>max(v['delivered'] for v in replies),
             'joining network recovery local installation order')
        install.interval(events,node,scope,forced[node,recovery_digest],cold[0],members,[],
                         'joining network recovery local installation order')
        result.update(recoveryInstallReplies=len(replies),recoveryLocalInstallations=1)
    journal_bounds=[]
    for (node,digest),at in forced.items():
        selected=selections[digest]
        scope='continuation-owner' if node==replay.joining else None
        replies=[v for v in rows if v['kind']=='SELECTED' and v['request']['payload']==dict(selection=digest)]
        if node==selected['ballot']['proposer']:
            grants=[bases[v['basisDigest']] for v in selected['sources']]
            promises=[v['delivered'] for v in rows if v['kind']=='PREPARE' and
                      v['request']['sender']['node']==node and
                      v['response']['payload']['basis'] in {s['basisDigest'] for s in selected['sources']}]
            lower=max([v['capturedEvent'] for v in grants]+promises);upper=min(v['sent'] for v in replies)
        else:
            reply=next(v for v in replies if v['request']['recipient']['node']==node)
            lower,upper=reply['received'],reply['offered']
        journal_bounds.append(dict(node=node,scope=scope,selection=digest,forced=at,lower=lower,upper=upper))
    selection_journal.validate(events,journal_bounds)
    return result


def network(root, *, size=3, kind='ADD', recovery=None):
    """Only called standalone after the original physical precondition passes."""
    root = Path(root); replay = s.Replay(root,size=size,kind=kind)
    for index in range(1,12): replay.step(index)
    events = s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
    wires = s.collection.read_json(root,'wire.json',s.collection.WIRE_BYTES)
    identities = s.catalog.identities(replay.states[-1]['identities'])
    failed=[];rows = causal(events,wires,identities,replay.root,failed=failed)
    result = transfers(rows)
    grant_result,bases = grants(root,events,rows)
    result.update(grant_result,**installations(root,events,rows,replay,bases,recovery=recovery))
    result.update(phase.phase_replay(events,rows,replay,phase.blocks(events,replay)))
    result.update(wireExchanges=len(rows),sentRequests=len(rows),receivedRequests=len(rows),deliveredResponses=sum(v['delivered'] is not None for v in rows))
    if failed:
        response_less=[v for v in failed if not v['withheldResponse']]
        result.update(sentRequests=len(rows)+len(response_less),
                      receivedRequests=len(rows)+sum(v['received'] is not None for v in response_less),
                      failedAttempts=len(failed),responseLessFailures=len(response_less),
                      terminalObservations=sum(1+(v['serverFailed'] is not None) for v in failed))
    policy=phase.loss.declaration(events)
    if policy:result.update(sourceFault=policy['kind'],lostReplies=1,recoveredLostReplies=1)
    initial_current.validate(events,replay.old)
    current_lifecycle.joining(events,replay,bases,recovery)
    return result


def validate(root):
    root = Path(root); before = s.collection.inventory(root)
    derived = physical.validate(root)
    result = network(root)
    need(s.collection.inventory(root) == before,'joining network original changed')
    return dict(status='PASS',scope='native-ADD-complete-observed-network-and-durable-ACKs',**result,
        physicalPrecondition=derived['scope'], sourceRetirementPhysicalQualified=True,
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


GRANT_WRITES = {
    'grant-missing-'+point.lower().replace('_','-'):point for point in (
        'PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','CAPTURE_INTENT_CREATED','CAPTURE_INTENT_PREFIX_WRITTEN',
        'CAPTURE_INTENT_WRITTEN','SOURCE_BEFORE_CREATE','SOURCE_CREATED','SOURCE_PACKET_CREATED',
        'SOURCE_PACKET_PREFIX_WRITTEN','SOURCE_PACKET_WRITTEN','SOURCE_IMAGE_CREATED',
        'SOURCE_IMAGE_PREFIX_WRITTEN','SOURCE_IMAGE_WRITTEN','BASIS_BEFORE_WRITE','BASIS_PREFIX_WRITTEN',
        'BASIS_WRITTEN','CAPTURE_INTENT_DELETED')}
GRANT_NEGATIVES = {
    **{name:'joining network durable grant order' for name in GRANT_WRITES},
    'grant-duplicate-prefix':'joining network durable grant order',
    'grant-reordered-prefix':'joining network durable grant order',
    'grant-foreign-write-scope':'joining network durable grant order',
    'grant-prefix-before-capture':'joining network durable grant order',
    'grant-unbound-write':'joining network unbound grant capture callback',
    'grant-unknown-capture-callback':'joining network unbound grant capture callback',
}


NEGATIVES = {
    'missing-send':'joining network receive without send',
    'missing-request':'joining network response without request',
    'late-request':'joining network response without request',
    'overlapping-retry':'joining network ambiguous overlapping retry',
    'wrong-send-owner':'joining network send identity',
    'wrong-send-kind':'joining network send bytes',
    'wrong-server-lifetime':'joining network response request binding',
    'wrong-client-lifetime':'joining network client lifetime',
    'missing-delivery':'joining network undelivered healthy response',
    'missing-grant-force':'joining network durable grant order',
    'early-promise':'joining network force before promise reply',
    'wrong-promise-authority':'joining network prepare authority',
    'wrong-prepare-view':'joining network prepare authority',
    'early-selection':'joining network selection before delivered promises',
    'early-propagation':'joining network selected propagation order',
    'missing-install-image-force':'joining network durable installation order',
    'wrong-install-cut':'joining network installation authority',
    'changed-chunk':'joining network complete transfer commit',
    'wrong-offer-extent':'joining network complete transfer commit',
    'wrong-commit':'joining network complete transfer commit',
    'transfer-sequence-gap':'joining network transfer sequence',
    'transfer-before-delivery':'joining network transfer next before delivery',
    **GRANT_NEGATIVES,
    **install.NEGATIVES,
    **selection_journal.NEGATIVES,
    **initial_current.NEGATIVES,
    **current_lifecycle.NEGATIVES,
    **current_lifecycle.JOINING_NEGATIVES,
}


def mutate(root, name):
    events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
    wires=s.collection.read_json(root,'wire.json',s.collection.WIRE_BYTES)
    def at(event,node=None):
        return next(i for i,v in enumerate(events) if v['event']==event and (node is None or v['node']==node))
    def replace(row,side,kind,value):
        old=sha(base64.b64decode(row[side]));raw=f.encode('wire',kind,value);new=sha(raw)
        row[side]=base64.b64encode(raw).decode()
        for event in events:
            if event.get(side)==old:
                event[side]=new
                if side=='request' and event['event'] in SENDS:event['bytes']=row[side]
                if side=='response' and 'responseKind' in event:event['responseKind']=kind
                if side=='response' and event['event']=='NETWORK_RECEIVED':event['kind']=kind
    def first(kind,answer=None):
        return next(row for row in wires if wire(row['request'])[0]==kind and (answer is None or wire(row['response'])[0]==answer))
    if name in {**current_lifecycle.NEGATIVES,**current_lifecycle.JOINING_NEGATIVES}:current_lifecycle.mutate(events,name)
    elif name in initial_current.NEGATIVES:initial_current.mutate(events,name)
    elif name in selection_journal.NEGATIVES:selection_journal.mutate(events,name)
    elif name in install.NEGATIVES:install.mutate(events,name)
    elif name in GRANT_NEGATIVES:
        if name in GRANT_WRITES:events.pop(at(GRANT_WRITES[name],'node-1'))
        elif name=='grant-duplicate-prefix':
            index=at('BASIS_PREFIX_WRITTEN','node-1');events.insert(index,dict(events[index]))
        elif name=='grant-reordered-prefix':
            index=at('BASIS_PREFIX_WRITTEN','node-1');other=at('BASIS_WRITTEN','node-1')
            events[index],events[other]=events[other],events[index]
        elif name=='grant-foreign-write-scope':events[at('SOURCE_PACKET_PREFIX_WRITTEN','node-1')]['scope']='foreign-owner'
        elif name=='grant-prefix-before-capture':
            row=events.pop(at('SOURCE_PACKET_PREFIX_WRITTEN','node-1'));events.insert(at('CURRENT_BEFORE_CAPTURE','node-1'),row)
        elif name=='grant-unbound-write':events.append(dict(node='node-1',event='BASIS_WRITTEN'))
        else:events.append(dict(node='node-1',event='CAPTURE_INTENT_UNKNOWN'))
    elif name=='missing-send':events.pop(at('NETWORK_SEND'))
    elif name=='missing-request':events.pop(at('NETWORK_REQUEST'))
    elif name=='late-request':
        row=events.pop(at('NETWORK_REQUEST'))
        reply=next(i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v['request']==row['request'])
        events.insert(reply+1,row)
    elif name=='overlapping-retry':
        i=at('NETWORK_SEND');events.insert(i,dict(events[i]))
    elif name=='wrong-send-owner':events[at('NETWORK_SEND')]['node']='node-3'
    elif name=='wrong-send-kind':events[at('NETWORK_SEND')]['kind']='PROOF'
    elif name=='wrong-server-lifetime':events[at('AFTER_REQUEST_READ')]['scope']='changed-lifetime'
    elif name=='wrong-client-lifetime':events[at('AFTER_RESPONSE_READ')]['scope']='changed-lifetime'
    elif name=='missing-delivery':events.pop(at('NETWORK_RECEIVED'))
    elif name=='missing-grant-force':events.pop(at('BASIS_FORCED','node-2'))
    elif name=='early-promise':
        row=first('PREPARE');digest=sha(base64.b64decode(row['response']))
        node=wire(row['request'])[1]['recipient']['node']
        pos=next(i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v['response']==digest)
        # Concurrent remote grants may answer in either order. Move this
        # actual reply before its own grant force, not a different voter's.
        forces=[i for i,v in enumerate(events[:pos]) if v['node']==node and v['event']=='BASIS_FORCED']
        need(forces,'joining early promise mutation original receiver force')
        offered=events.pop(pos);events.insert(forces[-1],offered)
    elif name=='early-selection':
        row=events.pop(at('SELECTED_FORCED','node-1'))
        pos=next(i for i,v in enumerate(events) if v['event']=='NETWORK_RECEIVED' and v['kind']=='PROMISE')
        events.insert(pos,row)
    elif name=='early-propagation':
        row=events.pop(at('SELECTED_FORCED','node-1'))
        pos=next(i for i,v in enumerate(events) if v['event']=='NETWORK_SEND' and v['kind']=='SELECTED')
        events.insert(pos+1,row)
    elif name=='missing-install-image-force':events.pop(at('INSTALL_IMAGE_FORCED','node-2'))
    elif name=='transfer-before-delivery':
        pos=next(i for i,v in enumerate(events) if v['event']=='NETWORK_SEND' and v['kind']=='CHUNK' and
                 wire(v['bytes'])[1]['sequence']==2)
        row=events.pop(pos)
        pos=max(i for i,v in enumerate(events[:pos]) if v['event']=='NETWORK_RECEIVED' and v['node']==row['node'])
        events.insert(pos,row)
    else:
        kind='PREPARE' if name in ('wrong-promise-authority','wrong-prepare-view') else 'SELECTED' if name=='wrong-install-cut' else 'TRANSFER_COMMIT' if name=='wrong-commit' else 'CHUNK'
        answer='SOURCE_OFFER' if name=='wrong-offer-extent' else 'CHUNK' if name in ('changed-chunk','transfer-sequence-gap') else None
        row=first(kind,answer);rk,q=wire(row['request']);ak,a=wire(row['response'])
        if name=='wrong-promise-authority':a['payload']['basis']='f'*64
        elif name=='wrong-prepare-view':
            q['view']=a['view']='f'*64;replace(row,'request',rk,q)
        elif name=='wrong-install-cut':a['payload']['cut']['index']+=1
        elif name=='wrong-offer-extent':a['payload']['bytes']+=1
        elif name=='wrong-commit':a['payload']['digest']='f'*64
        elif name=='transfer-sequence-gap':
            q['sequence']+=1;a['sequence']+=1;replace(row,'request',rk,q)
        elif name=='changed-chunk':
            data=bytearray(base64.b64decode(a['payload']['bytes']));data[0]^=1
            a['payload'].update(bytes=base64.b64encode(data).decode(),digest=sha(data))
        else:raise ValueError('unknown joining network mutation: '+name)
        replace(row,'response',ak,a)
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wires))


def qualify(root):
    root=Path(root);original=validate(root);before=s.collection.inventory(root);results=[]
    # Mutations alter observations only. Reuse the passing derivation only if
    # every physical file and directory remains byte-for-byte unchanged.
    files={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-network-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            after=s.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==files and
                 before['directories']==after['directories'],'joining network negative changed physical inputs')
            try:network(changed)
            except ValueError as error:need(str(error)==reason,'joining unrelated network negative: '+name+': '+str(error))
            else:raise ValueError('joining network mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(s.collection.inventory(root)==before,'joining network negative changed original')
    return dict(original=original,negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
