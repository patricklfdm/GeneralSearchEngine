"""Replay a complete native single-campaign three-owner competition.

Role observations come from original SELECTED bytes, then every state is derived
from admitted bootstrap, original grants, votes and publication. Producer status
is diagnostic, never a vote, floor, completion or readiness authority.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import authority_transition_evidence as t
from . import peer_observation_evidence as observation
from . import discovered_selection_evidence as exchange
from . import election_wait_evidence as wait

n,b,c,e,f,need = t.d,t.b,t.c,t.e,t.f,t.need

# Instrumentation vocabulary only: a recognized name never supplies authority.
# Original-state and per-phase force/dependency checks remain mandatory.
OWNER_POINTS = frozenset("""
ACCEPT_ACK_BEFORE_RETURN ACCEPT_ACTIVE_FORCED ACCEPT_ACTIVE_PARENT_FORCED
ACCEPT_BEFORE_RETURN ACCEPT_CANDIDATE_CREATED ACCEPT_CANDIDATE_FORCED
ACCEPT_CANDIDATE_PARENT_FORCED ACCEPT_CANDIDATE_WRITTEN ACCEPT_PARENT_FORCED
ACCEPT_PREFIX_WRITTEN ACCEPT_RENAMED ACCEPT_VALIDATED
ALLOCATOR_BEFORE_RETURN ALLOCATOR_BEFORE_WRITE ALLOCATOR_CREATED
ALLOCATOR_DIRECTORY_FORCED ALLOCATOR_FORCED ALLOCATOR_RENAMED
ALLOCATOR_WRITTEN APPLICATION_ACK_BEFORE_RETURN APPLICATION_AUTHORITY_VALIDATED
APPLY_ACK_CREATED APPLY_ACK_DIRECTORY_FORCED APPLY_ACK_FORCED
APPLY_ACK_PREFIX_WRITTEN APPLY_ACK_WRITTEN APPLY_BEFORE_RETURN
APPLY_DIRECTORY_CREATED APPLY_END_FORCED APPLY_IMAGE_CREATED
APPLY_IMAGE_FORCED APPLY_IMAGE_PREFIX_WRITTEN APPLY_IMAGE_WRITTEN
APPLY_METADATA_CREATED APPLY_METADATA_FORCED APPLY_METADATA_PREFIX_WRITTEN
APPLY_METADATA_WRITTEN APPLY_PARENT_ACK_CREATED APPLY_PARENT_ACK_FORCED
APPLY_PARENT_ACK_PREFIX_WRITTEN APPLY_PARENT_ACK_WRITTEN APPLY_PARENT_STATEMENT_CREATED
APPLY_PARENT_STATEMENT_FORCED APPLY_PARENT_STATEMENT_PREFIX_WRITTEN APPLY_PARENT_STATEMENT_WRITTEN
APPLY_PLAN_CREATED APPLY_PLAN_FORCED APPLY_PLAN_PREFIX_WRITTEN
APPLY_PLAN_WRITTEN APPLY_VALIDATED BASIS_BEFORE_WRITE
BASIS_FORCED BASIS_PREFIX_WRITTEN BASIS_WRITTEN
CAPTURE_INTENT_CLEARED CAPTURE_INTENT_CREATED CAPTURE_INTENT_DELETED
CAPTURE_INTENT_FORCED CAPTURE_INTENT_PARENT_FORCED CAPTURE_INTENT_PREFIX_WRITTEN
CAPTURE_INTENT_WRITTEN CERTIFICATE_ACTIVE_FORCED CERTIFICATE_ACTIVE_PARENT_FORCED
CERTIFICATE_BEFORE_RETURN CERTIFICATE_CANDIDATE_CREATED CERTIFICATE_CANDIDATE_FORCED
CERTIFICATE_CANDIDATE_PARENT_FORCED CERTIFICATE_CANDIDATE_WRITTEN CERTIFICATE_PARENT_FORCED
CERTIFICATE_PREFIX_WRITTEN CERTIFICATE_RENAMED CERTIFICATE_VALIDATED
COVERED_END_BEFORE_DELETE COVERED_END_BEFORE_DIRECTORY_DELETE COVERED_END_DIRECTORY_DELETED
COVERED_END_FILE_DELETED COVERED_END_VALIDATED COVERED_VOTE_CANDIDATE_CREATED
COVERED_VOTE_CANDIDATE_FORCED COVERED_VOTE_CANDIDATE_PARENT_FORCED COVERED_VOTE_CANDIDATE_WRITTEN
COVERED_VOTE_PARENT_FORCED COVERED_VOTE_PREFIX_WRITTEN COVERED_VOTE_RENAMED
CURRENT_BEFORE_CAPTURE CURRENT_DIRECTORY_FORCED CURRENT_FILES_FORCED
CURRENT_GENERATION_FORCED CURRENT_SELECTOR_FORCED CURRENT_VALIDATED
FLOOR_AUTHORITY_FORCED FLOOR_AUTHORITY_WRITTEN FLOOR_BEFORE_RETURN
FLOOR_COPIES_FORCED FLOOR_COPY_BEFORE_RETURN FLOOR_COPY_CREATED
FLOOR_COPY_DIRECTORY_FORCED FLOOR_COPY_HANDED_OFF FLOOR_DIRECTORY_CREATED
FLOOR_IMAGE_FORCED FLOOR_IMAGE_WRITTEN FLOOR_MANIFEST_FORCED
FLOOR_MANIFEST_WRITTEN FLOOR_MEMBER_FORCED FLOOR_MEMBER_WRITTEN
FLOOR_PARENT_FORCED FLOOR_PROPOSAL_FORCED FLOOR_PROPOSAL_WRITTEN
FLOOR_RELEASE_AUTHORITY_CLEARED FLOOR_RELEASE_AUTHORITY_CREATED FLOOR_RELEASE_AUTHORITY_FORCED
FLOOR_RELEASE_AUTHORITY_WRITTEN FLOOR_RELEASE_BEFORE_RETURN FLOOR_RELEASE_CLEARED
FLOOR_RELEASE_COPY_DELETED FLOOR_RELEASE_FILE_DELETED FLOOR_RELEASE_PARENT_FORCED
FLOOR_RELEASE_PROPOSAL_CLEARED FLOOR_RELEASE_RELINQUISHED FLOOR_RESERVED
FUTURE_RETENTION_ACK_BEFORE_RETURN FUTURE_RETENTION_BEFORE_RETURN FUTURE_RETENTION_BEFORE_WRITE
FUTURE_RETENTION_CANDIDATE_PARENT_FORCED FUTURE_RETENTION_CLEARED FUTURE_RETENTION_FORCED
FUTURE_RETENTION_PARENT_FORCED FUTURE_RETENTION_PREFIX_WRITTEN FUTURE_RETENTION_PROMOTED
FUTURE_RETENTION_RECOVERY_FORCED FUTURE_RETENTION_RECOVERY_PARENT_FORCED FUTURE_RETENTION_RENAMED
FUTURE_RETENTION_WRITTEN GRANT_BEFORE_RETURN INSTALL_BEFORE_RETURN
INSTALL_DIRECTORY_CREATED INSTALL_GENERATION_FORCED INSTALL_IMAGE_FORCED
INSTALL_IMAGE_WRITTEN INSTALL_MANIFEST_FORCED INSTALL_MANIFEST_WRITTEN
INSTALL_MEMBER_FORCED INSTALL_MEMBER_WRITTEN INSTALL_PARENT_FORCED
INSTALL_RESERVED INSTALL_SELECTOR_FORCED INSTALL_SELECTOR_RENAMED
INSTALL_SELECTOR_WRITTEN NATIVE_CERTIFICATE_RETAINED NODE_OPEN
PROMISE_BEFORE_WRITE PROMISE_FORCED PROMISE_WRITTEN
PROOF_ACK_BEFORE_RETURN PROOF_BEFORE_RETURN PROOF_CANDIDATE_CREATED
PROOF_CANDIDATE_FORCED PROOF_CANDIDATE_PARENT_FORCED PROOF_CANDIDATE_WRITTEN
PROOF_PARENT_FORCED PROOF_PREFIX_WRITTEN PROOF_RENAMED
PROOF_VALIDATED PUBLICATION_ACK_BEFORE_RETURN PUBLICATION_BEFORE_RETURN
PUBLICATION_COVERAGE_VALIDATED PUBLICATION_RETIRED PUBLICATION_SELECTOR_FORCED
PUBLICATION_VALIDATED REPLAY_APPLICATION_FINISHED REPLAY_BEFORE_APPLICATION
REPLAY_BEFORE_DELETE REPLAY_BEFORE_RETURN REPLAY_CLAIM_CREATED
REPLAY_CLAIM_FORCED REPLAY_CLAIM_PREFIX_WRITTEN REPLAY_CLAIM_WRITTEN
REPLAY_DELETED REPLAY_DIRECTORY_CREATED REPLAY_RESERVED
RETENTION_BEFORE_WRITE RETENTION_CANDIDATE_PARENT_FORCED RETENTION_FORCED
RETENTION_PARENT_FORCED RETENTION_PREFIX_WRITTEN RETENTION_RECOVERY_ACTIVE_FORCED
RETENTION_RECOVERY_PARENT_FORCED RETENTION_RENAMED RETENTION_WRITTEN
RETIREMENT_AUTHORITY_CLEARED RETIREMENT_AUTHORITY_FORCED RETIREMENT_AUTHORITY_WRITTEN
RETIREMENT_BEFORE_RETURN RETIREMENT_CLEARED RETIREMENT_CREATED
RETIREMENT_DELETE_VALIDATED RETIREMENT_DIRECTORY_DELETED RETIREMENT_FILE_DELETED
RETIREMENT_IMAGE_FORCED RETIREMENT_IMAGE_WRITTEN RETIREMENT_MANIFEST_FORCED
RETIREMENT_MANIFEST_WRITTEN RETIREMENT_MEMBER_FORCED RETIREMENT_MEMBER_WRITTEN
RETIREMENT_OLD_FILES_FORCED RETIREMENT_PARENT_FORCED RETIREMENT_PROPOSAL_CLEARED
RETIREMENT_PROPOSAL_FORCED RETIREMENT_PROPOSAL_WRITTEN RETIREMENT_RESERVED
RETIREMENT_SAVED_DIRECTORY_DELETED RETIREMENT_SAVED_FILE_DELETED RETIREMENT_SOURCE_CREATED
RETIREMENT_SOURCE_FORCED SELECTED_BEFORE_RETURN SELECTED_BEFORE_WRITE
SELECTED_FORCED SELECTED_WRITTEN SOURCE_BEFORE_CREATE
SOURCE_CREATED SOURCE_DIRECTORY_FORCED SOURCE_FILES_DIRECTORY_FORCED
SOURCE_IMAGE_CREATED SOURCE_IMAGE_FORCED SOURCE_IMAGE_PREFIX_WRITTEN
SOURCE_IMAGE_WRITTEN SOURCE_PACKET_CREATED SOURCE_PACKET_FORCED
SOURCE_PACKET_PREFIX_WRITTEN SOURCE_PACKET_WRITTEN
SOURCE_RETIREMENT_CREATED SOURCE_RETIREMENT_WRITTEN SOURCE_RETIREMENT_FORCED
SOURCE_RETIREMENT_PARENT_FORCED SOURCE_RETIREMENT_JOURNAL_PRUNED
SOURCE_RETIREMENT_FILE_DELETED SOURCE_RETIREMENT_DIRECTORY_DELETED
SOURCE_RETIREMENT_CLEARED SOURCE_RETIREMENT_BEFORE_RETURN
JOURNAL_ROTATION_CREATED JOURNAL_ROTATION_WRITTEN JOURNAL_ROTATION_FORCED
JOURNAL_ROTATION_RENAMED JOURNAL_ROTATION_PARENT_FORCED
""".split())


def inventory(root):
    exchange.inventory(root)
    extras = {'grant-captures', 'grant-capture-events.json'}
    present = extras & {v.name for v in root.iterdir()}
    need(not present or present == extras, 'competing complete grant capture attachments')
    b.selection.layout(root, {'initial','original-plan.gsbp','original-application.image','before-network',
        'after-close','calls.json','events.json','wire.json','failure.txt','close-failure.txt','result.json',
        'diagnostics.json','observations.json','drain-scratch','drains.json'} | present, 'competing original history')


def record(row, family, kind):
    raw=base64.b64decode(row['bytes'],validate=True)
    need(e.digest(raw)==row['record'], 'competing original event digest')
    return raw,f.decode(raw,family,kind)


def trace(root):
    rows=n.read(root/'events.json');need(type(rows) is list and 0<len(rows)<32768,'competing bounded events')
    last=-1;events=[]
    for row in rows:
        need(type(row) is dict and type(row.get('nanoTime')) is int and row['nanoTime']>=last
             and row.get('node') in c.NODES and type(row.get('event')) is str,'competing monotonic owned events')
        point=row['event']
        need(point in OWNER_POINTS or point in ('NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE')
             or point.startswith(('ROUND_','SLOT_')), 'competing unknown owner event')
        if point in OWNER_POINTS:need(set(row)=={'node','event','nanoTime'},'competing owner event shape')
        last=row['nanoTime'];events.append({k:v for k,v in row.items() if k!='nanoTime'})
    return events


def maintenance(group,voters):
    result=copy.deepcopy(group)
    for node in voters:
        prefix=c.current(group[node])[0]
        result[node]={k:v for k,v in result[node].items() if not k.startswith('generations/') or k==prefix[:-1] or k.startswith(prefix)}
        for peer in (node,*[v for v in voters if v!=node]):
            result[node][n.s.FILE]=observation.observe_same_cut(result[node][n.s.FILE],group[node],group[peer])
    return result


class History(t.NativeSlot):
    def __init__(self,root,group,selected,events):
        self.root=root;self.group=copy.deepcopy(group);self.proposer=selected['ballot']['proposer']
        self.voters=tuple(v['voter'] for v in selected['sources']);self.active=list(self.voters)
        self.slot=0;self.counter=selected['ballot']['counter'];self.first=None;self.documents=[]
        self.required=set();self.observed=set();self.phases={};self.events=events;self.snapshots={}
        self.history=f.decode(group[self.proposer]['root.gsr'],'records','ROOT')['historyId']

    def requested(self,index,entry,payload):
        rows=[v for v in self.events if v['event']=='ROUND_SLOT_BEGIN']
        need(len(rows)==2 and rows[index-1]['node']==self.proposer
             and record(rows[index-1],'records','ENTRY')[0]==entry,'competing exact client entry')
        self.entry=entry

    def data_documents(self):return [(100,'competing-node-100')]

    def application_image(self,index,nodes):
        if index==1:
            _,members,packet=c.current(self.group[self.proposer]);return members[packet['capsule']['application']+'.image']
        _,members,packet=c.current(c.inventory(self.root/'after-close'/self.proposer))
        return members[packet['capsule']['application']+'.image']

    def checkpoint_voters(self,view,node):return set(self.voters)

    def snapshot(self,label,group):
        if label.endswith('-applied'):self.applied=copy.deepcopy(group)
        elif label.endswith('-published'):self.publication_group(group)
        self.snapshots[label]=copy.deepcopy(group)

    def advance(self,kind):
        self.snapshots[f'before-{self.slot+1}']=copy.deepcopy(self.group)
        self.group=maintenance(self.group,self.voters)
        self.snapshots[f'maintained-{self.slot+1}']=copy.deepcopy(self.group)
        text=b'100:competing-node-100'
        payload=b'\x01'+struct.pack('>HIII',1,1,4,100)+struct.pack('>I',len(text))+text if kind=='DATA' else None
        self.publish(kind,payload)


def physical(root,events):
    group=n.s.initialize(b.original(root,3,False))
    group={node:dict(files,**{n.future.FILE:n.future.frame(n.future.initial(files),{})}) for node,files in group.items()}
    b.match(root,'before-network',group)
    rows=[v for v in events if v['event']=='ROUND_INSTALLED']
    need(len(rows)==1,'competing one original campaign')
    chosen,selected=record(rows[0],'records','SELECTED');leader=selected['ballot']['proposer'];voters=[v['voter'] for v in selected['sources']]
    need(leader in group and rows[0]['node']==leader and len(voters)==2 and voters==sorted(set(voters))
         and leader in voters and set(voters)<=set(group),'competing original selected majority')
    prepared,_,installed=n.s.campaign(root,{v:group[v] for v in voters},2,'after-close',selected_prefix=n.slot.prefix,proposer=leader)
    need(chosen==c.current(installed[leader])[1]['selected.gsr'],'competing original selection')
    history=History(root,dict(group,**installed),selected,events)
    history.initial=group;history.prepared=dict(group,**prepared);history.installed=copy.deepcopy(history.group)
    history.selected=selected;history.chosen=chosen
    history.advance('BARRIER');history.advance('DATA');b.match(root,'after-close',history.group)
    return history


def completion(history,index):
    files=history.snapshots[f'slot-{index}-published'][history.proposer];prefix,_,packet=c.current(files)
    certificate=history.snapshots[f'slot-{index}-applied'][history.proposer]['applied-end/certificate.gsr']
    return dict(certificate=e.digest(certificate),selection=e.digest(history.chosen),published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr']))


def completion_lifecycle(root,history,events):
    """Client/slot observations shared after independently derived activation."""
    leader=history.proposer;held=[(i,v) for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    need([v['event'] for _,v in held]==['ROUND_'+v for v in ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY','SLOT_BEGIN','SLOT_COMPLETE']],
         'competing exact round lifecycle')
    identity=n.future.identity(history.initial[leader]);acks={}
    for index,ordinal in ((1,2),(2,5)):
        raw,ack=record(held[ordinal][1],'wire','PUBLISH_ACK')
        need(ack==dict(root=history.selected['root'],view=history.selected['view'],ballot=history.selected['ballot'],sender=identity,
                       recipient=identity,trace=ack['trace'],sequence=1,payload=completion(history,index)), 'competing original completion')
        acks[index]=raw
    need(record(held[3][1],'wire','PUBLISH_ACK')[0]==acks[1],'competing readiness after original barrier')
    need(all(set(v)=={'node','event','record','bytes'} and v['node']==leader for _,v in held),'competing round owner')
    need(sum(v['event'].startswith('SLOT_') for v in events)==6,'competing exact slot hook inventory')
    for index,(lower,upper) in enumerate(((held[1][0],held[2][0]),(held[4][0],held[5][0])),1):
        marked=[v for v in events[lower:upper] if v['event'].startswith('SLOT_')]
        cert=history.snapshots[f'slot-{index}-applied'][leader]['applied-end/certificate.gsr']
        need([v['event'] for v in marked]==['SLOT_APPLIED','SLOT_FUTURE_QUORUM_COMPLETE','SLOT_PUBLISHED']
             and all(set(v)=={'node','event','record','bytes','voters'} and v['node']==leader and v['voters']==list(history.voters)
                     and record(v,'records','CERTIFICATE')[0]==cert for v in marked),'competing original slot hooks')
    observations=n.read(root/'observations.json')
    need(observations==[dict(node=leader,event=kind,bytes=base64.b64encode(acks[index]).decode())
                        for kind,index in [('START_COMPLETED',1),('DATA_COMPLETED',2)]],'competing original client observations')
    opened=[v for v in events if v['event']=='NODE_OPEN']
    need(opened==[dict(node=v,event='NODE_OPEN') for v in sorted(history.initial)],'competing all owners opened')
    before=[v for v in events[:events.index(opened[-1])+1] if v['event']!='NODE_OPEN']
    wait.lifecycle(n.read(root/'calls.json'),before,history.initial)
    return held


def lifecycle(root,history,events):
    held=completion_lifecycle(root,history,events)
    opened=[v for v in events if v['event']=='NODE_OPEN']
    unused=next(v for v in history.initial if v not in history.voters)
    need(all(v['event'] in ('NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE')
             for v in events[events.index(opened[-1])+1:] if v['node']==unused), 'competing unselected owner remains nonwriting')
    return held


def cleanup(root,history):
    need((root/'failure.txt').read_bytes()==(root/'close-failure.txt').read_bytes()==b'', 'competing retained execution failure')
    need(n.read(root/'result.json')==dict(status='PARTIAL',producerPassed=True,nodes=3,automaticOwners=3,defaultBounds=True,
         physicalReplay=False,phase3Complete=False),'competing producer scope')
    need(n.read(root/'diagnostics.json')==[dict(node=v,state='READY' if v==history.proposer else 'STARTING',rounds=1,losses=[],failure='')
         for v in sorted(history.initial)],'competing diagnostic scope')
    scratch(root,history,{history.proposer})


def scratch(root,history,outgoing):
    """Exact drained original owners; caller derives which owners campaigned."""
    need(type(outgoing) is set and history.proposer in outgoing and outgoing<=set(history.initial),
         'competing scratch outgoing owners')
    drains=n.read(root/'drains.json');nodes=sorted(history.initial,reverse=True)
    need(type(drains) is list and [v.get('node') for v in drains]==nodes,'competing drain owners')
    b.selection.layout(root/'drain-scratch',set(nodes),'competing scratch owners')
    paths=set();keys=set()
    for row in drains:
        node=row['node'];roles=['incoming','outgoing'] if node in outgoing else ['incoming']
        files=c.inventory(root/'drain-scratch'/node)
        need(set(files)=={v for role in roles for v in (role,role+'/owner.json',role+'/scope.lock')}
             and all(files[role] is None and files[role+'/scope.lock']==b'' for role in roles), 'competing exact drained scratch')
        expected=sorted([dict(path=k,bytes=len(v),sha256=e.digest(v)) for k,v in files.items() if v is not None],key=lambda v:v['path'])
        need(set(row)=={'node','failure','leases','files'} and row['failure']=='' and type(row['leases']) is int and row['leases']==0
             and sorted(row['files'],key=lambda v:v['path'])==expected,'competing exact drain receipt')
        for role in roles:
            value=json.loads(files[role+'/owner.json']);parent=value.get('parent',{})
            need(set(value)=={'schema','root','identity','role','parent','directoryKey'} and value['schema']=='gse-v53-derived-scratch-v1'
                 and value['root']==history.selected['root'] and value['identity']==n.future.identity(history.initial[node])
                 and value['role']==role.upper(),'competing scratch identity')
            need(set(parent)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'}
                 and all(type(v) is str and v for v in parent.values()) and Path(parent['path']).is_absolute()
                 and str(Path(parent['path']).parent)==parent['parentRealPath'] and Path(parent['path']).name==role
                 and type(value['directoryKey']) is str and value['directoryKey'],'competing original scratch path')
            need(parent['path'] not in paths and value['directoryKey'] not in keys,'competing distinct scratch ownership')
            paths.add(parent['path']);keys.add(value['directoryKey'])


def validate(root):
    from . import competing_node_network as network
    root=Path(root);inventory(root);events=trace(root);history=physical(root,events);held=lifecycle(root,history,events)
    checked=network.validate(root,history,events,held);cleanup(root,history)
    result = dict(status='PASS',scope='single-campaign-three-native-owners',physicalReplay=True,fullWireReplay=True,
        proposer=history.proposer,selected=list(history.voters),slots=2,clientMutations=1,network=checked,
        originalFirst=True,scratchTransfersDrained=True,processDeath=False,publicRuntime=False,phase3Complete=False)
    if (root/'grant-capture-events.json').exists():
        from . import competing_grant_captures as captures
        result['grantCollection'] = captures.validate(root)
    return result


def qualify(root):
    from .competing_node_negatives import CASES,mutate
    root=Path(root);original=validate(root);results=[]
    leader=original['proposer'];peer=next(v for v in original['selected'] if v!=leader);unused=next(v for v in c.NODES if v not in original['selected'])
    for name,reason in CASES.items():
        reason=reason.format(leader=leader,peer=peer,unused=unused)
        with tempfile.TemporaryDirectory(prefix='v53-competing-negative-') as temp:
            dest=Path(temp)/'raw';shutil.copytree(root,dest);mutate(dest,name)
            try:validate(dest)
            except ValueError as error:need(str(error)==reason,'competing unrelated negative '+name+': '+str(error))
            else:raise ValueError('competing mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
