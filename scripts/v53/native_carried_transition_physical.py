"""Derive carried context restart snapshots from the original admitted prefix.

This is a storage component, not network/force-order or hosted cohort admission.
Observed snapshots contribute only fresh source UUIDs and the selected cohort;
votes, sources, generations, catalogs and retention frames are derived separately.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import native_carried_transition_process as process
from . import native_carried_recovery_evidence as data
from . import joining_same_view_physical as floors

t=process.t
b,c,d,e,f,need=t.b,t.c,t.d,t.e,t.f,t.need


class View:
    """Name original snapshots without moving or rewriting any authority bytes."""
    def __init__(self,root,life):self.root,self.life=root,life
    def __truediv__(self,name):
        if name.startswith(('installed-','applied-','published-')):name=f'life-{self.life}-'+name
        return self.root/name


def vote(files,entry,payload,extra=()):
    _,members,packet=c.current(files);selected=f.decode(members['selected.gsr'],'records','SELECTED')
    value=f.decode(entry,'records','ENTRY')
    need(value['kind'] in t.KINDS and selected['nextEntry']==e.digest(entry) and
         selected['cut']==packet['capsule']['cut'] and value['root']==selected['root'] and
         value['authority']==selected['view'] and value['index']==selected['cut']['index']+1 and
         value['previous']==selected['cut']['entry'] and value['payload']==e.digest(payload),
         'context process exact successor vote')
    accept=f.encode('records','ACCEPT',dict(root=selected['root'],authority=selected['view'],
        ballot=selected['ballot'],index=value['index'],entry=e.digest(entry)))
    raw=e.container([files['selector.gsr'],members['promise.gsr'],members['selected.gsr'],entry,accept],payload)+b''.join(extra)
    return raw[:8]+struct.pack('>I',len(raw))+raw[12:]


def cold(group,entry,payload):
    result=copy.deepcopy(group)
    for node,files in group.items():
        need(not any(k=='applied-end' or k.startswith('applied-end/') for k in files),
             'context process cold staged application unsupported')
        frames,_=data.pending(files)
        need(frames and frames['ENTRY']==entry and frames['PAYLOAD']==payload,'context process cold original command')
        if frames['SELECTOR']==files['selector.gsr']:continue
        _,members,packet=c.current(files);selected=f.decode(members['selected.gsr'],'records','SELECTED')
        need(selected['nextEntry']==e.digest(entry) and packet['objects'].get(e.digest(entry))==entry and
             packet['objects'].get(e.digest(payload))==payload,'context process cold retained command')
        result[node]['pending.accept']=vote(files,entry,payload)
    return result


def needs_maintenance(files):
    prefix,members,packet=c.current(files)
    if any(k.startswith('generations/') and k!=prefix[:-1] and not k.startswith(prefix) for k in files):return True
    rows=c.journal(files['grants.gsr'],packet['capsule']['root'],d.future.identity(files)['node'])
    latest=next(v['ballot'] for k,_,v in reversed(rows) if k=='PROMISE')
    promises={v['basisId']:(raw,v) for k,raw,v in rows if k=='PROMISE' and v['basisId'] is not None}
    bases={v['basisId']:(raw,v) for k,raw,v in rows if k=='BASIS'}
    for name in files:
        if not name.startswith('sources/') or not name.endswith('/source.gscp'):continue
        identifier=name.split('/')[1];promise,p=promises[identifier];basis,v=bases[identifier]
        if promise!=members['promise.gsr'] and basis!=members.get('basis.gsr') and v['cut']==packet['capsule']['cut'] and p['ballot']['counter']<latest['counter']:return True
    return False


def maintain(group,owners,*,campaign=False):
    result=copy.deepcopy(group)
    for node in owners:
        files=group[node]
        if not needs_maintenance(files):continue
        need(not any(k=='applied-end' or k.startswith('applied-end/') for k in files),
             'context process maintenance staged application')
        frames,_=data.pending(files);_,members,packet=c.current(files)
        selected=f.decode(members['selected.gsr'],'records','SELECTED')
        if frames:
            if frames['SELECTOR']!=files['selector.gsr']:continue
            need(frames['PROMISE']==members['promise.gsr'] and frames['SELECTED']==members['selected.gsr'] and
                 selected['nextEntry']==e.digest(frames['ENTRY']) and selected['cut']==packet['capsule']['cut'] and
                 f.decode(frames['ENTRY'],'records','ENTRY')['kind'] in t.KINDS,
                 'context process maintenance exact transferred vote')
        copies=copy.deepcopy(group);copies[node]['pending.accept']=c.EMPTY
        voters=floors.floor_voters(group,node)
        projected=t.maintenance.maintenance(copies,voters,owners=(node,))[node]
        if frames:
            if campaign:t.current.retained_carried_sources(files,projected,node,frames,packet)
            else:projected.update({k:v for k,v in files.items() if k=='grants.gsr' or k.startswith('sources/')})
            projected['pending.accept']=files['pending.accept']
        result[node]=projected
    return result


def campaign(root,group,life,ordinal,counter,entry):
    snapshot=f'life-{life}-installed-{ordinal}'
    chosen=(root/(snapshot+'.gsr')).read_bytes();observed=f.decode(chosen,'records','SELECTED')
    voters=tuple(v['voter'] for v in observed['sources'])
    _,_,current=c.current(group['node-1']);view=current['capsule']['cut']['view']
    need(voters==tuple(sorted(set(voters))) and voters[0]=='node-1' and set(voters)<=set(group),
         'context process original selected cohort')
    t.a.x.context.majority(view,list(voters))
    touched=[]
    for node,files in group.items():
        actual=c.inventory(root/snapshot/node)
        if node in voters or actual['grants.gsr']!=files['grants.gsr']:touched.append(node)
    reconciled=t.t.reconcile(group,touched)
    group=maintain(reconciled,touched,campaign=True)
    ballot=dict(counter=counter,proposer='node-1',incarnation=d.future.identity(group['node-1'])['storage'])
    prepared=copy.deepcopy(group);grants={};sources={};identifiers=set()
    for node in touched:
        files=group[node];_,members,packet=c.current(files);cap=packet['capsule']
        prior=c.journal(files['grants.gsr'],cap['root'],node)
        rows=c.journal(c.inventory(root/snapshot/node)['grants.gsr'],cap['root'],node)
        need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==
             ['PROMISE','BASIS']+(['SELECTED'] if node in voters else []),'context process original grant extension')
        identifier=rows[len(prior)][2]['basisId']
        need(str(uuid.UUID(identifier))==identifier and identifier not in identifiers and
             all(v[2].get('basisId')!=identifier for v in prior),'context process fresh source UUID')
        identifiers.add(identifier)
        raw,tail=t.carried.old.captured(files,data.pending(files)[1]);captured=e.p.decode(raw)
        fields=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),ballot=ballot,basisId=identifier)
        promise=f.encode('records','PROMISE',fields);wrapper=d.s.s.wrap(promise,files[d.s.FILE])
        raw=c.packet_bytes(cap,dict(captured['objects'],**{e.digest(wrapper):wrapper}),captured['images']);frozen=e.p.decode(raw)
        basis=f.encode('records','BASIS',dict(fields,voter=node,cut=cap['cut'],capsule=e.digest(frozen['capsuleBytes']),
            inventory=e.digest(frozen['indexBytes']),accepted=tail));source='sources/'+identifier
        changed=dict(files,**{'grants.gsr':files['grants.gsr']+promise+basis,source:None,source+'/source.gscp':raw})
        changed.update({source+'/'+h+'.image':members[h+'.image'] for h in frozen['images']})
        if node=='node-1':changed['allocator.gsr']=f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=counter))
        prepared[node]=changed;grants[node]=(promise,basis);sources[node]=(basis,frozen,wrapper)
    _,installed=t.carried.install.install(prepared,sources,grants,voters,ballot,{}, {},selected_prefix=d.slot.prefix,
        merge_ledgers=lambda before,originals:t.maintenance.merge(group,before,originals))
    need(c.current(installed['node-1'])[1]['selected.gsr']==chosen and
         observed['nextEntry']==(e.digest(entry) if entry is not None else None),'context process derived selected command')
    b.match(root,snapshot,installed)
    return installed,voters


def interrupted(group,voters,entry,payload,point):
    need(point in process.CUTS,'context process exact crash cut')
    changed=copy.deepcopy(group)
    for node in (('node-1',) if point=='ACCEPT_RENAMED' else voters):
        changed[node]['pending.accept']=vote(group[node],entry,payload)
    if point=='ACCEPT_RENAMED':return changed
    changed=maintain(changed,('node-1',))
    frames,_=data.pending(changed['node-1']);accept=frames['ACCEPT'];value=f.decode(accept,'records','ACCEPT')
    accepts=[dict(voter=n,incarnation=d.future.identity(group[n])['storage'],receipt=e.digest(f.canonical(dict(
        root=value['root'],voter=n,incarnation=d.future.identity(group[n])['storage'],phase='ACCEPT',record=e.digest(accept))))) for n in voters]
    proof=f.encode('records','PROOF',dict(value,accepts=accepts))
    changed['node-1']['pending.accept']=vote(changed['node-1'],entry,payload,(proof,))
    return changed


class NativeSlot(t.a.NativeSlot):
    def entry_bytes(self,fields):
        if fields['index']!=self.old_index:return super().entry_bytes(fields)
        old=f.decode(self.carried_entry,'records','ENTRY')
        need(dict(old,origin=fields['origin'])==fields and old['origin']!=fields['origin'],
             'context process unchanged inherited entry')
        return self.carried_entry

    def snapshot(self,label,group):
        if label==f'slot-{self.old_index}-accepted':self.group=maintain(group,self.voters)
        return super().snapshot(label,group)


def physical(root,kind,point):
    root=Path(root);walk,entry,payload=t.prelude(root,kind);index,campaigns,_=t.shape(kind)
    group=cold(walk.group,entry,payload);b.match(root,'life-1-opened',group)
    group,voters=campaign(root,group,1,1,walk.counter+1,entry)
    group=interrupted(group,voters,entry,payload,point)
    b.match(root,'at-cut',group);b.match(root,'before-reopen',group)
    group=cold(group,entry,payload);b.match(root,'life-2-opened',group)
    native=NativeSlot.__new__(NativeSlot);native.__dict__.update(walk.__dict__)
    native.root=View(root,2);native.old_index=index;native.carried_entry=entry;native.group=group
    for ordinal,slot in enumerate(range(index,8),1):
        native.group,voters=campaign(root,native.group,2,ordinal,walk.counter+ordinal+1,entry if ordinal==1 else None)
        if ordinal>1:native.group=maintain(native.group,voters)
        native.voters=voters;native.active=list(voters);native.first=None
        operation={5:'INTENT',6:'FINAL',7:'BARRIER'}[slot]
        native.publish(operation,None if operation=='BARRIER' else t.command(native,operation))
    b.match(root,'life-2-ready',native.group);b.match(root,'after-close',native.group)
    return dict(status='PARTIAL',scope='carried-transition-original-storage-snapshots',kind=kind,cut=point,
        snapshotByteReplay=True,originalPrefixReplayed=True,publishedSlots=list(range(index,8)),
        campaigns=1+campaigns,fullForceReplay=False,fullWireReplay=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=process.collection.inventory(root)
    original=process.validate(root)
    storage=physical(root,original['kind'],original['cut'])
    need(process.collection.inventory(root)==before,'context process physical original changed')
    return dict(process=original,physical=storage,status='PARTIAL',phase3Complete=False)


NEGATIVES={
    'cold-original-vote':'admitted exact life-1-opened: node-4',
    'cold-current-vote':'admitted exact life-2-opened: node-1',
    'cold-retained-source':'admitted exact life-2-opened: node-4',
    'installed-unselected-owner':'admitted exact life-1-installed-1: node-4',
    'installed-source-bytes':'admitted exact life-1-installed-1: node-2',
    'installed-owned-tail':'admitted exact life-1-installed-1: node-2',
    'interrupted-peer-vote':'admitted exact at-cut: node-2',
    'interrupted-unselected-owner':'admitted exact at-cut: node-4',
    'reclaimed-source-restored':'admitted exact life-2-installed-1: node-1',
    'current-source-removed':'admitted exact life-2-installed-1: node-2',
    'applied-vote':'admitted exact applied-{index}: node-2',
    'applied-catalog':'admitted exact applied-{index}: node-2',
    'applied-checkpoint-ack':'admitted exact applied-{index}: node-2',
    'control-image':'cross-view control image changed',
    'published-peer-ledger':'admitted exact published-{index}: node-2',
    'next-campaign-unselected-owner':'admitted exact life-2-installed-2: node-4',
    'next-campaign-source':'admitted exact life-2-installed-2: node-2',
    'barrier-catalog':'admitted exact applied-7: node-2',
    'ready-peer-inventory':'admitted exact life-2-ready: node-3',
    'closed-unselected-owner':'admitted exact after-close: node-4',
}


def negative_cases(kind):
    index,_,_=t.shape(kind)
    return {name:reason.format(index=index) for name,reason in NEGATIVES.items()}


def mutate(root,name):
    """Alter disposable original copies, including both sides of the death cut.

    Changing both interrupted inventories deliberately preserves the parent's
    unchanged-directory observation: only the independent storage reducer can
    reject those two mutations.
    """
    root=Path(root);index=t.shape(process.read(root/'process/result.json')['carriedKind'])[0]
    files={
        'cold-original-vote':'life-1-opened/node-4/pending.accept',
        'cold-current-vote':'life-2-opened/node-1/pending.accept',
        'installed-unselected-owner':'life-1-installed-1/node-4/allocator.gsr',
        'applied-vote':f'life-2-applied-{index}/node-2/pending.accept',
        'applied-catalog':f'life-2-applied-{index}/node-2/applied-end/catalog.gsr',
        'applied-checkpoint-ack':f'life-2-applied-{index}/node-2/applied-end/ack.gsr',
        'control-image':f'life-2-applied-{index}/node-1/applied-end/application.image',
        'published-peer-ledger':f'life-2-published-{index}/node-2/'+d.s.FILE,
        'next-campaign-unselected-owner':'life-2-installed-2/node-4/pending.accept',
        'barrier-catalog':'life-2-applied-7/node-2/applied-end/catalog.gsr',
        'ready-peer-inventory':'life-2-ready/node-3/pending.accept',
        'closed-unselected-owner':'after-close/node-4/pending.accept',
    }
    if name in files:
        path=root/files[name];need(path.is_file(),'context process original mutation file')
        path.write_bytes(b'changed original');return
    if name in ('interrupted-peer-vote','interrupted-unselected-owner'):
        owner='node-2' if name=='interrupted-peer-vote' else 'node-4'
        for label in ('at-cut','before-reopen'):(root/label/owner/'pending.accept').write_bytes(b'changed original')
    elif name in ('installed-source-bytes','next-campaign-source','current-source-removed'):
        label='life-1-installed-1' if name=='installed-source-bytes' else 'life-2-installed-2' if name=='next-campaign-source' else 'life-2-installed-1'
        path=root/label/'node-2';_,members,_=c.current(c.inventory(path))
        identifier=f.decode(members['basis.gsr'],'records','BASIS')['basisId']
        source=path/'sources'/identifier/'source.gscp'
        if name=='current-source-removed':source.unlink()
        else:source.write_bytes(b'changed original')
    elif name=='cold-retained-source':
        path=root/'life-2-opened/node-4';sources=sorted(path.glob('sources/*/source.gscp'))
        need(bool(sources),'context process original retained source');sources[0].unlink()
    elif name=='installed-owned-tail':
        path=root/'life-1-installed-1/node-2';prefix,_,_=c.current(c.inventory(path))
        (path/prefix/'owned-tail.gsr').write_bytes(b'changed original')
    elif name=='reclaimed-source-restored':
        old=root/'life-2-opened/node-1';new=root/'life-2-installed-1/node-1'
        missing=[path for path in sorted((old/'sources').iterdir()) if not (new/'sources'/path.name).exists()]
        need(bool(missing),'context process original reclaimed source')
        shutil.copytree(missing[0],new/'sources'/missing[0].name)
    else:raise ValueError('unknown context process physical mutation')


def qualify(root):
    root=Path(root);before=process.collection.inventory(root);original=validate(root);results=[]
    with tempfile.TemporaryDirectory(prefix='v53-transition-physical-') as work:
        for name,reason in negative_cases(original['physical']['kind']).items():
            changed=Path(work)/name;shutil.copytree(root,changed);mutate(changed,name)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'context process physical wrong negative '+name+': '+str(error))
            else:raise ValueError('context process physical accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason));shutil.rmtree(changed)
    need(process.collection.inventory(root)==before,'context process physical original changed during negatives')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('original');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.original) if a.qualify else validate(a.original),sort_keys=True))
