"""Replay original owner files after an explicitly conditional SEALED prefix.

This is a storage continuation oracle, not historical learner authority or a
whole-group runtime/resource qualification. The caller must name the profile;
a short smoke can never stand in for the fixed operation-231 boundary.
"""
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import admitted_cross_view_evidence as cross
from . import publication_capacity_evidence as refusal
from .offline_fixture_image import application
from .selected_sources_evidence import cuts

e,c,b,selection=cross.e,cross.c,cross.b,cross.selection
read,same=cross.read,cross.same
PROFILES={'capacity-231':231,'replay-smoke-1':1}
NODES=['node-1','node-2','node-3']
HISTORY='11111111-2222-3333-4444-555555555555'
INITIAL_INDEXES=((3,'value',''),(2,'id',''))
FINAL_INDEXES=((2,'id',''),(3,'value',''))
CRITICAL={
    'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
    'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
    'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
    'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
    'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN'],
    'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
    'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
    'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
}


def receipt(profile):
    e.need(profile in PROFILES,'completion explicit profile');number=PROFILES[profile]
    return dict(schema='gse-v53-capacity-completion-v2',status='PASS',profile=profile,completedOperation=number,
                nextOperationRefused=number+1 if number==231 else None,applicationSequence=42,nodes=3,
                conditionalPrefix=True,freshProcesses=False,nativeNetwork=False,phase3Complete=False)


class Walk(cross.Walk):
    def __init__(self,root,profile):
        self.root=Path(root);self.number=PROFILES[profile];self.required={'sealed','stopped','calls.json','observations.json','receipt.json'}
        selection.layout(self.root/'sealed',set(NODES),'completion conditional owners')
        self.group={n:c.inventory(self.root/'sealed'/n) for n in NODES}
        self.active=NODES;self.slot=7*self.number-2;self.counter=3;self.first=None;self.observed=set();self.phases={}
        self.documents=[(7,'old'),(2,'retained')];self.history=HISTORY
        members,packet,cap,state=self.state();root_record=e.f.decode(self.group[NODES[0]]['root.gsr'],'records','ROOT')
        e.need(self.group[NODES[0]]['root.gsr'][16:48].hex()==cap['root'] and
               e.digest(self.group[NODES[0]]['root.gsr']) in packet['objects'] and
               root_record['historyId']==HISTORY and root_record['baseSequence']==41,'completion conditional application identity')
        e.need(cap['cut']['index']==self.slot and cap['cut']['view']['generation']==self.number-1 and
               cap['cut']['view']['operation'] is None and len(cap['items'])==3*self.number-2 and
               state['active']==self.number and state['nextOperation']==self.number+1 and state['retiredThrough']==self.number-1 and
               state['applicationSequence']==41 and len(state['results'])==1 and
               state['results'][0]['request']['number']==self.number and state['results'][0]['phase']=='SEALED',
               'completion fixed conditional prefix')
        application(members[cap['application']+'.image'],HISTORY,41,self.documents,expected_indexes=INITIAL_INDEXES)
        for n,files in self.group.items():
            _,local,original=c.current(files);identity=e.f.decode(files['node.gsr'],'records','NODE',cap['root'])['identity']
            e.need(original['capsuleBytes']==packet['capsuleBytes'] and local['source.gscp']==members['source.gscp'] and
                   files['root.gsr']==self.group[NODES[0]]['root.gsr'] and files['genesis.gsr']==packet['objects'][root_record['genesis']] and
                   identity['node']==n and identity in root_record['initial'] and files['pending.accept']==c.EMPTY,
                   'completion conditional owner binding')
            rows=c.journal(files['grants.gsr'],cap['root'],n)
            e.need([v[0] for v in rows]==['PROMISE','BASIS','SELECTED'] and
                   all(local[k.lower()+'.gsr']==raw for k,raw,_ in rows),'completion conditional grant binding')
            promise,basis,selected=[v[2] for v in rows];identifier=basis['basisId']
            ballot=dict(counter=3,proposer='node-1',incarnation=root_record['initial'][0]['storage'])
            e.need(promise['ballot']==basis['ballot']==selected['ballot']==ballot and
                   promise['view']==basis['view']==selected['view']==e.authority(cap['root'],cap['cut']['view']) and
                   basis['cut']==selected['cut']==cap['cut'] and selected['nextEntry'] is None and
                   files['sources/'+identifier+'/source.gscp']==local['source.gscp'], 'completion conditional selection')
            c.p.bind(original,local['basis.gsr'])
            same(cuts(local['selected-sources.gsr'],selected),[cap['cut']]*3,'completion conditional selected sources')
            same(e.f.decode(files['allocator.gsr'],'records','ALLOCATOR'),dict(root=cap['root'],node=n,counter=0),'completion initial allocator')
        e.need(b.settled(self.group)==self.group,'completion initial settled owners')

    def data_documents(self):return self.documents+[(21,'admitted-completion')]

    def requested(self,slot,entry,payload):
        for name,data in ((f'entry-{slot}.gsr',entry),(f'payload-{slot}.bin',payload)):
            self.required.add(name)
            e.need(b.t.plans.read(self.root/name,8*e.MIB)==data,'cross-view requested command')

    def application_image(self,slot,nodes):
        return b.t.plans.read(self.root/f'slot-{slot}-applied'/nodes[0]/'applied-end/application.image',64*e.MIB)

    def verify_application(self,image,sequence,documents):
        application(image,self.history,sequence,documents,expected_indexes=FINAL_INDEXES)

    def refused(self):
        self.required|={'refusal','refused-entry.gsr','refused-payload.bin'}
        selection.layout(self.root/'refusal',set(NODES),'completion refusal owners')
        _,_,cap,state=self.state()
        def identity(number):
            return dict(node='node-'+str(number),storage=f'00000000-0000-0005-0000-{number:012x}',host='127.0.0.1',port=19000+number)
        target=sorted([identity(i) for i in [1,2,3,4,self.number+6]],key=lambda v:v['node'])
        payload=e.f.canonical(dict(request=dict(root=cap['root'],expected=e.authority(cap['root'],cap['cut']['view']),number=self.number+1,kind='REPLACE',target=target)))
        ballot=e.f.decode(self.state()[0]['selected.gsr'],'records','SELECTED')['ballot']
        entry=e.f.encode('records','ENTRY',dict(root=cap['root'],authority=e.authority(cap['root'],cap['cut']['view']),index=self.slot+1,
                                             previous=cap['cut']['entry'],origin=ballot,kind='RESERVE',payload=e.digest(payload)))
        e.need(b.t.plans.read(self.root/'refused-entry.gsr',8192)==entry and
               b.t.plans.read(self.root/'refused-payload.bin',8192)==payload,'completion refused command')
        for n in NODES:
            path=self.root/'refusal'/n;refusal.validate_voter(path)
            e.need(c.inventory(path/'before')==self.group[n],'completion refusal original parent')


def validate(root,profile):
    root=Path(root);expected=receipt(profile)
    e.need(root.is_dir() and not root.is_symlink(),'completion original root')
    same(read(root/'receipt.json'),expected,'completion receipt/profile')
    w=Walk(root,profile);operation=w.state()[3]['results'][0]
    w.publish('INTENT',dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}));w.campaign()
    w.publish('FINAL',dict(binding=operation['binding']));w.campaign()
    w.publish('BARRIER');w.publish('RETIRE',dict(through=w.number))
    if profile=='capacity-231':w.refused()
    value=b'21:admitted-completion';payload=b'\x01'+struct.pack('>HIII',1,1,4,21)+struct.pack('>I',len(value))+value
    w.publish('DATA',payload);w.snapshot('stopped',w.group)
    observed=read(root/'observations.json')
    e.need(len(observed)==len(w.observed) and {e.f.canonical(v) for v in observed}==w.observed,'completion exact observations')
    calls=read(root/'calls.json');validate_calls(calls,w.phases)
    selection.layout(root,w.required,'completion history')
    return dict(status='PASS',profile=profile,slots=5,owners=3,campaigns=2,callObservations=len(calls),ownedObservations=len(observed),
                conditionalPrefix=True,originalFirst=True,capacityBoundary=profile=='capacity-231',freshProcesses=False,nativeNetwork=False,phase3Complete=False)


def validate_calls(calls,phases):
    coverage=[dict(operation=label,node=n) for label,nodes in phases.items() for n in nodes]
    e.need(all(set(v)=={'operation','node','events'} for v in calls) and
           [{k:v[k] for k in ('operation','node')} for v in calls]==coverage,'completion exact call coverage')
    for call in calls:
        required=CRITICAL[call['operation'].rsplit('-',1)[0]]
        e.need(isinstance(call['events'],list) and all(isinstance(v,str) for v in call['events']) and
               [v for v in call['events'] if v in set(required)]==required,'completion force before return')


VARIANTS={
    'profile':'completion receipt/profile',
    'accept':'admitted exact slot-{first}-accepted: node-1',
    'proof':'admitted exact slot-{first}-proved: node-1',
    'certificate':'admitted exact slot-{first}-certified: node-1',
    'apply':'admitted exact slot-{first}-applied: node-1',
    'publish':'admitted exact slot-{first}-published: node-1',
    'allocator':'admitted exact campaign-4-prepared: node-1',
    'source':'admitted exact campaign-4-prepared: node-1',
    'control-image':'cross-view control image changed',
    'data-sequence':'cross-view application sequence/documents',
    'data-index':'cross-view application indexes',
    'data-document':'cross-view application document bytes',
    'force':'completion force before return',
    'call':'completion exact call coverage',
    'observation':'completion exact observations',
    'stopped':'admitted exact stopped: node-1',
}


def qualify(root,profile):
    root=Path(root);result=validate(root,profile);rows=[];first=7*PROFILES[profile]-1;last=first+4
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-completion-negative-') as temp:
            copy=Path(temp)/'raw';shutil.copytree(root,copy)
            direct={k:f'slot-{first}-{stage}/node-1/{file}' for k,stage,file in
                    [('accept','accepted','pending.accept'),('proof','proved','pending.accept'),('certificate','certified','pending.accept'),
                     ('apply','applied','applied-end/ack.gsr'),('publish','published','pending.accept'),('control-image','applied','applied-end/application.image')]}
            direct.update(allocator='campaign-4-prepared/node-1/allocator.gsr',stopped='stopped/node-1/pending.accept')
            if name in direct:
                p=copy/direct[name];p.write_bytes(p.read_bytes()+b'changed')
            elif name=='source':
                p=copy/'campaign-4-prepared/node-1';files=c.inventory(p);root_hash=c.current(files)[2]['capsule']['root']
                identifier=c.journal(files['grants.gsr'],root_hash,'node-1')[-1][2]['basisId'];p=p/'sources'/identifier/'source.gscp';p.write_bytes(b'changed')
            elif name.startswith('data-'):
                p=copy/f'slot-{last}-applied/node-1/applied-end/application.image';raw=p.read_bytes();size=int.from_bytes(raw[12:16],'big');checkpoint=bytearray(raw[16:16+size])
                if name=='data-sequence':struct.pack_into('>q',checkpoint,60,0)
                elif name=='data-index':checkpoint[80]=1
                else:checkpoint[checkpoint.index(b'21:admitted-completion')+3]^=1
                checkpoint[-4:]=struct.pack('>I',cross.core.crc32c(checkpoint[:-4]));p.write_bytes(raw[:16]+checkpoint+raw[16+size:])
            else:
                p=copy/('receipt.json' if name=='profile' else 'observations.json' if name=='observation' else 'calls.json');values=read(p)
                if name=='profile':values['profile']='capacity-231' if profile=='replay-smoke-1' else 'replay-smoke-1'
                elif name in ('call','observation'):values=values[1:]
                else:values[0]['events'].remove('ACCEPT_ACTIVE_FORCED')
                p.write_bytes(e.f.canonical(values))
            try:validate(copy,profile)
            except ValueError as error:e.need(str(error)==reason.format(first=first),'completion wrong negative: '+name+': '+str(error))
            else:raise ValueError('completion mutation accepted: '+name)
        rows.append(dict(case=name,status='REJECTED',reason=reason.format(first=first)))
    with tempfile.TemporaryDirectory(prefix='v53-completion-portable-') as temp:
        copy=Path(temp)/'raw';shutil.copytree(root,copy);same(validate(copy,profile),result,'completion portable replay')
    return dict(**result,negativeCases=rows,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--profile',choices=PROFILES,required=True)
    args=parser.parse_args();print(json.dumps(qualify(args.root,args.profile),sort_keys=True))
