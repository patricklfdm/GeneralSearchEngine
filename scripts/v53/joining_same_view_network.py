"""Original same-view selected recovery: transport and durable installation ACKs.

Storage is independently derived first. This is one observed 3-REPLACE history,
not full export/maintenance composition or a process-death qualification.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_same_view_physical as physical
from . import joining_network_evidence as network
from . import joining_profile_network_evidence as profiles

need, collection, f, sha = network.need, network.s.collection, network.f, network.sha
SELECTION = 'joining-final-recovery-selection.gsr'
NEGATIVES = {
    'recovery-early-selection':'joining network selection before delivered promises',
    'recovery-missing-grant-force':'joining network durable grant order',
    'recovery-missing-remote-image-force':'joining network durable installation order',
    'recovery-early-ACK':'joining network durable installation order',
    'recovery-wrong-ACK-cut':'joining network installation authority',
    'recovery-missing-local-selection-return':'joining network recovery local selection return',
    'recovery-missing-local-reservation':'joining network recovery local installation order',
    'recovery-local-before-delivered-ACK':'joining network recovery local installation order',
    'recovery-local-wrong-lifetime':'joining network recovery local installation order',
    'recovery-missing-local-member-force':'joining network recovery local installation order',
    'recovery-duplicate-local-force':'joining network recovery local installation order',
    'recovery-unbound-selection-force':'joining network unbound selection force',
}


def observed(root):
    raw = physical.semantic.snapshot.s.regular(Path(root)/SELECTION,65536)
    return network.network(root,size=3,kind='REPLACE',recovery=raw)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    derived=physical.validate(root);result=observed(root)
    need(collection.inventory(root)==before,'joining same-view network original changed')
    return dict(status='PARTIAL',scope='original-same-view-network-and-durable-ACKs',profile='3-REPLACE',
        physicalContinuation=derived,network=result,observedNetworkQualified=True,durableACKsQualified=True,
        recoveryLocalInstallationQualified=True,completeControlExportQualified=False,
        maintenanceAndPeerCompositionQualified=False,sameViewPhysicalQualified=False,
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


def move_before(events,index,before):
    # Equal event dictionaries recur across campaigns. Use the chosen original
    # occurrence, not list.index equality (which would mutate an earlier round).
    target=next(i for i,value in enumerate(events) if value is before)
    value=events.pop(index);events.insert(target-(index<target),value)


def mutate(root,name):
    root=Path(root)
    if name not in NEGATIVES:profiles.mutate(root,name);return
    events=collection.read_json(root,'events.json',collection.EVENT_BYTES)
    wires=collection.read_json(root,'wire.json',collection.WIRE_BYTES)
    selected=f.decode((root/SELECTION).read_bytes(),'records','SELECTED');digest=sha((root/SELECTION).read_bytes())
    own=selected['ballot']['proposer']
    row=next(v for v in wires if network.wire(v['request'])[0]=='SELECTED' and
             network.wire(v['request'])[1]['payload']==dict(selection=digest))
    peer=network.wire(row['request'])[1]['recipient']['node']
    def last(event,node):
        return max(i for i,v in enumerate(events) if v['event']==event and v.get('node')==node and
                   v.get('scope')!= 'stable-cold-owner')
    def move(index,before):
        move_before(events,index,before)
    if name=='recovery-early-selection':
        promise=next(v for v in wires if network.wire(v['request'])[0]=='PREPARE' and
                     network.wire(v['request'])[1]['ballot']==selected['ballot'])
        response=sha(base64.b64decode(promise['response']))
        delivery=next(v for v in events if v.get('response')==response and v['event'] in ('NETWORK_RECEIVED','AFTER_RESPONSE_READ'))
        move(last('SELECTED_FORCED',own),delivery)
    elif name=='recovery-missing-grant-force':events.pop(last('BASIS_FORCED',peer))
    elif name=='recovery-missing-remote-image-force':events.pop(last('INSTALL_IMAGE_FORCED',peer))
    elif name=='recovery-early-ACK':
        response=sha(base64.b64decode(row['response']))
        index=next(i for i,v in enumerate(events) if v.get('response')==response and v['event']=='WIRE_RESPONSE')
        move(index,events[last('CURRENT_DIRECTORY_FORCED',peer)])
    elif name=='recovery-wrong-ACK-cut':
        old=sha(base64.b64decode(row['response']));kind,value=network.wire(row['response']);value['payload']['cut']['index']-=1
        raw=f.encode('wire',kind,value);row['response']=base64.b64encode(raw).decode()
        for event in events:
            if event.get('response')==old:event['response']=sha(raw)
    elif name=='recovery-local-before-delivered-ACK':
        response=sha(base64.b64decode(row['response']))
        delivery=next(v for v in events if v.get('response')==response and v['event']=='AFTER_RESPONSE_READ')
        move(last('INSTALL_RESERVED',own),delivery)
    elif name=='recovery-local-wrong-lifetime':events[last('INSTALL_MEMBER_FORCED',own)]['scope']='foreign-owner'
    elif name=='recovery-duplicate-local-force':
        i=last('INSTALL_MEMBER_FORCED',own);events.insert(i,dict(events[i]))
    elif name=='recovery-unbound-selection-force':
        i=last('SELECTED_FORCED',own);events.insert(i,dict(events[i],node='foreign-owner'))
    else:
        event={'recovery-missing-local-selection-return':'SELECTED_BEFORE_RETURN',
               'recovery-missing-local-reservation':'INSTALL_RESERVED',
               'recovery-missing-local-member-force':'INSTALL_MEMBER_FORCED'}[name]
        events.pop(last(event,own))
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wires))


def qualify(root,progress=None):
    root=Path(root);original=validate(root);before=collection.inventory(root);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    cases={**network.NEGATIVES,**NEGATIVES}
    if profiles.terminal_pair(root) is not None:cases.update(profiles.TERMINAL_NEGATIVES)
    files={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-same-view-network-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            after=collection.inventory(copied)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==files and
                 after['directories']==before['directories'],'joining same-view network negative changed physical inputs')
            try:observed(copied)
            except ValueError as error:
                need(str(error)==reason,'joining same-view unrelated network negative: '+name+': '+str(error))
            else:raise ValueError('joining same-view network accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(results[-1],completed=len(results),total=len(cases)))
    need(collection.inventory(root)==before,'joining same-view network qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root),sort_keys=True))
