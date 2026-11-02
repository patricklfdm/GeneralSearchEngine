"""Original competing-owner exports bound to derived generation/source windows.

The complete physical and network replay is mandatory. A received losing
SELECTED is authorized only through its actual DATA response, never as COMMIT.
This gate establishes observed availability, not expiry/close fault coverage.
"""
import argparse
import base64
from collections import Counter
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from . import competing_activation_network as activation
from . import joining_export_evidence as exports
from . import joining_transcript as transcript

e=exports;f=activation.f;disk=activation.disk;need=activation.need;sha=activation.sha


def generation_windows(events,history):
    result=[]
    for node,initial in history.initial.items():
        changes=[]
        if node in history.voters:
            changes=[('INSTALL_BEFORE_RETURN',history.installed[node])]
            changes += [('PUBLICATION_BEFORE_RETURN',history.snapshots[f'slot-{i}-published'][node]) for i in (1,2)]
        renames=[i for i,v in enumerate(events) if v==dict(node=node,event='INSTALL_SELECTOR_RENAMED')]
        returns=[(i,v['event']) for i,v in enumerate(events) if v.get('node')==node and
                 v['event'] in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN')]
        need(len(renames)==len(returns)==len(changes) and [v for _,v in returns]==[v for v,_ in changes],
             'competing export complete generation timeline')
        def add(files,start,end):
            need(start<end,'competing export generation lifetime')
            prefix,members,packet=disk.current(files);identity=f.decode(files['node.gsr'],'records','NODE')['identity']
            need(identity['node']==node,'competing export generation owner')
            result.append(dict(node=node,start=start,end=end,members=members,packet=packet,
                               manifest=files[prefix+'generation.gsr'],identity=identity))
        add(initial,-1,renames[0] if renames else len(events))
        for i,((_,files),(returned,_)) in enumerate(zip(changes,returns)):
            need(renames[i]<returned and (i==0 or returns[i-1][0]<renames[i]),
                 'competing export selector completion order')
            add(files,returned,renames[i+1] if i+1<len(renames) else len(events))
    return result


def source_windows(replay):
    result=[]
    for cap in replay.by_basis.values():
        files=replay.original[cap['basisSha256']];prefix='sources/'+cap['basisId']+'/'
        members={k[len(prefix):]:v for k,v in files.items() if k.startswith(prefix)}
        result.append(dict(node=cap['node'],start=cap['capturedEvent'],end=activation.end_of_source(replay,cap),
            basis=cap['basis'],promise=cap['promise'],value=f.decode(cap['basis'],'records','BASIS'),
            packet=disk.p.decode(members['source.gscp']),members=members))
    return result


def record_windows(replay,history,windows,sources):
    phases=[disk.pending(history.snapshots[f'slot-{i}-applied'][history.proposer]['pending.accept'],
                         ('PROOF','CERTIFICATE'))[0] for i in (1,2)]
    model=SimpleNamespace(root=history.selected['root'],phases=phases,old=tuple(history.initial),joining=None,
        owner=lambda stage,index,node:history.snapshots[f'slot-{index}-{stage}'][node])
    # A selected voter is not evidence that it stored SELECTED. In the losing
    # campaign node-2 receives bytes but never forces that decision locally.
    records=e.record_windows(replay.root,replay.events,model,windows,sources,nodes=(),selection_records=[])
    for bound in replay.bindings:
        raw=replay.selections[bound['selection']]['raw'];value=f.decode(raw,'records','SELECTED')
        held=[v for v in sources if v['node']==bound['node'] and v['value']['ballot']==value['ballot']]
        need(len(held)==1 and held[0]['start']<bound['forced']<held[0]['end'],
             'competing export original durable selection lifetime')
        records.append(dict(node=bound['node'],start=bound['forced'],end=held[0]['end'],raw=raw,
                            reference=sha(raw),ballot=None,view=None,family='journal'))
    return records


def transfer_contents(replay):
    """Separate the already checked incomplete selection from complete transfers."""
    successful={v['request']['trace'] for v in replay.rows if v['answer']=='INSTALL_ACK'}
    losing=[v for v in replay.attempts if v['kind']=='SELECTED' and v['request']['trace'] not in successful]
    need(len(losing)<=1,'competing export original incomplete selection')
    if not losing:
        contents=[];counts=transcript.transfers(replay.rows,contents=contents)
        return contents,None,counts
    choice=losing[0]['request']['payload']['selection']
    offers=[v for v in replay.rows if v['answer']=='SOURCE_OFFER' and v['request']['payload']['digest']==choice]
    need(len(offers)==1,'competing export incomplete selection offer');offer=offers[0]
    trace=offer['request']['trace'];rows=[v for v in replay.rows if v['request']['trace']==trace]
    need(len(rows)==2 and rows[0] is offer and rows[1]['answer']=='CHUNK',
         'competing export incomplete selection response prefix')
    raw=base64.b64decode(rows[1]['response']['payload']['bytes'],validate=True)
    need(raw==replay.selections[choice]['raw'] and offer['response']['payload']['kind']=='RECORD',
         'competing export incomplete original decision bytes')
    contents=[];counts=transcript.transfers([v for v in replay.rows if v['request']['trace']!=trace],contents=contents)
    partial=dict(offer=offer,raw=raw,kind='RECORD',through=rows[1]['offered'])
    return contents,partial,counts


def authorize_session(values,windows,sources,records):
    first=values[0];kind=e.record_kind(first['raw'])
    if kind=='GENERATION' or first['kind']=='CAPSULE':return e.authorize_generation(values,windows)
    if kind=='BASIS':
        e.authorize_source(values,windows,sources);return 'frozen-source'
    return e.authorize_record(values,windows,records)


def authorize(groups,partial,windows,sources,records):
    families=Counter();transfers=Counter()
    for values in groups:
        scope=authorize_session(values,windows,sources,records)
        families[scope]+=1;transfers[scope]+=len(values)
    need(families['current-generation'] and families['frozen-source'], 'competing export required original families')
    scope=None
    if partial is not None:
        need('commit' not in partial,'competing export incomplete transfer cannot commit')
        scope=e.authorize_record_interval(partial,windows,records,partial['through'])
        need(scope=='journal','competing export incomplete original journal authority')
    return dict(boundSessions=dict(families),boundTransfers=dict(transfers),
                incompleteTransfers=int(partial is not None),incompleteFamily=scope,incompleteTransferCommitted=False,unqualifiedTransfers=0)


class Replay:
    def __init__(self,root):self.root=Path(root)

    def run(self):
        gate=activation.Replay(self.root);self.precondition=gate.run();self.replay=gate.replay
        history=gate.original.history
        self.windows=generation_windows(self.replay.events,history)
        self.sources=source_windows(self.replay)
        self.records=record_windows(self.replay,history,self.windows,self.sources)
        contents,self.partial,counts=transfer_contents(self.replay);self.groups=e.sessions(contents)
        result=authorize(self.groups,self.partial,self.windows,self.sources,self.records)
        need(sum(result['boundTransfers'].values())==counts['committedTransfers'],
             'competing export complete transfer coverage')
        return dict(status='PARTIAL',scope='competing-bootstrap-observed-temporal-exports',precondition=self.precondition,
            generationWindows=len(self.windows),sourceWindows=len(self.sources),recordWindows=len(self.records),
            transport=counts,**result,observedTemporalExportAuthorityQualified=True,
            completeExportLifetimesQualified=False,processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False)


def validate(root):
    inventory=activation.publication.preceding.prefix.collection.h.inventory
    before=inventory(Path(root));result=Replay(root).run()
    need(inventory(Path(root))==before,'competing export original changed');return result


NEGATIVES={
    'generation-alias':'joining export current generation alias',
    'generation-bytes':'joining export exact current generation',
    'generation-missing-member':'joining export exact current generation',
    'generation-after-selector':'joining export inactive current generation',
    'generation-storage':'joining export current permanent identities',
    'source-alias':'joining export original source alias',
    'source-ballot':'joining export original source view/ballot',
    'source-promise':'joining export exact frozen source',
    'source-before-capture':'joining export inactive frozen source',
    'source-after-window':'joining export inactive frozen source',
    'receipt-alias':'joining export unavailable original record',
    'receipt-bytes':'joining export exact live record',
    'receipt-ballot':'joining export exact live record',
    'receipt-before-force':'joining export unavailable original record',
    'pending-payload-bytes':'joining export exact live record',
    'pending-record-view':'joining export record original context',
    'checkpoint-before-apply':'joining export unavailable original record',
    'checkpoint-after-window':'joining export inactive current generation',
    'journal-after-retirement':'joining export unavailable original record',
    'published-bytes':'joining export exact published record',
    'partial-before-selection':'joining export unavailable original record',
    'partial-after-retirement':'joining export unavailable original record',
    'partial-received-at-retirement':'joining export unavailable original record',
    'partial-bytes':'joining export exact live record',
    'partial-view':'joining export record original context',
    'partial-other-owner':'joining export unavailable original record',
}


def negative_claim(reader,name):
    """Alter a derived export claim, not the native events or physical inputs.

    These exercise the capability reader independently of the preceding wire
    gate (which would reject a changed transcript earlier). Never advertise
    these as native executions or fault-injection histories.
    """
    need(name in NEGATIVES or name=='journal-after-history','competing export unknown capability negative')
    windows,sources,records=reader.windows,reader.sources,reader.records
    if name.startswith('partial-'):
        partial=copy.deepcopy(reader.partial);q=partial['offer']['request']
        held=next(v for v in records if v['reference']==q['payload']['digest'] and v['node']==q['recipient']['node'])
        if name=='partial-before-selection':partial['offer']['received']=held['start']
        elif name=='partial-after-retirement':partial['through']=held['end']
        elif name=='partial-received-at-retirement':partial['offer']['received']=partial['through']=held['end']
        elif name=='partial-bytes':partial['raw']+=b'changed'
        elif name=='partial-view':q['view']='f'*64
        elif name=='partial-other-owner':q['recipient'],q['sender']=q['sender'],q['recipient']
        return e.authorize_record_interval(partial,windows,records,partial['through'])
    prefix=name.split('-')[0]
    if prefix=='generation':
        original=next(v for v in reader.groups if e.record_kind(v[0]['raw'])=='GENERATION')
    elif prefix=='source':original=next(v for v in reader.groups if e.record_kind(v[0]['raw'])=='BASIS')
    else:
        family={'receipt':'native-vote-receipt','pending':'pending-payload' if name.startswith('pending-payload') else 'pending-record',
                'checkpoint':'native-applied-checkpoint','journal':'journal','published':'published-record'}[prefix]
        original=next(v for v in reader.groups if len(v)==1 and authorize_session(v,windows,sources,records)==family
                      and (name!='journal-after-retirement' or any(z['reference']==v[0]['offer']['request']['payload']['digest'] and
                           z['node']==v[0]['offer']['request']['recipient']['node'] and z['end']<len(reader.replay.events) for z in records)))
    values=copy.deepcopy(original);first=values[0];q=first['offer']['request'];reference=q['payload']['digest']
    own=e.current(windows,q['recipient']['node'],first['offer']['received'],values[-1]['commit']['offered'])
    held=next((v for v in records if v['node']==q['recipient']['node'] and v['reference']==reference),None)
    source=next((v for v in sources if v['node']==q['recipient']['node'] and sha(v['basis'])==reference),None)
    if name.endswith('-alias'):q['payload']['digest']='f'*64
    elif name.endswith('-bytes'):first['raw']+=b'changed'
    elif name.endswith('-ballot'):q['ballot']['counter']+=1
    elif name=='generation-missing-member':values.pop()
    elif name=='generation-after-selector':values[-1]['commit']['offered']=own['end']
    elif name=='generation-storage':q['ballot']['incarnation']='00000000-0000-0000-0000-000000000099'
    elif name=='source-promise':values[1]['raw']+=b'changed'
    elif name=='source-before-capture':first['offer']['received']=source['start']
    elif name=='source-after-window':values[-1]['commit']['offered']=source['end']
    elif name in ('receipt-before-force','checkpoint-before-apply'):first['offer']['received']=held['start']
    elif name=='checkpoint-after-window':values[-1]['commit']['offered']=held['end']
    elif name=='pending-record-view':q['view']='f'*64
    elif name in ('journal-after-retirement','journal-after-history'):values[-1]['commit']['offered']=held['end']
    if prefix=='generation':return e.authorize_generation(values,windows)
    if prefix=='source':return e.authorize_source(values,windows,sources)
    return e.authorize_record(values,windows,records)


def negative_cases(reader):
    cases=dict(NEGATIVES);not_applicable={}
    if reader.partial is None:
        for name in tuple(cases):
            if name.startswith('partial-'):
                not_applicable[name]='Original history has no incomplete SELECTED transfer.';del cases[name]
    if not any(v['retiredSources'] for v in reader.replay.transactions):
        cases.pop('journal-after-retirement')
        not_applicable['journal-after-retirement']='Original history has no source retirement.'
        cases['journal-after-history']='joining export inactive current generation'
    return cases,not_applicable


def qualify(root):
    inventory=activation.publication.preceding.prefix.collection.h.inventory;root=Path(root);before=inventory(root)
    reader=Replay(root);original=reader.run();outcomes=[]
    cases,not_applicable=negative_cases(reader)
    for name,reason in cases.items():
        try:negative_claim(reader,name)
        except ValueError as error:need(str(error)==reason,'unrelated competing export negative: '+name+': '+str(error))
        else:raise ValueError('competing export capability mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason))
    # Claims are deep copies. Recheck the unchanged original derived inputs,
    # as well as the on-disk native bytes, after all hostile claims.
    need(authorize(reader.groups,reader.partial,reader.windows,reader.sources,reader.records)==
         {k:original[k] for k in ('boundSessions','boundTransfers','incompleteTransfers','incompleteFamily',
          'incompleteTransferCommitted','unqualifiedTransfers')},'competing export negative changed derived original')
    need(inventory(root)==before,'competing export negative changed native original')
    return dict(original=original,negativeScope='derived-capability-claims-not-native-faults',negatives=outcomes,
                notApplicable=not_applicable)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
