"""Original-byte replay of carried INTENT/FINAL through fresh stable readiness.

The complete admitted REMOVE prefix, old ACCEPT, new native selections and all
subsequent publications remain one history. No Phase 2 authority is substituted.
This component does not claim the complete activation/transfer network oracle.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import continuous_transition_evidence as t
from . import transition_round_evidence as lifecycle
from . import carried_slot_evidence as carried
from . import node_current_evidence as current
from . import remove_maintenance_evidence as maintenance

a,b,c,d,e,f,need=t.a,t.b,t.c,t.d,t.e,t.f,t.need
KINDS=('INTENT','FINAL')


def shape(kind):
    need(kind in KINDS,'carried transition exact kind')
    return (5,3,t.topology(4)) if kind=='INTENT' else (6,2,t.topology(4)[1:])


def command(walk,kind):
    operation=walk.state()[3]['results'][-1]
    return dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}) if kind=='INTENT' else dict(binding=operation['binding'])


def layout(root,kind):
    index,count,_=shape(kind)
    need(root.is_dir() and not root.is_symlink(),'carried transition regular original')
    total=0
    for at,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()),'carried transition regular original')
        if path.is_file():total+=path.stat().st_size
        need(at<=65536 and total<=512*e.MIB,'carried transition bounded original')
    expected={'initial','original-plan.gsbp','original-application.image','before-network','after-close',
              'calls.json','events.json','wire.json','failures.json','carried-transition-result.json'}
    expected|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in range(1,index) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{slot}.{suffix}' for slot in range(1,index+1) for name,suffix in (('entry','gsr'),('payload','bin'))}
    expected.add(f'slot-{index}-accepted')
    if kind=='FINAL':expected|={'campaign-3-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'installed-{ordinal}' for ordinal in range(1,count+1)}
    expected|={f'selected-{ordinal}.gsr' for ordinal in range(1,count+1)}
    expected|={f'{label}-{slot}' for slot in range(index,8) for label in ('applied','published')}
    expected|={f'native-{name}-{slot}.{suffix}' for slot in range(index,8) for name,suffix in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(root,expected,'carried transition')
    for name in ('events','wire','failures'):
        rows=d.read(root/(name+'.json'));need(type(rows) is list and len(rows)<=32768,'carried transition bounded trace')


def prelude(root,kind):
    index,_,_=shape(kind)
    walk=a.prelude(root,kind,match_before=False)
    if kind=='FINAL':
        walk.group=t.reconcile(walk.group,sorted(walk.group))
        prepared,selected,installed=d.s.campaign(root,walk.group,3,'campaign-3-prepared',selected_prefix=d.slot.prefix)
        for stage,group in (('prepared',prepared),('selected',selected),('installed',installed),('settled',b.settled(installed))):
            b.match(root,'campaign-3-'+stage,group)
        walk.group=b.settled(installed);walk.counter=3;walk.first=None
        for phase in ('prepare','select','install'):walk.phase(phase+'-3',sorted(walk.group))
    body=f.canonical(command(walk,kind));members,packet,cap,_=walk.state()
    selected=f.decode(members['selected.gsr'],'records','SELECTED')
    entry=f.encode('records','ENTRY',dict(root=cap['root'],authority=selected['view'],index=index,
        previous=cap['cut']['entry'],origin=selected['ballot'],kind=kind,payload=e.digest(body)))
    need((root/f'entry-{index}.gsr').read_bytes()==entry and (root/f'payload-{index}.bin').read_bytes()==body,
         'carried transition original command')
    walk.group=carried.old.vote(root,f'slot-{index}-accepted',walk.group,sorted(walk.group),entry,body,[])
    b.match(root,'before-network',walk.group)
    a.preparation_calls(root,walk)
    rows=d.read(root/'calls.json');votes=[v for v in rows if v['operation']==f'accept-{index}']
    need([v['node'] for v in votes]==sorted(walk.group),'carried transition original ACCEPT owners')
    for row in votes:
        required=['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']
        need([v for v in row['events'] if v in required]==required,'carried transition original ACCEPT force')
    proofs=[v for v in rows if v['operation']==f'proof-{index}']
    need(len(proofs)==1 and proofs[0]['node']=='node-1' and proofs[0]['events']==['CURRENT_VALIDATED'],
         'carried transition original stopped PROOF')
    return walk,entry,body


def install_carried(root,group,voters,counter):
    group=t.reconcile(group,voters);prepared=dict(group);grants={};sources={};identifiers=set()
    identity=d.future.identity(group['node-1']);ballot=dict(counter=counter,proposer='node-1',incarnation=identity['storage'])
    for node in voters:
        files=group[node];_,members,_=c.current(files);raw,tail=carried.old.captured(files)
        packet=d.s.p.decode(raw);cap=packet['capsule'];prior=c.journal(files['grants.gsr'],cap['root'],node)
        observed=c.journal(c.inventory(root/'installed-1'/node)['grants.gsr'],cap['root'],node)
        need(observed[:len(prior)]==prior and [v[0] for v in observed[len(prior):]]==['PROMISE','BASIS','SELECTED'],
             'carried transition original grant extension')
        identifier=observed[len(prior)][2]['basisId']
        need(str(uuid.UUID(identifier))==identifier and identifier not in identifiers and
             all(v[2].get('basisId')!=identifier for v in prior),'carried transition fresh grant identity')
        identifiers.add(identifier);fields=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        promise=f.encode('records','PROMISE',fields);wrapper=d.s.s.wrap(promise,files[d.s.FILE])
        raw=c.packet_bytes(cap,dict(packet['objects'],**{e.digest(wrapper):wrapper}),packet['images']);frozen=d.s.p.decode(raw)
        basis=f.encode('records','BASIS',dict(fields,voter=node,cut=cap['cut'],capsule=e.digest(frozen['capsuleBytes']),
                     inventory=e.digest(frozen['indexBytes']),accepted=tail));source='sources/'+identifier
        changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise+basis,source:None,source+'/source.gscp':raw})
        changed.update({source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
        if node=='node-1':changed['allocator.gsr']=f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=counter))
        prepared[node]=changed;grants[node]=(promise,basis);sources[node]=(basis,frozen,wrapper)
    _,installed=carried.install.install(prepared,sources,grants,voters,ballot,{}, {},selected_prefix=d.slot.prefix)
    for node in voters:installed[node][d.s.FILE]=maintenance.merge(group,prepared[node][d.s.FILE],[group[n][d.s.FILE] for n in voters])
    b.match(root,'installed-1',installed)
    selected=c.current(installed['node-1'])[1]['selected.gsr']
    need((root/'selected-1.gsr').read_bytes()==selected,'carried transition original selection')
    return installed


class NativeSlot(t.NativeSlot):
    def entry_bytes(self,fields):
        if fields['index']!=self.old_index:return super().entry_bytes(fields)
        old=f.decode(self.carried_entry,'records','ENTRY')
        need(dict(old,origin=fields['origin'])==fields and old['origin']!=fields['origin'],
             'carried transition exact inherited command')
        return self.carried_entry

    def snapshot(self,label,group):
        if self.slot==self.old_index and label==f'slot-{self.slot}-accepted':
            self.group=current.maintenance(group,self.voters,after_accept=True)
        return super().snapshot(label,group)


def first_boundaries(root,index,voters):
    rows=d.read(root/'events.json')
    starts=[i for i,v in enumerate(rows) if v['event']=='SLOT_BEGIN' and v['index']==index]
    ends=[i for i,v in enumerate(rows) if v['event']=='DRIVER_PUBLISHED' and v['index']==index]
    need(len(starts)==len(ends)==1 and starts[0]<ends[0],'carried transition complete first lifetime')
    for node in voters:
        trace=[v['event'] for v in rows[starts[0]:ends[0]+1] if v['node']==node]
        d.s.ordered(trace,['ACCEPT_PARENT_FORCED',*maintenance.FLOOR,*maintenance.RETIRE,*maintenance.RELEASE,
                          'PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED',
                          'PUBLICATION_SELECTOR_FORCED'],'carried transition reaccept before floor '+node)
        need(not any(v in maintenance.SOURCE for v in trace),'carried transition no pending-source retirement')
        need(trace.count('APPLY_ACK_DIRECTORY_FORCED')==1,'carried transition one application acknowledgement')


def validate(root,kind):
    root=Path(root);index,count,profiles=shape(kind);layout(root,kind)
    walk,entry,body=prelude(root,kind)
    expected=dict(status='PASS',kind=kind,oldIndex=index,oldEntry=e.digest(entry),activations=count,
                  internalReady=True,publicReady=False,originalBudgetSeconds=600)
    need(f.canonical(d.read(root/'carried-transition-result.json'))==f.canonical(expected),'carried transition scope')
    native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__)
    native.old_index=index;native.carried_entry=entry
    for ordinal,(operation,voters) in enumerate(profiles,1):
        pregrant=t.reconcile(native.group,voters)
        prepared=maintenance.maintenance(pregrant,voters) if ordinal>1 else pregrant
        if ordinal==1:native.group=install_carried(root,native.group,voters,walk.counter+ordinal)
        else:native.group=t.install(root,native.group,ordinal,voters,current_maintenance=True,counter=walk.counter+ordinal)
        before=native.group
        if ordinal>1:
            native.group=maintenance.maintenance(before,voters)
            maintenance.boundaries(root,ordinal,voters,before,native.group,index=index+ordinal-1,
                                   pregrant=(pregrant,prepared))
        native.voters=voters;native.active=list(voters);native.first=None
        native.publish(operation,None if operation=='BARRIER' else command(native,operation))
        t.publication(root,native,ordinal)
    b.match(root,'after-close',native.group);first_boundaries(root,index,profiles[0][1])
    lifecycle.lifecycle(root,carried=kind)
    return dict(status='PASS',kind=kind,oldEntry=e.digest(entry),publishedSlots=list(range(index,8)),activations=count,
                originalEntryPreserved=True,physicalQualified=True,publicationBoundaryQualified=True,internalReady=True,
                fullNetworkQualified=False,publicReady=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection carried transition inventory',
    'original-entry':'carried transition original command',
    'original-payload':'carried transition original command',
    'original-vote':'admitted exact slot-{index}-accepted: node-2',
    'old-unselected-vote':'admitted exact before-network: node-4',
    'old-accept-force':'carried transition original ACCEPT force',
    'old-proof-progress':'carried transition original stopped PROOF',
    'installed-tail':'admitted exact installed-1: node-2',
    'selected-tail':'carried transition original selection',
    'freshened-native-entry':'continuous original native command',
    'new-ballot-vote':'admitted exact applied-{index}: node-2',
    'new-certificate':'transition exact native command',
    'control-image':'cross-view control image changed',
    'next-selected':'continuous original selection',
    'barrier-payload':'continuous original native command',
    'final-peer-ledger':'admitted exact published-7: node-2',
    'removed-peer':'admitted exact after-close: node-4',
    'missing-reactivation':'transition round exact lifecycle',
    'early-ready':'transition round exact lifecycle',
    'wrong-ready':'transition round readiness after fresh barrier',
    'wrong-completion':'transition round original completion',
    'first-selection-event':'transition round original selection',
    'first-entry-event':'transition round original entry',
    'reaccept-force':'selected retention force order: carried transition reaccept before floor node-1',
    'early-floor':'selected retention force order: carried transition reaccept before floor node-1',
    'early-publication':'continuous all retention quorums before publication',
    'wrong-publication-ack':'continuous original publication acknowledgement',
    'pregrant-source-force':'REMOVE maintenance exact pre-grant retirement: node-1',
    'public-service':'carried transition scope',
    'wrong-budget':'carried transition scope',
}


def negative_cases(kind):
    index,_,_=shape(kind)
    return {name:reason.format(index=index) for name,reason in NEGATIVES.items()}


def mutate(path,kind,name):
    index,_,_=shape(kind);need(name in NEGATIVES,'carried transition declared mutation')
    files={'original-entry':f'entry-{index}.gsr','original-payload':f'payload-{index}.bin',
           'original-vote':f'slot-{index}-accepted/node-2/pending.accept','old-unselected-vote':'before-network/node-4/pending.accept',
           'new-ballot-vote':f'applied-{index}/node-2/pending.accept','next-selected':'selected-2.gsr',
           'barrier-payload':'native-payload-7.bin','final-peer-ledger':'published-7/node-2/'+d.s.FILE,
           'removed-peer':'after-close/node-4/selector.gsr'}
    if name in files:(path/files[name]).write_bytes(b'changed');return
    if name=='extra-file':(path/'foreign').write_bytes(b'changed');return
    if name in ('public-service','wrong-budget'):
        p=path/'carried-transition-result.json';value=d.read(p)
        value['publicReady' if name=='public-service' else 'originalBudgetSeconds']=True if name=='public-service' else 180
        p.write_text(json.dumps(value));return
    if name in ('old-accept-force','old-proof-progress'):
        p=path/'calls.json';rows=d.read(p)
        row=next(v for v in rows if v['node']=='node-1' and v['operation']==('accept-' if name=='old-accept-force' else 'proof-')+str(index))
        if name=='old-accept-force':row['events'].remove('ACCEPT_ACTIVE_FORCED')
        else:row['events'].append('PROOF_PARENT_FORCED')
        p.write_text(json.dumps(rows));return
    if name=='installed-tail':
        p=path/'installed-1/node-2';prefix,_,_=c.current(c.inventory(p));(p/prefix/'owned-tail.gsr').write_bytes(b'changed');return
    if name in ('selected-tail','freshened-native-entry','new-certificate'):
        file='selected-1.gsr' if name=='selected-tail' else f'native-entry-{index}.gsr' if name=='freshened-native-entry' else f'applied-{index}/node-1/applied-end/certificate.gsr'
        record='SELECTED' if name=='selected-tail' else 'ENTRY' if name=='freshened-native-entry' else 'CERTIFICATE'
        p=path/file;value=f.decode(p.read_bytes(),'records',record)
        if name=='freshened-native-entry':value['origin']['counter']+=1
        else:value['nextEntry' if name=='selected-tail' else 'entry']='0'*64
        p.write_bytes(f.encode('records',record,value));return
    if name=='control-image':
        p=path/f'applied-{index}/node-1/applied-end/application.image';p.write_bytes(p.read_bytes()+b'changed');return
    rows=d.read(path/'events.json')
    def event(suffix,ordinal=0):return [v for v in rows if v['event']=='ROUND_'+suffix][ordinal]
    def change(row,family,record,edit):
        value=f.decode(base64.b64decode(row['bytes']),family,record);edit(value);raw=f.encode(family,record,value)
        row.update(record=e.digest(raw),bytes=base64.b64encode(raw).decode())
    if name=='missing-reactivation':rows.remove(event('INSTALLED',1))
    elif name=='early-ready':
        row=event('BEFORE_READY');rows.remove(row);rows.insert(rows.index(event('INSTALLED',1)),row)
    elif name=='wrong-ready':change(event('BEFORE_READY'),'wire','PUBLISH_ACK',lambda v:v['payload'].update(certificate='0'*64))
    elif name=='wrong-completion':change(event('SLOT_COMPLETE'),'wire','PUBLISH_ACK',lambda v:v['payload'].update(generation='0'*64))
    elif name=='first-selection-event':change(event('INSTALLED'),'records','SELECTED',lambda v:v.update(nextEntry=None))
    elif name=='first-entry-event':change(event('SLOT_BEGIN'),'records','ENTRY',lambda v:v['origin'].update(counter=v['origin']['counter']+1))
    elif name=='reaccept-force':rows.remove(next(v for v in rows if v['node']=='node-1' and v['event']=='ACCEPT_PARENT_FORCED'))
    elif name=='early-floor':
        row=next(v for v in rows if v['node']=='node-1' and v['event']=='FLOOR_COPIES_FORCED');rows.remove(row)
        at=next(i for i,v in enumerate(rows) if v['node']=='node-1' and v['event']=='ACCEPT_PARENT_FORCED');rows.insert(at,row)
    elif name=='pregrant-source-force':rows.remove(next(v for v in rows if v['node']=='node-1' and v['event']=='SOURCE_RETIREMENT_FORCED'))
    elif name=='early-publication':
        row=next(v for v in rows if v['event']=='PUBLICATION_SEND_BOUNDARY');rows.remove(row)
        at=next(i for i,v in enumerate(rows) if v['event']=='SLOT_BEGIN' and v['index']==index);rows.insert(at+1,row)
    elif name=='wrong-publication-ack':
        p=path/'wire.json';wire=d.read(p);row=next(v for v in wire if d.transfer.t.wire(v['request'])[0]=='PUBLISH')
        record,value=d.transfer.t.wire(row['response']);value['payload']['generation']='0'*64
        row['response']=base64.b64encode(f.encode('wire',record,value)).decode();p.write_text(json.dumps(wire));return
    else:raise ValueError('carried transition mutation not implemented')
    (path/'events.json').write_text(json.dumps(rows))


def qualify(root,kind):
    root=Path(root);original=validate(root,kind);negatives=[]
    for name,reason in negative_cases(kind).items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-transition-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);mutate(path,kind,name)
            try:validate(path,kind)
            except ValueError as error:need(str(error)==reason,'carried transition unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried transition mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--kind',choices=KINDS,required=True);p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root,args.kind),sort_keys=True))
