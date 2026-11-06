"""Whole-group INTENT/FINAL death after application ACK, before publication.

Independent storage projection from the admitted original prefix. This does not
qualify every force/TCP/resource callback or a final-source hosted cohort.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import native_carried_transition_physical as p

t,b,c,d,e,f,need=p.t,p.b,p.c,p.d,p.e,p.f,p.need
CUT='APPLY_ACK_DIRECTORY_FORCED'


def cold(group,entry,payload):
    result={}
    for node,files in group.items():
        if 'applied-end' in files:
            frames,phases=p.data.pending(files)
            need(phases==('PROOF','CERTIFICATE') and frames['ENTRY']==entry and frames['PAYLOAD']==payload and
                 frames['SELECTOR']==files['selector.gsr']==files['applied-end/selector.gsr'] and
                 frames['CERTIFICATE']==files['applied-end/certificate.gsr'], 'context application cold original end')
            result[node]=copy.deepcopy(files)
        else:result[node]=p.cold({node:files},entry,payload)[node]
    return result


def maintain(group,owners,*,campaign=False):
    # A staged owner pins original source/floor references. Native campaign
    # maintenance must defer that owner, not pretend its derived end is gone.
    eligible=[node for node in owners if 'applied-end' not in group[node]]
    return p.maintain(group,eligible,campaign=campaign)


class CutComplete(Exception):pass


class InterruptedSlot(p.NativeSlot):
    def requested(self,slot,entry,payload):
        need(slot==self.old_index and entry==self.carried_entry and payload==self.carried_payload,
             'context application original interrupted command')
        self.entry=entry

    def application_image(self,slot,nodes):
        _,members,packet=c.current(self.group[nodes[0]])
        return members[packet['capsule']['application']+'.image']

    def snapshot(self,label,group):
        if label.endswith('-accepted'):self.group=p.maintain(group,self.voters)
        elif label.endswith('-proved'):self.proven=copy.deepcopy(group)
        elif label.endswith('-applied'):
            # Only the leader has forced its certificate/end. Remote voters
            # have returned PROOF; no remote CERT/APPLY/PUBLISH has happened.
            self.interrupted=copy.deepcopy(self.proven)
            self.interrupted['node-1']=copy.deepcopy(group['node-1'])
            raise CutComplete()


def interrupted(walk,group,voters,entry,payload,kind):
    slot=InterruptedSlot.__new__(InterruptedSlot);slot.__dict__.update(copy.deepcopy(walk.__dict__))
    slot.old_index=t.shape(kind)[0];slot.carried_entry=entry;slot.carried_payload=payload
    slot.group=copy.deepcopy(group);slot.voters=voters;slot.active=list(voters);slot.first=None
    try:slot.publish(kind,t.command(slot,kind))
    except CutComplete:return slot.interrupted
    raise ValueError('context application projection passed crash boundary')


def retire(files,entry,payload):
    frames,phases=p.data.pending(files);_,members,packet=c.current(files)
    selected=f.decode(members['selected.gsr'],'records','SELECTED')
    need(phases==('PROOF','CERTIFICATE') and frames['ENTRY']==entry and frames['PAYLOAD']==payload and
         frames['SELECTOR']==files['applied-end/selector.gsr'] and frames['SELECTOR']!=files['selector.gsr'] and
         frames['CERTIFICATE']==files['applied-end/certificate.gsr'] and selected['nextEntry']==e.digest(entry) and
         packet['objects'].get(e.digest(entry))==entry and packet['objects'].get(e.digest(payload))==payload,
         'context application exact retained retirement')
    previous=f.decode(frames['SELECTED'],'records','SELECTED')
    need(selected['cut']==previous['cut'] and selected['ballot']['counter']>previous['ballot']['counter'],
         'context application newer identical parent')
    basis=f.decode(members['basis.gsr'],'records','BASIS')
    source=e.p.decode(files['sources/'+basis['basisId']+'/source.gscp']);e.p.bind(source,members['basis.gsr'])
    need(all(source['objects'].get(e.digest(frames[k]))==frames[k]
             for k in ('ENTRY','ACCEPT','PROOF','CERTIFICATE','PAYLOAD')), 'context application original certified source')
    return p.data.staging.without_staging(files)


class RecoveredSlot(p.NativeSlot):
    def snapshot(self,label,group):
        if label==f'slot-{self.old_index}-accepted':
            changed=copy.deepcopy(group)
            for node in self.voters:
                original=self.group[node]
                if 'applied-end' in original:
                    retire(original,self.carried_entry,self.carried_payload)
                    changed[node]=p.data.staging.without_staging(changed[node])
            self.group=p.maintain(changed,self.voters)
        else:super().snapshot(label,group)


def physical(root,kind):
    root=Path(root);walk,entry,payload=t.prelude(root,kind);index,campaigns,_=t.shape(kind)
    group=cold(walk.group,entry,payload);b.match(root,'life-1-opened',group)
    group,voters=p.campaign(root,group,1,1,walk.counter+1,entry)
    group=interrupted(walk,group,voters,entry,payload,kind)
    b.match(root,'at-cut',group);b.match(root,'before-reopen',group)
    group=cold(group,entry,payload);b.match(root,'life-2-opened',group)
    slot=RecoveredSlot.__new__(RecoveredSlot);slot.__dict__.update(walk.__dict__)
    slot.root=p.View(root,2);slot.old_index=index;slot.carried_entry=entry;slot.carried_payload=payload;slot.group=group
    for ordinal,index in enumerate(range(index,8),1):
        slot.group,voters=p.campaign(root,slot.group,2,ordinal,walk.counter+ordinal+1,entry if ordinal==1 else None,maintenance=maintain)
        if ordinal>1:slot.group=p.maintain(slot.group,voters)
        slot.voters=voters;slot.active=list(voters);slot.first=None
        operation={5:'INTENT',6:'FINAL',7:'BARRIER'}[index]
        slot.publish(operation,None if operation=='BARRIER' else t.command(slot,operation))
    b.match(root,'life-2-ready',slot.group);b.match(root,'after-close',slot.group)
    return dict(status='PARTIAL',kind=kind,cut=CUT,originalPrefixReplayed=True,snapshotByteReplay=True,
        campaigns=1+campaigns,freshStableBarrier=True,fullForceReplay=False,fullWireReplay=False,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=p.process.collection.inventory(root)
    original=p.process.validate_application(root);storage=physical(root,original['kind'])
    need(before==p.process.collection.inventory(root),'context application original changed')
    return dict(status='PARTIAL',process=original,physical=storage,phase3Complete=False)


NEGATIVES={
    'old-entry':'carried transition original command',
    'old-ack':'admitted exact at-cut: node-1',
    'old-certificate':'admitted exact at-cut: node-1',
    'old-catalog':'admitted exact at-cut: node-1',
    'peer-ack':'admitted exact at-cut: node-2',
    'cold-ack':'admitted exact life-2-opened: node-1',
    'lost-retained-certificate':'admitted exact life-2-installed-1: node-1',
    'new-ack':'admitted exact applied-{index}: node-1',
    'published-ledger':'admitted exact published-{index}: node-2',
}


def mutate(root,name):
    index=t.shape(p.process.read(root/'process/result.json')['carriedKind'])[0]
    paths={
        'old-entry':[f'entry-{index}.gsr'],
        'old-ack':[f'{at}/node-1/applied-end/ack.gsr' for at in ('at-cut','before-reopen')],
        'old-certificate':[f'{at}/node-1/applied-end/certificate.gsr' for at in ('at-cut','before-reopen')],
        'old-catalog':[f'{at}/node-1/applied-end/catalog.gsr' for at in ('at-cut','before-reopen')],
        'peer-ack':[f'{at}/node-2/unobserved-ack.gsr' for at in ('at-cut','before-reopen')],
        'cold-ack':['life-2-opened/node-1/applied-end/ack.gsr'],
        'new-ack':[f'life-2-applied-{index}/node-1/applied-end/ack.gsr'],
        'published-ledger':[f'life-2-published-{index}/node-2/'+d.s.FILE],
    }
    if name=='lost-retained-certificate':
        at=root/'life-2-installed-1/node-1';_,members,_=c.current(c.inventory(at))
        basis=f.decode(members['basis.gsr'],'records','BASIS')
        (at/'sources'/basis['basisId']/'source.gscp').write_bytes(b'changed retained certificate source')
    else:
        for path in paths[name]:(root/path).write_bytes(b'changed original')


def qualify(root):
    root=Path(root);before=p.process.collection.inventory(root);original=validate(root)
    index=t.shape(original['physical']['kind'])[0];results=[]
    for name,expected in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-application-negative-') as temp:
            target=Path(temp)/'copy';shutil.copytree(root,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:need(str(error)==expected.format(index=index),'context application unrelated negative: '+name+': '+str(error))
            else:raise ValueError('context application accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=expected.format(index=index)))
    need(before==p.process.collection.inventory(root),'context application negatives changed original')
    return dict(original=original,negatives=results,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
