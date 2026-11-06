"""Independent replay of the native selected-future continuation history.

Every expected byte starts at the original bootstrap/vote/application prelude.
Observed grants provide only fresh UUIDs, never the selected content or ledger.
Optional process evidence covers publication cuts; neither form qualifies
autonomous dispatch or all Phase 3.
"""
import argparse
import copy
import json
import shutil
import tempfile
import struct
import uuid
from pathlib import Path
from . import selected_future_evidence as original
from . import distinct_minority_evidence as carried

u, s, p, c, f, e, need = original.u, original.s, original.p, original.c, original.f, original.e, original.need
NAMES = ('node-2', 'node-3')


def frame(magic, body, flags=0):
    header = struct.pack('>IHHII', magic, 1, 3, flags, len(body))
    return header+bytes.fromhex(e.digest(header+body))+body


def projection(root, owner, proofs):
    refs = [dict(owner=value[0], sha256=h) for h, value in sorted(proofs.items())]
    return frame(0x47534653, f.canonical(dict(root=root, owner=owner, proofs=refs)))


def wrapped(promise, ledger, descriptor):
    return frame(0x47535250, s.part(promise)+s.part(ledger)+bytes.fromhex(e.digest(descriptor)), 2)


def install(group, sources, grants, names, ballot, futures, extras, *, selected_prefix=None, merge_ledgers=None):
    # The default keeps the older no-confirmation contract. Histories with
    # original confirmation/renewal provenance must supply their owning reducer;
    # neither a decoded response nor an observed final ledger is a substitute.
    longest = names[-1]; packet = sources[longest][1]; cap = packet['capsule']
    choices = []
    for node in names:
        basis = f.decode(grants[node][1], 'records', 'BASIS')
        need(basis['cut'] == cap['cut'], 'continuation equal original cuts')
        if basis['accepted'] is not None:
            raw = sources[node][1]['objects'][basis['accepted']]
            accept = f.decode(raw, 'records', 'ACCEPT')
            choices.append((accept['ballot']['counter'], node, raw, accept))
    chosen = max(choices) if choices else None
    tail = e.digest(chosen[2]) if chosen else None
    selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']),
        ballot=ballot, cut=cap['cut'], nextEntry=chosen[3]['entry'] if chosen else None,
        sources=[dict(voter=n, basisId=f.decode(grants[n][1], 'records', 'BASIS')['basisId'], basisDigest=e.digest(grants[n][1])) for n in names]))
    result = dict(group); selected_group = dict(group)
    for node in names:
        files = group[node]; prefix, old, _ = c.current(files)
        ledger_intent = s.intent(u.identity(files), selected, files[s.FILE], [sources[n] for n in names])
        objects = dict(packet['objects']) if selected_prefix is None else selected_prefix(packet, files['root.gsr'])
        if selected_prefix is not None and 'owned-tail.gsr' in old:
            original_accept = old['owned-tail.gsr']; old_packet = c.current(files)[2]
            original_entry = f.decode(original_accept, 'records', 'ACCEPT')['entry']
            payload = f.decode(old_packet['objects'][original_entry], 'records', 'ENTRY')['payload']
            for h in (e.digest(original_accept), original_entry, payload): objects[h] = old_packet['objects'][h]
        objects.update(extras); objects.update({h:v[1] for h,v in futures.items()})
        objects[e.digest(ledger_intent)] = ledger_intent
        if chosen:
            _, from_node, accept_raw, accept = chosen
            entry = f.decode(sources[from_node][1]['objects'][accept['entry']], 'records', 'ENTRY')
            for h in (tail, accept['entry'], entry['payload']): objects[h] = sources[from_node][1]['objects'][h]
        raw = c.packet_bytes(cap, objects, packet['images'])
        members = dict(zip(('promise.gsr','basis.gsr'), grants[node]), **{'selected.gsr':selected,
            'selected-sources.gsr':b''.join(grants[n][1] for n in names), 'source.gscp':raw})
        if tail: members['owned-tail.gsr'] = objects[tail]
        members.update({h+'.image':old[h+'.image'] for h in packet['images']})
        selector, generation = c.generation(members, s.p.decode(raw)['capsule'], node, 'b' if prefix=='generations/a/' else 'a', tail)
        selected_group[node] = dict(files, **{'grants.gsr':files['grants.gsr']+selected})
        result[node] = dict(selected_group[node], **generation, **{'selector.gsr':selector,
            s.FILE:(s.merged if merge_ledgers is None else merge_ledgers)(files[s.FILE], [group[n][s.FILE] for n in names])})
    return selected_group, result


def vote(group, entry):
    result = dict(group)
    for node in NAMES:
        files = group[node]; _, local, _ = c.current(files); selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
        value = f.decode(entry, 'records', 'ENTRY')
        accept = f.encode('records','ACCEPT',dict(root=value['root'], authority=value['authority'], ballot=selected['ballot'], entry=e.digest(entry), index=value['index']))
        result[node] = dict(files, **{'pending.accept':e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept], b'')})
    return result


def maintained(group):
    result = dict(group); result.update(p.settled({n:group[n] for n in NAMES})); return result


def campaign(root, group, counter, futures, *, selected_prefix=None):
    proposer = u.identity(group['node-3']); ballot = dict(counter=counter,proposer='node-3',incarnation=proposer['storage'])
    prepared, grants, sources, extras = dict(group), {}, {}, {}
    for node in NAMES:
        files = group[node]; raw, tail = carried.captured(files); packet = s.p.decode(raw); cap = packet['capsule']
        _, local, _ = c.current(files); actual = c.inventory(root/f'round-{counter}-prepared'/node)
        prior = c.journal(files['grants.gsr'],cap['root'],node); after = c.journal(actual['grants.gsr'],cap['root'],node)
        need(after[:len(prior)]==prior and [r[0] for r in after[len(prior):]]==['PROMISE','BASIS'], 'continuation original grant extension')
        identifier=after[-2][2]['basisId']
        need(str(uuid.UUID(identifier))==identifier and all(v[2].get('basisId')!=identifier for v in prior),'continuation fresh source identity')
        value=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        promise=f.encode('records','PROMISE',value); objects=dict(packet['objects'])
        if futures:
            descriptor=projection(cap['root'],u.identity(files),futures); wrapper=wrapped(promise,files[s.FILE],descriptor)
            objects[e.digest(descriptor)]=descriptor; extras[e.digest(descriptor)]=descriptor
            objects.update({h:v[1] for h,v in futures.items()})
            need(tail is not None,'continuation inherited tail missing'); extras[tail]=objects[tail]
        else: wrapper=s.s.wrap(promise,files[s.FILE])
        objects[e.digest(wrapper)]=wrapper; raw=c.packet_bytes(cap,objects,packet['images']); frozen=s.p.decode(raw)
        basis=f.encode('records','BASIS',dict(value,voter=node,cut=cap['cut'],capsule=e.digest(frozen['capsuleBytes']),inventory=e.digest(frozen['indexBytes']),accepted=tail))
        folder='sources/'+identifier
        changed=dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis,folder:None,folder+'/source.gscp':raw})
        changed.update({folder+'/'+h+'.image':local[h+'.image'] for h in packet['images']})
        if node=='node-3': changed['allocator.gsr']=f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=counter))
        prepared[node]=changed;grants[node]=(promise,basis);sources[node]=(basis,frozen,wrapper)
    p.match(root,f'round-{counter}-prepared',prepared)
    chosen, installed=install(prepared,sources,grants,NAMES,ballot,futures,extras, selected_prefix=selected_prefix)
    p.match(root,f'round-{counter}-selected',chosen)
    return installed, extras


def publish(group, originals, futures, extras, stages=False):
    _, local, packet=c.current(group['node-2']);cap=packet['capsule']; root=cap['root']
    vote_frames,_=c.pending(group['node-2']['pending.accept']);accept=vote_frames['ACCEPT'];entry=vote_frames['ENTRY']
    def witnesses(raw,phase):
        return [dict(voter=n,incarnation=u.identity(group[n])['storage'],receipt=e.digest(f.canonical(dict(root=root,voter=n,incarnation=u.identity(group[n])['storage'],phase=phase,record=e.digest(raw))))) for n in NAMES]
    proof=f.encode('records','PROOF',dict(f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
    certificate=f.encode('records','CERTIFICATE',dict(f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
    catalog=originals['catalog.gsr'];cat=f.decode(catalog,'records','CATALOG');statement=originals['statement.gsr']
    acks=[f.encode('records','CHECKPOINT_ACK',dict(root=root,voter=n,incarnation=u.identity(group[n])['storage'],cut=cat['cut'],statement=e.digest(statement))) for n in NAMES]
    values=[group['node-2'][k] for k in ('root.gsr','genesis.gsr')]+[entry,accept,proof,certificate,b'',catalog,statement,*acks]
    base={e.digest(raw):raw for raw in values}; target=dict(cut=cat['cut'],catalog=e.digest(catalog),application=cat['application'])
    result=dict(group);applied=dict(group);switched=dict(group);retired=dict(group)
    for node in NAMES:
        files=group[node];prefix,members,source=c.current(files)
        selected=f.decode(members['selected.gsr'],'records','SELECTED')
        # Find the exact current intent by independently reconstructing it from
        # the original frozen sources referenced by the local selected-sources file.
        candidates=[raw for raw in source['objects'].values() if raw[:4]==b'GSRS']
        owned=[raw for raw in candidates if s.part(f.canonical(u.identity(files)))+s.part(members['selected.gsr']) == raw[48:48+len(s.part(f.canonical(u.identity(files)))+s.part(members['selected.gsr']))]]
        need(len(owned)==1,'continuation original installed retention intent');intent=owned[0]
        # Intent bytes have already been derived and matched by install().
        completion=frame(0x47534643,bytes.fromhex(e.digest(intent))+s.part(files[s.FILE]))
        objects=dict(base,**extras,**{h:v[1] for h,v in futures.items()})
        objects[e.digest(intent)]=intent;objects[e.digest(completion)]=completion
        item=dict(kind='RANGE',statement=e.digest(statement),endorsements=[e.digest(raw) for raw in acks],certificate=None,descriptor=None)
        raw=c.packet_bytes(dict(cap,**target,items=[item]),objects,packet['images'])
        coverage=dict(schema='gse-v53-selected-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(certificate))
        new={k:members[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
        new.update({'source.gscp':raw,c.COVERAGE:f.canonical(coverage),cat['application']+'.image':members[cat['application']+'.image']})
        selector,generation=c.generation(new,s.p.decode(raw)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
        ack=next(raw for raw in acks if f.decode(raw,'records','CHECKPOINT_ACK')['voter']==node)
        end=dict(zip(('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr'),
                     (files['selector.gsr'],certificate,catalog,statement,members[cat['application']+'.image'],ack)))
        end['plan.json']=f.canonical(dict(schema='gse-v53-applied-end/1.3',root=root,node=node,
            files=[dict(path=k,**e.info(v)) for k,v in sorted(end.items())]))
        pending=files['pending.accept']+proof+certificate
        pending=pending[:8]+struct.pack('>I',len(pending))+pending[12:]
        applied[node]=dict(files,**{'pending.accept':pending,'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})
        switched[node]=dict(applied[node],**generation,**{'selector.gsr':selector})
        retired[node]={k:v for k,v in switched[node].items() if k!='applied-end' and not k.startswith('applied-end/')}
        retired[node]['pending.accept']=c.EMPTY
        state=s.r.decode(files[s.FILE]);plan=copy.deepcopy(state['plan'])
        for peer in plan['peers']:
            if peer['identity']['node'] in NAMES:peer['possible'].append(target)
        ledger=s.r.frame(dict(state,revision=state['revision']+1,previous=e.digest(files[s.FILE]),plan=plan))
        updated=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY,s.FILE:ledger})
        if node=='node-2':updated[u.FILE]=u.frame(dict(u.initial(files),revision=2,previous=e.digest(files[u.FILE])),{})
        result[node]=updated
    return (applied,switched,retired,result) if stages else result


def process_points(node):
    points=['PUBLICATION_SELECTOR_FORCED','RETENTION_PREFIX_WRITTEN','RETENTION_RENAMED']
    if node=='node-2':points+=['INHERITED_FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_PREFIX_WRITTEN','FUTURE_RETENTION_RENAMED']
    return points


def processes(root,applied,switched,retired,completed):
    cases=[(node,mode,point) for node in NAMES for mode in ('halt','kill') for point in process_points(node)]
    p.selection.layout(root,{'-'.join(case) for case in cases},'inherited future complete process matrix')
    for node,mode,point in cases:
        path=root/'-'.join((node,mode,point))
        p.selection.layout(path,{'nodes.json','worker.log','resume.log','interrupted','recovered','result.json'},'inherited future process case')
        need(json.loads((path/'result.json').read_text())==dict(status='PASS',node=node,mode=mode,cut=point,exit=23 if mode=='halt' else 137),'inherited future process exit')
        inputs=json.loads((path/'nodes.json').read_text())
        need(len(inputs)==2 and all(set(row)=={'replica','application'} for row in inputs),'inherited future process paths')
        lines,events=u.worker(path/'worker.log')
        need(lines[-1]=='CUT '+point and events[-1]==point and sum(line.startswith('CUT ') for line in lines)==1
             and not any(line.startswith('RESPONSE ') for line in lines),'inherited future interrupted response')
        u.n.native_order(events,1);s.ordered(events,['PUBLICATION_SELECTOR_FORCED'],'inherited future publication')
        expected=dict(switched[node] if point=='PUBLICATION_SELECTOR_FORCED' else retired[node])
        if point=='RETENTION_PREFIX_WRITTEN':expected[s.NEXT]=completed[node][s.FILE][:len(completed[node][s.FILE])//2]
        if point not in ('PUBLICATION_SELECTOR_FORCED','RETENTION_PREFIX_WRITTEN'):expected[s.FILE]=completed[node][s.FILE]
        if point=='FUTURE_RETENTION_PREFIX_WRITTEN':expected[u.NEXT]=completed[node][u.FILE][:len(completed[node][u.FILE])//2]
        if point=='FUTURE_RETENTION_RENAMED':expected[u.FILE]=completed[node][u.FILE]
        if point in process_points('node-2')[3:]:
            s.ordered(events,['RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED'],'inherited future promotion before clear')
        need(c.inventory(path/'interrupted')==expected,'inherited future exact interrupted files')
        need(c.inventory(path/'recovered')==completed[node],'inherited future exact recovered files')
        lines,recovery=u.worker(path/'resume.log')
        need(lines[-1].startswith('RESPONSE ') and sum(line.startswith('RESPONSE ') for line in lines)==1
             and not any(line.startswith('CUT ') for line in lines),'inherited future recovered response position')
        state=s.r.decode(completed[node][s.FILE]);final=completed[node]
        response=dict(pending=False,revision=2 if node=='node-2' else 0,digest=e.digest(final[u.FILE]),
                      plan=state['plan'],peerRevision=state['revision'],published=c.current(final)[2]['capsule']['cut'])
        need(json.loads(lines[-1][9:])==response,'inherited future exact recovered response')
        if point in ('PUBLICATION_SELECTOR_FORCED','RETENTION_PREFIX_WRITTEN'):
            s.ordered(recovery,['RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED'],'inherited future resumed promotion')
        if node=='node-2' and point!='FUTURE_RETENTION_RENAMED':
            s.ordered(recovery,['FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_CLEARED'],'inherited future resumed clear')
    return len(cases)


def validate(root,require_process=False, *, selected_prefix=None):
    root=Path(root)
    required={'original-plan.gsbp','original-application.image','initial','retaining-genesis','calls.json',
              'entry-1.gsr','payload-1.bin','certified','before-future','pending-future','two-futures','proposal-sources',
              'future-installed','future-native-retired','future-install-maintenance','future-reinstalled',
              'future-reclaimed','future-republished','future-published-maintenance'}
    required|={'round-1-'+name for name in ('prepared','selected','installed','settled')}
    required|={'slot-1-'+name for name in ('accepted','proved','certified')}
    required|={'round-'+str(round)+'-'+phase for round in (4,5) for phase in ('prepared','selected')}
    required.add('round-5-installed')
    process=(root/'publication-process').exists()
    need(not require_process or process,'inherited future process evidence required')
    if process:required|={'publication-process','future-reapplied'}
    p.selection.layout(root,required,'inherited future evidence inventory')
    _,group,sources,grants,pending,originals,ballot=original.original_sources(root, selected_prefix=selected_prefix)
    futures={e.digest(raw):(u.identity(group[node]),raw) for node,raw in pending.items()}
    _,group=install(group,sources,grants,sorted(group),ballot,futures,{}, selected_prefix=selected_prefix)
    p.match(root,'future-installed',group)
    for n in NAMES:group[n]={k:v for k,v in group[n].items() if k!='applied-end' and not k.startswith('applied-end/')}
    group=vote(group,originals['entry.gsr']);p.match(root,'future-native-retired',group)
    group=maintained(group);p.match(root,'future-install-maintenance',group)
    group,extras=campaign(root,group,4,futures, selected_prefix=selected_prefix);p.match(root,'future-reinstalled',group)
    group=maintained(vote(group,originals['entry.gsr']));p.match(root,'future-reclaimed',group)
    if process:
        applied,switched,retired,group=publish(group,originals,futures,extras,True)
        p.match(root,'future-reapplied',applied)
        process_cases=processes(root/'publication-process',applied,switched,retired,group)
    else:group=publish(group,originals,futures,extras);process_cases=0
    p.match(root,'future-republished',group)
    for n in NAMES:
        for peer in NAMES:
            state=s.r.decode(group[n][s.FILE]);plan=copy.deepcopy(state['plan'])
            row=next(r for r in plan['peers'] if r['identity']['node']==peer);row['possible']=row['possible'][-1:]
            group[n][s.FILE]=s.r.frame(dict(state,revision=state['revision']+1,previous=e.digest(group[n][s.FILE]),plan=plan))
    group=maintained(group);p.match(root,'future-published-maintenance',group)
    group,_=campaign(root,group,5,{}, selected_prefix=selected_prefix);p.match(root,'round-5-installed',group)
    rows=json.loads((root/'calls.json').read_text())
    for op,names,events in [
        ('record-future',['node-1'],['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_BEFORE_RETURN']),
        ('second-future',['node-2'],['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_BEFORE_RETURN']),
        ('future-select',sorted(group),['SELECTED_FORCED','SELECTED_BEFORE_RETURN']),
        ('future-install',sorted(group),['INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']),
        ('future-retire',list(NAMES),['NATIVE_RETIREMENT_CERTIFICATE_RETAINED','STAGED_RETIREMENT_BEFORE_RETURN','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN']),
        ('verify-inherited-source',list(NAMES),['INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']),
        ('future-reaccept',list(NAMES),['ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN']),
        ('future-reapply',list(NAMES),['NATIVE_CERTIFICATE_RETAINED','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']),
        ('future-reprove',list(NAMES),['PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN']),
        ('future-recertify',list(NAMES),['CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN']),
        ('future-republish',list(NAMES),['PUBLICATION_SELECTOR_FORCED','RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'])]:
        calls=[row for row in rows if row['operation']==op]
        need([row['node'] for row in calls]==names,'inherited future owner calls: '+op)
        for row in calls:s.ordered(row['events'],events,'inherited future '+op)
    for counter in (4,5):
        for phase,names,events in [
            ('allocate',['node-3'],['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']),
            ('prepare',list(NAMES),['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN']),
            ('select',list(NAMES),['SELECTED_FORCED','SELECTED_BEFORE_RETURN'])]:
            calls=[row for row in rows if row['operation']==phase+'-'+str(counter)]
            need([row['node'] for row in calls]==names,'inherited future campaign calls: '+phase)
            for row in calls:s.ordered(row['events'],events,'inherited future '+phase)
    last_original=max(i for i,row in enumerate(rows) if row['operation']=='future-install')
    need(all(row['node'] in NAMES for row in rows[last_original+1:]),'inherited future offline owner participated')
    return dict(status='PASS',originalFutureProofs=2,survivingOwners=2,elections=[3,4,5],
                publicationIndex=1,offlineOriginalOwner='node-1',processCrashQualification=process,
                processCases=process_cases,freshProcesses=2*process_cases,phase3Complete=False)


def qualify(root,require_process=False, *, selected_prefix=None):
    root=Path(root);result=validate(root,require_process, selected_prefix=selected_prefix);negatives=[]
    variants=[('original-proof','two-futures/node-1/'+u.FILE,'admitted exact two-futures: node-1'),
              ('installed-proof','future-installed/node-3/selector.gsr','admitted exact future-installed: node-3'),
              ('retirement','future-native-retired/node-2/pending.accept','admitted exact future-native-retired: node-2'),
              ('maintenance','future-install-maintenance/node-2/grants.gsr','admitted exact future-install-maintenance: node-2'),
              ('inherited-installed','future-reinstalled/node-3/selector.gsr','admitted exact future-reinstalled: node-3'),
              ('successor-vote','future-reclaimed/node-2/pending.accept','admitted exact future-reclaimed: node-2'),
              ('promotion','future-republished/node-3/'+s.FILE,'admitted exact future-republished: node-3'),
              ('clearing','future-republished/node-2/'+u.FILE,'admitted exact future-republished: node-2'),
              ('offline-owner','future-republished/node-1/'+s.FILE,'admitted exact future-republished: node-1'),
              ('observation','future-published-maintenance/node-3/'+s.FILE,'admitted exact future-published-maintenance: node-3'),
              ('next-election','round-5-installed/node-3/selector.gsr','admitted exact round-5-installed: node-3'),
              ('force-order','calls.json','selected retention force order: inherited future future-republish')]
    if result['processCrashQualification']:
        case='publication-process/node-2-kill-RETENTION_PREFIX_WRITTEN/'
        variants += [('process-ledger',case+'interrupted/'+s.NEXT,'inherited future exact interrupted files'),
                     ('process-clear',case+'recovered/'+u.FILE,'inherited future exact recovered files'),
                     ('process-selector',case+'recovered/selector.gsr','inherited future exact recovered files'),
                     ('process-response',case+'resume.log','inherited future exact recovered response')]
    for name,relative,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-inherited-future-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);path=copied/relative;before=path.read_bytes()
            if name=='force-order':
                rows=json.loads(before);next(row for row in rows if row['operation']=='future-republish')['events'].remove('RETENTION_PARENT_FORCED')
                changed=json.dumps(rows).encode()
            elif name=='process-response':changed=before.replace(b'"pending":false',b'"pending":true',1)
            else:changed=before[:-1]+bytes([before[-1]^1])
            need(changed!=before,'inherited future ineffective mutation');path.write_bytes(changed)
            try:validate(copied,require_process, selected_prefix=selected_prefix)
            except ValueError as error:need(str(error)==reason,'inherited future wrong rejection: '+name+': '+str(error))
            else:raise ValueError('inherited future accepted mutation: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(result,negatives=negatives)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--negative',action='store_true');parser.add_argument('--process',action='store_true')
    parser.add_argument('--reachable-selection',action='store_true',help='use the typed live-prefix model for sources built with selected-generation reachability')
    args=parser.parse_args()
    from .selected_prefix_evidence import prefix
    print(json.dumps((qualify if args.negative else validate)(args.root,args.process,
        selected_prefix=prefix if args.reachable_selection else None),sort_keys=True))


if __name__=='__main__':main()
