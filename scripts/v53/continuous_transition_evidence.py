"""Derive one uninterrupted REMOVE history from original bootstrap bytes.

Three original campaigns share the same four stores. The independent reduction
covers pre-grant floor maintenance/source retirement, joint voting, FINAL and the
fresh new-stable barrier. It does not claim autonomous operation or public READY.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import authority_transition_evidence as a

b,c,d,e,f,need=a.b,a.c,a.d,a.e,a.f,a.need
def topology(size):
    need(type(size) is int and size in (4,5),'continuous REMOVE voter count')
    old=tuple('node-'+str(i+1) for i in range(size//2+1))
    new=tuple('node-'+str(i+1) for i in range((size-1)//2+1))
    return (('INTENT',old),('FINAL',old),('BARRIER',new))


PROFILES=topology(4)


def reconcile(group,voters):
    result=copy.deepcopy(group)
    for node in voters:
        files=result[node];previous=d.s.r.decode(files[d.s.FILE]);view=c.current(files)[2]['capsule']['cut']['view']
        if previous['plan']['view']==view:continue
        members=set(view['old'])|set(view['new'])
        peers=[row for row in previous['plan']['peers'] if row['identity']['node'] in members]
        need({row['identity']['node'] for row in peers}==members,'continuous actual joining identity required')
        plan=dict(previous['plan'],view=view,peers=peers)
        files[d.s.FILE]=d.s.r.frame(dict(previous,revision=previous['revision']+1,previous=e.digest(files[d.s.FILE]),plan=plan))
    return result


def install(root,group,ordinal,voters,*,current_maintenance=False,counter=None):
    from . import remove_maintenance_evidence as maintenance
    group=reconcile(group,voters)
    if ordinal>1 and current_maintenance:
        group=maintenance.maintenance(group,voters)
    elif ordinal>1:
        group=a.maintenance(group,voters)
        # The complete current quorum supports retirement of the inactive
        # generation and strictly older sources. The current original grant,
        # selection and its source remain owned; no vote authority is invented.
        group.update(b.settled({n:group[n] for n in voters}))
    options={}
    if current_maintenance:
        options=dict(merge_ledgers=lambda before,sources:maintenance.merge(group,before,sources))
    _,_,installed=d.s.campaign(root,{n:group[n] for n in voters},ordinal+2 if counter is None else counter,'installed-'+str(ordinal),selected_prefix=d.slot.prefix,**options)
    group=dict(group,**installed);b.match(root,'installed-'+str(ordinal),group)
    chosen=c.current(group['node-1'])[1]['selected.gsr']
    need((root/f'selected-{ordinal}.gsr').read_bytes()==chosen,'continuous original selection')
    return group


class NativeSlot(a.NativeSlot):
    def requested(self,slot,entry,payload):
        super().requested(slot,entry,payload)
        need((self.root/f'native-entry-{slot}.gsr').read_bytes()==entry and
             (self.root/f'native-payload-{slot}.bin').read_bytes()==payload,'continuous original native command')


def maintenance_boundaries(root,ordinal,voters):
    events=d.read(root/'events.json')
    installed=[(i,row) for i,row in enumerate(events) if row['event']=='CONTINUOUS_INSTALLED' and row['ordinal']==ordinal]
    need(len(installed)==1 and installed[0][1]['selection']==e.digest((root/f'selected-{ordinal}.gsr').read_bytes()),
         'continuous installed original selection')
    if ordinal==1:return
    prior=[i for i,row in enumerate(events) if row['event']=='DRIVER_PUBLISHED' and row['index']==ordinal+3]
    need(len(prior)==1 and prior[0]<installed[0][0],'continuous original campaign boundary')
    for node in voters:
        trace=[row['event'] for row in events[prior[0]:installed[0][0]] if row['node']==node]
        d.s.ordered(trace,['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
            'RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_BEFORE_RETURN',
            'SOURCE_RETIREMENT_FORCED','SOURCE_RETIREMENT_PARENT_FORCED','JOURNAL_ROTATION_FORCED',
            'JOURNAL_ROTATION_PARENT_FORCED','SOURCE_RETIREMENT_JOURNAL_PRUNED','SOURCE_RETIREMENT_FILE_DELETED',
            'SOURCE_RETIREMENT_BEFORE_RETURN','FLOOR_RELEASE_BEFORE_RETURN','PROMISE_FORCED','SOURCE_DIRECTORY_FORCED',
            'BASIS_FORCED','GRANT_BEFORE_RETURN','SELECTED_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'],
            'continuous pre-grant '+node)


def publication(root,slot,ordinal,*,wire=None):
    events=d.read(root/'events.json');wire=d.read(root/'wire.json') if wire is None else wire;voters=slot.voters
    selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes();selected=f.decode(selected_raw,'records','SELECTED')
    starts=[i for i,row in enumerate(events) if row['event']=='SLOT_BEGIN' and row['index']==slot.slot]
    finishes=[i for i,row in enumerate(events) if row['event']=='DRIVER_PUBLISHED' and row['index']==slot.slot]
    need(len(starts)==len(finishes)==1 and starts[0]<finishes[0],'continuous complete slot lifetime')
    start,end=starts[0],finishes[0];within=events[start:end+1]
    quorums=[(i,row) for i,row in enumerate(within) if row['event']=='DRIVER_FUTURE_QUORUM_COMPLETE']
    sends=[i for i,row in enumerate(within) if row['event']=='PUBLICATION_SEND_BOUNDARY']
    need(len(quorums)==len(voters)-1 and len(sends)>=len(voters)-1 and all(
        row['index']==slot.slot and row['voters']==list(voters) and i<min(sends) for i,row in quorums),
        'continuous all retention quorums before publication')
    identities={n:d.future.identity(files) for n,files in slot.group.items()}
    cert=e.digest(slot.applied['node-1']['applied-end/certificate.gsr']);received=set()
    for row in wire:
        kind,request=d.transfer.t.wire(row['request'])
        if kind!='PUBLISH' or request['ballot']!=selected['ballot']:continue
        answer,reply=d.transfer.t.wire(row['response']);peer=request['recipient']['node'];received.add(peer)
        need(peer in voters[1:] and answer=='PUBLISH_ACK' and row.get('withheld') is False,'continuous original publication response')
        need(request['root']==selected['root'] and request['view']==selected['view'] and
             request['sender']==identities['node-1'] and request['recipient']==identities[peer] and
             request['payload']==dict(certificate=cert),'continuous original publication request')
        prefix,_,packet=c.current(slot.group[peer])
        payload=dict(certificate=cert,selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),
                     generation=e.digest(slot.group[peer][prefix+'generation.gsr']))
        need(reply==dict(request,sender=request['recipient'],recipient=request['sender'],payload=payload),
             'continuous original publication acknowledgement')
        response=e.digest(base64.b64decode(row['response'],validate=True))
        at=next((i for i,v in enumerate(within) if v['event']=='WIRE_RESPONSE' and v.get('response')==response),None)
        need(at is not None,'continuous publication response event')
        d.s.ordered([v['event'] for v in within[:at] if v['node']==peer],
            ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'continuous publication')
    need(received==set(voters[1:]),'continuous all publication acknowledgements')


def history(root, result_file, *, size=4, current_maintenance=False, backup=False, additional=(), maximum_bytes=512*e.MIB, wire_bytes=8*e.MIB):
    """Shared original-byte reduction; callers separately enforce their scope.

    Only the declared result filename varies. Sources, traces, images, quorums
    and exact inventories are still reduced from the same unmodified directory.
    """
    root=Path(root);profiles=topology(size)
    need(result_file in ('continuous-result.json','transition-round-result.json'),'continuous result filename')
    need(root.is_dir() and not root.is_symlink(),'continuous regular original inventory')
    total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()),'continuous regular original inventory')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=maximum_bytes,'continuous bounded original inventory')
    expected={'initial','original-plan.gsbp','original-application.image','before-network','after-close',
              'calls.json','events.json','wire.json','failures.json',result_file}
    expected|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in range(1,5) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{slot}.{suffix}' for slot in range(1,5) for name,suffix in (('entry','gsr'),('payload','bin'))}
    expected|={f'{label}-{ordinal}' for ordinal in range(1,4) for label in ('installed',)}
    expected|={f'selected-{ordinal}.gsr' for ordinal in range(1,4)}
    expected|={f'{label}-{slot}' for slot in range(5,8) for label in ('applied','published')}
    expected|={f'native-{name}-{slot}.{suffix}' for slot in range(5,8) for name,suffix in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(root,expected|set(additional),'continuous transition')
    wire=json.loads(b.t.plans.read(root/'wire.json',wire_bytes))
    for name in ('events','wire','failures'):
        values=wire if name=='wire' else d.read(root/(name+'.json'));need(type(values) is list and len(values)<=32768,'continuous bounded traces')
    walk=a.prelude(root,'INTENT',size=size,backup=backup);native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__)
    for ordinal,(kind,voters) in enumerate(profiles,1):
        native.group=install(root,native.group,ordinal,voters,current_maintenance=current_maintenance)
        from . import remove_maintenance_evidence as maintenance
        preceding=native.group
        native.group=(maintenance.maintenance if current_maintenance else a.maintenance)(preceding,voters)
        if current_maintenance:maintenance.boundaries(root,ordinal,voters,preceding,native.group)
        else:maintenance_boundaries(root,ordinal,voters)
        native.active=list(voters);native.voters=voters;native.first=None
        operation=native.state()[3]['results'][-1]
        command=dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}) if kind=='INTENT' else (
            dict(binding=operation['binding']) if kind=='FINAL' else None)
        native.publish(kind,command);publication(root,native,ordinal,wire=wire)
    b.match(root,'after-close',native.group)
    return dict(status='PASS',kind='REMOVE',activations=3,publishedSlots=[5,6,7],physicalQualified=True,
                publicationBoundaryQualified=True,publicReady=False,phase3Complete=False)


def validate(root):
    root=Path(root);result=d.read(root/'continuous-result.json')
    need(result==dict(status='PASS',kind='REMOVE',activations=3,publicReady=False,automaticLifecycle=False),'continuous scope')
    return dict(history(root,'continuous-result.json'),automaticLifecycle=False)


NEGATIVES=('scope','extra-file','preparation','old-source','joint-journal','joint-selection','joint-vote',
           'final-certificate','final-future','stable-journal','stable-selection','barrier-entry','barrier-payload',
           'barrier-future','removed-peer','missing-force','early-publication','wrong-ack')


def qualify(root):
    root=Path(root);original=validate(root);rows=[]
    targets={
        'preparation':('before-network/node-4/selector.gsr','admitted exact before-network: node-4'),
        'joint-journal':('installed-2/node-1/grants.gsr','orphan/duplicate grant basis'),
        'joint-selection':('selected-2.gsr','continuous original selection'),
        'joint-vote':('applied-6/node-3/pending.accept','admitted exact applied-6: node-3'),
        'final-certificate':('applied-6/node-1/applied-end/certificate.gsr','transition exact native command'),
        'final-future':('published-6/node-1/'+d.future.FILE,'admitted exact published-6: node-1'),
        'stable-journal':('installed-3/node-2/grants.gsr','orphan/duplicate grant basis'),
        'stable-selection':('selected-3.gsr','continuous original selection'),
        'barrier-entry':('native-entry-7.gsr','continuous original native command'),
        'barrier-payload':('native-payload-7.bin','continuous original native command'),
        'barrier-future':('published-7/node-2/'+d.future.FILE,'admitted exact published-7: node-2'),
        'removed-peer':('after-close/node-4/selector.gsr','admitted exact after-close: node-4'),
    }
    for name in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-continuous-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='scope':
                value=d.read(path/'continuous-result.json');value['automaticLifecycle']=True
                (path/'continuous-result.json').write_text(json.dumps(value));reason='continuous scope'
            elif name=='extra-file':
                (path/'extra').write_bytes(b'bad');reason='context selection continuous transition inventory'
            elif name=='old-source':
                # Restore the actual obsolete source deleted before campaign 2.
                before=c.inventory(path/'published-5/node-1');after=c.inventory(path/'installed-2/node-1')
                removed=[k for k in before if k.startswith('sources/') and k not in after]
                need(bool(removed),'continuous negative obsolete source exists')
                for k in removed:
                    target=path/'installed-2/node-1'/k
                    if before[k] is None:target.mkdir(parents=True,exist_ok=True)
                    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(before[k])
                reason='admitted exact installed-2: node-1'
            elif name in ('missing-force','early-publication'):
                values=d.read(path/'events.json')
                if name=='missing-force':
                    at=next(i for i,v in enumerate(values) if v['event']=='DRIVER_PUBLISHED' and v['index']==5)
                    at=next(i for i in range(at+1,len(values)) if values[i]['node']=='node-1' and values[i]['event']=='SOURCE_RETIREMENT_FORCED')
                    values.pop(at);reason='selected retention force order: continuous pre-grant node-1'
                else:
                    at=next(i for i,v in enumerate(values) if v['event']=='SLOT_BEGIN' and v['index']==6)
                    send=next(i for i in range(at+1,len(values)) if values[i]['event']=='PUBLICATION_SEND_BOUNDARY')
                    values.insert(at+1,values.pop(send));reason='continuous all retention quorums before publication'
                (path/'events.json').write_text(json.dumps(values))
            elif name=='wrong-ack':
                values=d.read(path/'wire.json');row=next(v for v in values if d.transfer.t.wire(v['request'])[0]=='PUBLISH'
                    and d.transfer.t.wire(v['request'])[1]['ballot']['counter']==4)
                kind,fields=d.transfer.t.wire(row['response']);fields['payload']['generation']='0'*64
                row['response']=base64.b64encode(f.encode('wire',kind,fields)).decode();(path/'wire.json').write_text(json.dumps(values))
                reason='continuous original publication acknowledgement'
            elif name in ('joint-journal','stable-journal'):
                target,reason=targets[name];file=path/target;value=file.read_bytes()
                first=48+int.from_bytes(value[12:16],'big');file.write_bytes(value[first:])
            elif name=='final-certificate':
                target,reason=targets[name];file=path/target;value=f.decode(file.read_bytes(),'records','CERTIFICATE')
                value['entry']='0'*64;file.write_bytes(f.encode('records','CERTIFICATE',value))
            else:
                target,reason=targets[name];(path/target).write_bytes(b'changed')
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'continuous unrelated negative: '+name+': '+str(error))
            else:raise ValueError('continuous mutation accepted: '+name)
        rows.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
