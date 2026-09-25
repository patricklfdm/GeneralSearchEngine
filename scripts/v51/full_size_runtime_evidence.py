"""Independent public-call and physical-byte audit of the 512-slot runtime gate."""
import argparse
import copy
from pathlib import Path
from . import performance_model as m, performance_plan as plan, performance_projection as projection
from . import performance_physical as physical, performance_evidence as provenance, performance_semantics as semantics
from . import format_inspector as fmt, recovery_inspector as recovery, storage_inspector as storage
from . import cloud_workload_contract as cloud, remote_rich_evidence as remote
from .full_size_evidence import read, json, documents

NODES=('node-1','node-2','node-3')
need=m.need
raw=projection.raw


class Calls:
    def __init__(self,history,runtime):
        self.expected={v['opId']:v for v in history};self.runtime=runtime
        need(1<=len(history)<=530 and len(self.expected)==len(history),'full runtime duplicate operation')
        updates=[v for v in history if v['kind']=='update']
        need(sum(v['kind']=='read' for v in history)<=8,'full runtime auxiliary read attempt bound')
        need(len(updates)<=511 and all(v['key']==1+(i-1)%64 and v['revision']==1+(i-1)//64 for i,v in enumerate(updates,1)),
             'full runtime mutation schedule')
        self.active={};self.seen=set();self.finished=set();self.reads={};self.captures={};self.validated={}
        self.mutations=set();self.read_barriers=set();self.projected=None;self.update_entries=None

    def event(self,node,row,projected,published,votes,promise):
        self.projected=projected;event=row['event'];manifest=projected['manifest']
        if self.update_entries is None:
            self.update_entries={}
            for digest,entry in projected['entries'].items():
                if entry['operation']==2:
                    command=tuple(m.decode_command(2,raw(entry['payload'])))
                    self.update_entries.setdefault(command,[]).append(digest)
        key=(node,row['generation'],row.get('readId'))
        if event=='CLIENT_INVOKE':
            op=row['opId'];want=self.expected.get(op)
            need(want is not None and op not in self.seen and all(want[k]==row[k] for k in ('kind','node','pid','generation')),
                 'full runtime unowned invocation')
            need(want['startNanos']<=row['localNanos'],'full runtime invocation interval')
            if row['kind']=='update':
                need(all(want[k]==row[k] for k in ('key','revision')),'full runtime changed update')
                matches=self.update_entries.get(((row['key'],m.document(row['key'],row['revision'])),),[])
                need(len(matches)==1 and matches[0] not in self.mutations,'full runtime update projection')
                self.mutations.add(matches[0]);row=dict(row,digest=matches[0])
            self.active[op]=row;self.seen.add(op)
        elif event=='PUBLIC_READ_INVOKE':
            op=row['opId'];need(op in self.active and self.active[op]['kind']=='read' and key not in self.reads and
                type(row['readId']) is int and row['readId']>0 and op not in [v['opId'] for v in self.reads.values()],
                'full runtime read identity')
            need(self.active[op]['order']<row['order'],'full runtime read invocation order');self.reads[key]=row
        elif event=='READ_CAPTURE_VALIDATED':
            need(key in self.reads and key not in self.validated and row['index'] in published,'full runtime read validation identity')
            snapshot,_=published[row['index']];proof=fmt.contextual_frame(raw(snapshot['terminalProof']),'PROOF',manifest)
            need((row['epoch'],proof['incarnation'])==promise,'full runtime stale capture')
            self.validated[key]=row
        elif event=='READ_CAPTURED':
            need(key in self.validated and key not in self.captures,'full runtime capture identity')
            validated=self.validated[key];invoke=self.reads[key]
            need(all(row[k]==validated[k] for k in ('epoch','index','sequence')) and validated['order']<row['order'],
                 'full runtime changed capture')
            snapshot,order=published[row['index']];digest=snapshot['anchors'][-1]['entryDigest'];proof=fmt.inspect(raw(snapshot['terminalProof']),'PROOF')
            vote=(proof['epoch'],proof['incarnation'],proof['index'],digest)
            need(projected['entries'][digest]['operation']==9 and digest not in self.read_barriers and
                 invoke['order']<votes.get(vote,-1)<order<validated['order'] and snapshot['applicationSequence']==row['sequence'],
                 'full runtime fresh read barrier')
            self.read_barriers.add(digest);self.captures[key]=dict(captured=row,opId=invoke['opId'])
        elif event=='READ_RELEASED':
            need(key in self.captures and 'released' not in self.captures[key],'full runtime unowned release')
            capture=self.captures[key]['captured']
            need(all(row[k]==capture[k] for k in ('index','sequence','epoch')) and capture['order']<row['order'],
                 'full runtime changed read release');self.captures[key]['released']=row
        elif event=='CLIENT_RESULT':
            op=row['opId'];need(op in self.active,'full runtime unmatched response');invoke=self.active.pop(op);want=self.expected[op]
            need(row['order']>invoke['order'] and row['localNanos']<=want['endNanos'] and
                 all(row[k]==want[k] for k in ('kind','node','pid','generation','outcome')),'full runtime response binding')
            if row['outcome']!='SUCCESS':
                need(row['kind']=='read' and row['outcome']=='NOT_APPLICABLE' and row.get('reasonCode')==want.get('reasonCode') and
                     row.get('reasonCode') in ('NOT_LEADER','NOT_READY','QUORUM_UNAVAILABLE','STALE_EPOCH','DEADLINE_EXCEEDED') and
                     not any(c['opId']==op for c in self.captures.values()),'full runtime unexpected refusal')
            elif row['kind']=='update':
                index=projected['entries'][invoke['digest']]['index']
                need(index in published and invoke['order']<published[index][1]<row['order'],
                     'full runtime update before own publication')
            elif row['kind']=='read':
                captures=[c for c in self.captures.values() if c['opId']==op]
                need(len(captures)==1 and 'released' in captures[0] and captures[0]['released']['order']<row['order'],
                     'full runtime result before read release')
                answer=documents(projected['states'][captures[0]['captured']['index']])
                need(row['documents']==want['documents']==answer,'full runtime captured answer')
            else:need(row['kind']=='checkpoint','full runtime unexpected command')
            self.finished.add(op)

    def finish(self):
        uncertain=self.runtime['uncertainOpId'];need(set(self.active)=={uncertain} and self.seen==set(self.expected) and
            self.finished==set(self.expected)-{uncertain},'full runtime incomplete public history')
        record=self.expected[uncertain]
        need(record['outcome']=='PENDING' and record['endNanos'] is None and record['disconnectNanos']>record['startNanos'],
             'full runtime invented crash response')
        need(all('released' in c for c in self.captures.values()) and len(self.read_barriers)<=8,'full runtime auxiliary read bound')


def load_traces(root,runtime):
    traces={n:[] for n in NODES};budget=[6<<30];seen=set()
    for process in runtime['processes']:
        node,generation=process['node'],process['generation'];key=node,generation
        need(node in traces and key not in seen and generation==1+sum(n==node for n,g in seen),'full runtime process generation')
        seen.add(key);rows=remote.lines(root/'group',f'{node}-g{generation}-trace',budget)
        need(rows and len(rows)<=100000 and [r['order'] for r in rows]==list(range(1,len(rows)+1)) and
             all(r['pid']==process['pid'] and r['node']==node and r['generation']==generation for r in rows),
             'full runtime original trace identity')
        need(all(a['localNanos']<=b['localNanos'] for a,b in zip(rows,rows[1:])) and
             process['startNanos']<=rows[0]['localNanos']<=rows[-1]['localNanos']<=process['endNanos'],
             'full runtime process clock')
        need(any(r['event']=='STARTED' for r in rows),'full runtime missing startup')
        for row in rows:row['order']+=generation*1_000_000
        traces[node].extend(rows)
    return traces


def transfer(traces,manifest,node):
    """Complete sender-local snapshot exchange, including chunks and install ACK."""
    completed=[]
    for owner,rows in traces.items():
        offers={};parts={};probes={}
        for row in rows:
            if row['event'] not in ('REQUEST','RECEIVED'):continue
            request=fmt.wire(raw(row['request']),manifest);p=request['payload'];kind=request['type']
            if request['recipient']!=node or kind not in ('AUTHORITY_STATUS_PROBE','SNAPSHOT_OFFER','SNAPSHOT_CHUNK','REJOIN_INSTALL'):continue
            session=(row['pid'],request['epoch'],request['incarnationId'],request['traceId'])
            if kind=='AUTHORITY_STATUS_PROBE':
                if row['event']=='REQUEST':probes[session]=row
                continue
            key=row['pid'],p['transferId']
            if row['event']=='REQUEST':
                if kind=='SNAPSHOT_OFFER':
                    need(session in probes,'full runtime transfer without authority probe')
                    offers.setdefault(key,(row,p,request,probes[session]));parts.setdefault(key,{})
                continue
            response=fmt.wire(raw(row['frame']),manifest)
            if response['type']!=kind:continue
            need(key in offers,'full runtime transfer without offer');begin,offer,binding,probe=offers[key]
            need(all(request[k]==binding[k] for k in ('epoch','incarnationId','proposer','traceId')),'full runtime transfer ballot')
            if kind=='SNAPSHOT_CHUNK':
                chunk=raw(p['chunk']);offset=p['offset']
                need(p['maxChunkBytes']==4096 and 0<len(chunk)<=4096 and response['payload']==dict(p,action='ACK',chunk=''),
                     'full runtime transfer chunk ACK')
                need(offset not in parts[key] or parts[key][offset]==chunk,'full runtime changed transfer chunk');parts[key][offset]=chunk
            elif kind=='REJOIN_INSTALL':
                need(response['payload']==dict(p,response=True),'full runtime install ACK')
                image=b''
                for offset,chunk in sorted(parts[key].items()):
                    need(offset==len(image),'full runtime transfer hole');image+=chunk
                need(len(image)==offer['imageBytes'] and image[16:48].hex()==offer['imageDigest']==p['imageDigest'],
                     'full runtime transfer image')
                snapshot=raw(fmt.contextual_frame(image,'IMAGE',manifest)['snapshot'])
                if len(fmt.inspect(snapshot,'SNAPSHOT')['anchors'])==512:
                    duration=row['localNanos']-begin['localNanos']
                    # The preceding status probe starts before image creation, admission
                    # and the runtime's transfer deadline; this bound includes those costs.
                    need(probe['localNanos']<=begin['localNanos'] and 0<duration<=row['localNanos']-probe['localNanos']<=9_600_000_000,
                         'full runtime whole transfer deadline')
                    installed=[r for r in traces[node] if r['event']=='REJOIN_INSTALLED' and r['transferId']==p['transferId']]
                    need(len(installed)==1 and raw(installed[0]['snapshot'])==snapshot,'full runtime installed transfer identity')
                    completed.append(dict(bytes=len(image),elapsedNanos=duration,owner=owner,recipient=node))
    need(completed,'full runtime missing complete 512 transfer');return completed[0]


def follower_stop(runtime,traces,manifest):
    """Bind the fault target to the original slot-500 publication and selected pair."""
    stop=runtime['followerStop'];leader=stop['leader'];node=runtime['fullTransferNode']
    selected=fmt.contextual_frame(raw(stop['selected']),'SELECTED',manifest)
    pair={b['node'] for b in selected['bases']}
    need(leader==selected['ballot']['proposer'] and leader in pair and len(pair)==2 and
         node in NODES and node not in pair and pair|{node}==set(NODES),'full runtime stopped selected voter')
    processes=[p for p in runtime['processes'] if p['node']==node and p['generation']==stop['generation']]
    need(len(processes)==1 and processes[0]['exitCode']==0 and
         processes[0]['startNanos']<stop['beforeNanos']<processes[0]['endNanos'],'full runtime follower stop lifetime')
    rows=[r for r in traces[leader] if r['generation']==stop['leaderGeneration'] and r['localNanos']<stop['beforeNanos']]
    selections=[r for r in rows if r['event']=='PROMISE_QUORUM']
    need(selections and selections[-1]['selected']==stop['selected'],'full runtime follower stop selection')
    publications=[r for r in rows if r['event']=='PUBLISHED']
    need(publications,'full runtime follower stop publication')
    snapshot=fmt.contextual_frame(raw(publications[-1]['snapshot']),'SNAPSHOT',manifest)
    proof=fmt.contextual_frame(raw(snapshot['terminalProof']),'PROOF',manifest)
    need(len(snapshot['anchors'])==proof['index']==500 and
         {k:proof[k] for k in ('epoch','proposer','incarnation')}==selected['ballot'] and
         {r['voter'] for r in proof['receipts']}==pair,'full runtime follower stop at wrong cut/pair')


def released_recovery(rows,capture,release,projected):
    """Require newer durable authority; a follower need not publish a leader view."""
    for row in rows:
        if row['node']!=capture['node'] or row['localNanos']<=release['localNanos']:continue
        event=row['event']
        if event in ('REJOIN_INSTALLED','PUBLISHED'):
            encoded=raw(row['snapshot']);snapshot=fmt.contextual_frame(encoded,'SNAPSHOT',projected['manifest'])
            state=projection.snapshot(projected,encoded);index=len(snapshot['anchors'])
        elif event=='FORCE' and row['kind']=='PROOF':
            proof=fmt.contextual_frame(raw(row['record']),'PROOF',projected['manifest']);index=proof['index']
            identity=tuple(proof[k] for k in ('epoch','proposer','incarnation','index','entryDigest'))
            voters={r['voter'] for r in proof['receipts']}
            need(projected['chosen'].get(index)==proof['entryDigest'] and
                 voters<=projected['accepted'].get(identity,set()),'full runtime recovery proof lacks exact chosen votes')
            if capture['node'] not in voters or proof['epoch']<=capture['epoch']:continue
            state=projected['states'][index];event='FORCED_PROOF'
        else:continue
        if index>capture['index'] and state.sequence>capture['sequence']:
            return dict(node=capture['node'],event=event,index=index,sequence=state.sequence)
    raise ValueError('full runtime released voter did not recover newer prefix')


def facts(root,runtime,history,traces,location):
    calls=Calls(history,runtime)
    result=physical.automatic(root/'group',history,traces,evidence_location=location,cloud_calls=calls)
    projected=calls.projected;manifest=projected['manifest']
    follower_stop(runtime,traces,manifest)
    need(result['chosen']==512 and all(v['provenIndex']==512 for v in result['retained'].values()),'full runtime 512-slot coverage')
    entry=projected['entries'][calls.active[runtime['uncertainOpId']]['digest']]
    epochs={identity[0] for identity,voters in projected['accepted'].items() if identity[4]==calls.active[runtime['uncertainOpId']]['digest'] and len(voters)>=2}
    need(entry['index']==runtime['chosenAt']==481 and len(epochs)>=2,'full runtime automatic same-slot reproposal')
    pins=[c for c in calls.captures.values() if c['opId']==runtime['pinnedOpId']]
    need(len(pins)==1,'full runtime pinned read coverage');capture,release=pins[0]['captured'],pins[0]['released'];node=capture['node']
    rows=traces[node];inside=lambda r:capture['localNanos']<r['localNanos']<release['localNanos']
    need(any(r['event']=='FORCE' and r['kind']=='PROMISE' and inside(r) and fmt.inspect(raw(r['record']),'PROMISE')['epoch']>capture['epoch'] for r in rows),
         'full runtime pin without higher promise')
    recovered=released_recovery(rows,capture,release,projected)
    need(any(r['event']=='PUBLISHED' and inside(r) and fmt.inspect(raw(r['snapshot']),'SNAPSHOT')['applicationSequence']>capture['sequence']
             for r in traces[runtime['pinMajorityLeader']]),'full runtime pin without majority progress')
    final=[c for c in calls.captures.values() if c['opId']==runtime['finalReadOpId']]
    need(len(final)==1 and final[0]['captured']['index']==512,'full runtime final public read')
    for rows in traces.values():
        for row in rows:
            if row['event'] in ('PUBLISHED','REJOIN_INSTALLED'):projection.snapshot(projected,raw(row['snapshot']))
            if row['event']=='GENERATION_PAIR':
                for snapshot in row['snapshots']:projection.snapshot(projected,raw(snapshot))
    pairs=[r for rows in traces.values() for r in rows if r['event']=='GENERATION_PAIR' and
           len({len(fmt.inspect(raw(s),'SNAPSHOT')['anchors']) for s in r['snapshots']})==2 and
           min(len(fmt.inspect(raw(s),'SNAPSHOT')['anchors']) for s in r['snapshots'])>=480]
    need(pairs,'full runtime near-limit generation overlap')
    terminal=runtime['terminalNode'];selected,prefix=recovery.read_selection(root/'group'/terminal,manifest)
    need(selected is not None and len(prefix['anchors'])==selected['prefixIndex']==512 and selected['nextEntry'] is None,
         'full runtime terminal selected prefix')
    rows=traces[terminal];cuts=[r for r in rows if r['event']=='CUT_REACHED' and r['cut']=='PROMISE_QUORUM']
    need(len(cuts)==1,'full runtime terminal halt coverage');cut=cuts[0]
    selections=[r for r in rows if r['event']=='PROMISE_QUORUM' and r['order']<cut['order'] and fmt.inspect(raw(r['selected']),'SELECTED')==selected]
    need(len(selections)==1,'full runtime actual terminal selection')
    # The remote basis must have been downloaded in this same campaign before selection.
    peer=next(b for b in selected['bases'] if b['node']!=terminal);chunks={};descriptor=None;start=None
    for row in rows:
        if row['pid']!=cut['pid'] or row['order']>=selections[0]['order']:continue
        if row['event']=='SEND_QUEUED' and row['kind']=='PREPARE' and row['peer']==peer['node'] and {k:fmt.inspect(raw(row['ballot']),'PROMISE')[k] for k in ('epoch','proposer','incarnation')}==selected['ballot']:start=row
        if row['event']!='RECEIVED':continue
        message=fmt.wire(raw(row['frame']),manifest);p=message['payload']
        if message['sender']!=peer['node']:continue
        if message['type']=='PROMISE':
            value=fmt.inspect(raw(p['basis']),'BASIS')
            if value['basisId']==peer['basisId']:descriptor=raw(p['basis'])
        if message['type']=='BASIS_CHUNK' and p['basisId']==peer['basisId'] and p['action']=='DATA':
            need(p['maxChunkBytes']==4096,'full runtime basis chunk bound');chunks[p['offset']]=raw(p['chunk'])
    image=b''
    for offset,chunk in sorted(chunks.items()):need(offset==len(image),'full runtime terminal basis hole');image+=chunk
    need(descriptor is not None and descriptor[16:48].hex()==peer['basisDigest'],'full runtime terminal remote descriptor')
    basis=recovery.basis(descriptor,image,manifest);projection.snapshot(projected,raw(fmt.inspect(image,'IMAGE')['snapshot']))
    need(basis[0]['node']==peer['node'] and len(basis[1]['anchors'])==512 and start is not None,'full runtime terminal full basis')
    duration=selections[0]['localNanos']-start['localNanos']
    need(0<duration<=1_200_000_000,'full runtime complete prepare deadline')
    campaigns=[r for r in rows if r['event']=='CAMPAIGN_BEGIN' and r['pid']==cut['pid'] and
               {k:fmt.inspect(raw(r['ballot']),'PROMISE')[k] for k in ('epoch','proposer','incarnation')}==selected['ballot']]
    need(len(campaigns)==1,'full runtime terminal campaign identity')
    campaign_duration=selections[0]['localNanos']-campaigns[0]['localNanos']
    need(0<campaign_duration<=9_600_000_000,'full runtime terminal campaign deadline')
    result.update(reproposalSlot=481,pinnedIndex=capture['index'],releasedRecovery=recovered,
                  fullTransfer=transfer(traces,manifest,runtime['fullTransferNode']),
                  terminalBasisBytes=len(image),terminalPrepareNanos=duration,terminalCampaignNanos=campaign_duration)
    return result


def validate(root,*,traces=None,history=None):
    root=Path(root).resolve();execution=json(root/'execution.json');runtime=json(root/'group/runtime.json');admitted=plan.load(root/'plan.json')
    need(execution['schema']=='gse-v51-full-size-runtime-v1' and execution['status']=='EXECUTED' and
         execution['execution']=='local-public-full-size-runtime' and execution['paidCloud'] is False and execution['fullRemoteQualification'] is False,
         'full runtime scope')
    need(runtime['status']=='EXECUTED' and runtime['paidCloud'] is False and not runtime['cleanupErrors'],'full runtime execution/cleanup')
    location=remote.EvidenceLocation(root,execution['root']);inventory=storage.inventory(root)
    need(len(inventory)<=16000 and sum(v['size'] for v in inventory.values())<=8<<30 and max(v['size'] for v in inventory.values())<=32<<20,
         'full runtime evidence bounds')
    source=json(root/'source-inventory.json');need(m.sha(read(root/'source-inventory.json'))==execution['sourceInventorySha256'],'full runtime source inventory')
    pinned={a['artifact']+'-'+a['version']+'.jar':a['sha256'] for a in admitted['publishedControls']['artifacts']}
    need(set(execution['adapters'])=={'published-v4.4-local','published-v5.0-configured','candidate-v5.1-automatic'},'full runtime adapter set')
    for mode,adapter in execution['adapters'].items():provenance.artifacts(root,mode,adapter,pinned,source)
    backup=semantics.source_backup(root/'source',m.initial(admitted));need(backup==execution['sourceBackup'],'full runtime source backup')
    source_inventory=[dict(path=p,kind=1,**v) for p,v in storage.inventory(root/'source').items()]
    genesis=fmt.inspect(read(root/'group/node-1/genesis.gsr'),'GENESIS')
    need(genesis['sourceDigest']==m.sha(m.canonical(source_inventory)),'full runtime bootstrap source')
    descriptor=m.strict_json(raw(fmt.inspect(read(root/'group/operation/bootstrap-binding.gsr'),'BOOTSTRAP_BINDING')['descriptor']))
    need(descriptor['sourceInventory']==source_inventory and [v['node'] for v in descriptor['replicas']]==list(NODES),'full runtime bootstrap members')
    frozen=cloud.load()
    for replica in descriptor['replicas']:
        need(replica['replicationBounds']==frozen['replicationBounds'] and replica['materialization']['bounds']==
             {k:frozen['application'][k] for k in ('checkpointWalBytes','maxBulkElements','maxDerivedStateBytes','maxDocuments',
                 'maxEncodedDocumentBytes','maxEncodedKeyBytes','maxRetainedBytes')},'full runtime frozen resource limits')
    cp=execution['adapters']['candidate-v5.1-automatic']['cp'];original=Path(execution['root'])
    for label,mode,main,args in [('prepare-source','published-v4.4-local','V51MeasuredLocal',[original,'prepare',original/'plan.json',original/'source']),
            ('bootstrap','candidate-v5.1-automatic','V51MeasuredAutomatic',[original/'group','setup',original/'plan.json',original/'source'])]:
        process=json(root/(label+'.json'))
        need(process['exitCode']==0 and 0<process['endNanos']-process['startNanos']<=90_000_000_000 and
             process['args']==['java',*admitted['jvmArguments'],'-cp',execution['adapters'][mode]['cp'],
                 'io.github.patricklfdm.generalsearch.admission.'+main,*map(str,args)],'full runtime preparation provenance')
    need(len(runtime['processes'])==5,'full runtime owned process count')
    for process in runtime['processes']:
        need(process['args']==['java',*admitted['jvmArguments'],'-cp',cp,'io.github.patricklfdm.generalsearch.replication.V51FullSizeRuntime',
                str(original/'group'),process['node'][-1],str(process['generation'])] and process['exitCode'] in (0,71) and
                process['startNanos']<process['endNanos'],'full runtime process provenance')
    history=history if history is not None else json(root/'group/history.json')
    traces=traces if traces is not None else load_traces(root,runtime)
    return facts(root,runtime,history,traces,location)


def negatives(root):
    # Reject an invalid original before modifying any observations.
    validate(root)
    root=Path(root).resolve();runtime=json(root/'group/runtime.json');execution=json(root/'execution.json')
    history=json(root/'group/history.json');traces=load_traces(root,runtime);results=[]
    location=remote.EvidenceLocation(root,execution['root'])
    def reject(name,reason,edit):
        changed={n:[dict(r) for r in rows] for n,rows in traces.items()};calls=copy.deepcopy(history)
        edit(changed,calls)
        try:facts(root,runtime,calls,changed,location)
        except ValueError as error:
            need(str(error)==reason,'unrelated full runtime negative: '+name+': '+str(error))
            results.append(dict(case=name,status='REJECTED',reason=reason));return
        raise ValueError('full runtime mutation accepted: '+name)
    def answer(rows,calls):
        op=runtime['pinnedOpId'];call=next(c for c in calls if c['opId']==op)
        call['documents'][0][1]='changed'
        row=next(r for own in rows.values() for r in own if r['event']=='CLIENT_RESULT' and r['opId']==op)
        row['documents']=call['documents']
    reject('changed-pinned-answer','full runtime captured answer',answer)
    def release(rows,calls):
        row=next(r for own in rows.values() for r in own if r['event']=='READ_RELEASED');row['index']+=1
    reject('changed-read-cut','full runtime changed read release',release)
    def early(rows,calls):
        row=next(r for own in rows.values() for r in own if r['event']=='CLIENT_RESULT' and r['kind']=='read' and r['outcome']=='SUCCESS')
        own=rows[row['node']];invoke=next(r for r in own if r['event']=='CLIENT_INVOKE' and r['opId']==row['opId']);row['order']=invoke['order']+1
    reject('early-read-response','full runtime result before read release',early)
    def crash(rows,calls):next(c for c in calls if c['opId']==runtime['uncertainOpId'])['outcome']='SUCCESS'
    reject('invented-crash-response','full runtime invented crash response',crash)
    def generations(rows,calls):
        for own in rows.values():
            for r in own:
                if r['event']=='GENERATION_PAIR':r['event']='OMITTED'
    reject('missing-generation-overlap','full runtime near-limit generation overlap',generations)
    def selected(rows,calls):
        own=rows[runtime['terminalNode']];terminal=next(r for r in own if r['event']=='CUT_REACHED' and r['cut']=='PROMISE_QUORUM')
        prior=max((r for r in own if r['event']=='PROMISE_QUORUM' and r['order']<terminal['order']),key=lambda r:r['order']);prior['event']='OMITTED'
    reject('missing-terminal-selection','full runtime actual terminal selection',selected)
    def prepare(rows,calls):
        own=rows[runtime['terminalNode']];terminal=next(r for r in own if r['event']=='CUT_REACHED' and r['cut']=='PROMISE_QUORUM')
        prior=max((r for r in own if r['event']=='PROMISE_QUORUM' and r['order']<terminal['order']),key=lambda r:r['order']);prior['localNanos']+=1_200_000_000
    reject('late-complete-prepare','full runtime complete prepare deadline',prepare)
    def identity(rows,calls):
        next(r for own in rows.values() for r in own if r['event']=='PUBLIC_READ_INVOKE')['opId']='unowned'
    reject('unowned-read','full runtime read identity',identity)
    def invocation(rows,calls):
        next(r for own in rows.values() for r in own if r['event']=='CLIENT_INVOKE')['pid']+=1
    reject('changed-call-process','full runtime unowned invocation',invocation)
    def mutate(rows,calls):
        next(c for c in calls if c['kind']=='update')['revision']+=1
    reject('changed-update-request','full runtime mutation schedule',mutate)
    def late_transfer(rows,calls):
        target=next(r for r in rows[runtime['fullTransferNode']] if r['event']=='REJOIN_INSTALLED' and
                    len(fmt.inspect(raw(r['snapshot']),'SNAPSHOT')['anchors'])==512)
        encoded=read(root/'group/node-1/manifest.gsr');manifest=dict(fmt.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
        for own in rows.values():
            for row in own:
                if row['event']!='RECEIVED':continue
                message=fmt.wire(raw(row['frame']),manifest)
                if message['type']=='REJOIN_INSTALL' and message['payload']['transferId']==target['transferId']:
                    row['localNanos']+=9_600_000_000;return
        raise ValueError('missing full-size transfer negative target')
    reject('late-complete-transfer','full runtime whole transfer deadline',late_transfer)
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(m.canonical(validate(a.root)).decode())
