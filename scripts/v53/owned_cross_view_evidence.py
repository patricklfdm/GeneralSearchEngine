"""Replay original REMOVE histories before binding complete TCP adoption and native reopen.

The storage walk still drives votes explicitly. These histories qualify native
ownership and received-prefix adoption, not autonomous membership or public READY.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import admitted_cross_view_evidence as x
from . import prefix_discovery_evidence as p
from . import promised_source_evidence as t

b=x.b;e=b.e;c=b.c


def load(path,maximum=4*e.MIB):
    return e.parse(b.t.plans.read(path,maximum))


def same(actual,expected,message):
    e.need(e.f.canonical(actual)==e.f.canonical(expected),message)


def transfer(history,root,size,number):
    removed=f'node-{size-number+1}';slot=7+8*(number-1)
    # The caller already reconstructed and matched these complete original files.
    before=c.inventory(history/f'slot-{slot}-settled'/removed)
    source=c.inventory(history/f'slot-{slot}-settled/node-1')
    after=c.inventory(history/f'removed-{number}-adopted'/removed)
    source_prefix,members,packet=c.current(source);cap=packet['capsule']
    adopted_prefix,_,adopted=c.current(after)
    expected={'source.gscp':members['source.gscp'],**{h+'.image':members[h+'.image'] for h in packet['images']},
              'manifest.gsr':source[source_prefix+'generation.gsr'],'ancestry.gsr':members.get('ancestry.gsr',b''),
              'adopted.gsr':after[adopted_prefix+'generation.gsr']}
    b.selection.layout(root,set(expected)|{'prefix-wire.json','ancestry-wire.json','source-events.json','reopened.json'},'owned cross-view transfer')
    for name,raw in expected.items():
        e.need(b.t.plans.read(root/name,64*e.MIB)==raw,'owned cross-view exact '+name)
    same(load(root/'source-events.json'),[],'owned cross-view source authority writes')
    rows=load(root/'prefix-wire.json');prefix_count=p.transcript(rows,{'node-1':before,'node-2':source})
    _,local,old=c.current(before);ballot=e.f.decode(local['selected.gsr'],'records','SELECTED')['ballot']
    sender=e.f.decode(before['node.gsr'],'records','NODE')['identity'];recipient=e.f.decode(source['node.gsr'],'records','NODE')['identity']
    ancestry=load(root/'ancestry-wire.json');e.need(bool(ancestry),'owned cross-view missing ancestry exchange')
    trace=t.t.wire(ancestry[0]['request'])[1]['trace']
    e.need(all(trace!=t.t.wire(row['request'])[1]['trace'] for row in rows),'owned cross-view distinct session')
    reference=e.digest(e.f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-ancestry')))
    originals=[(reference,expected['manifest.gsr'],'RECORD')]
    if expected['ancestry.gsr']:originals.append((e.digest(expected['ancestry.gsr']),expected['ancestry.gsr'],'RECORD'))
    count=t.transcript(ancestry,originals,cap['root'],e.authority(cap['root'],old['capsule']['cut']['view']),ballot,sender,recipient,
                       'owned cross-view ancestry',chunk_bytes=4*e.MIB)
    reopened=load(root/'reopened.json',65536);events=reopened.get('events')
    e.need(type(events) is list and 0<len(events)<=4096 and all(type(v) is str for v in events),'owned cross-view reopen events')
    e.need(not any(v.startswith(('PROMISE_','BASIS_','SELECTED_','ADOPTION_','INSTALL_')) for v in events),'owned cross-view reopened authority writes')
    manifest=e.f.decode(expected['adopted.gsr'],'records','GENERATION')
    same(reopened,dict(status='PASS',manifest=e.digest(expected['adopted.gsr']),cut=adopted['capsule']['cut'],basisAbsent=True,selectionAbsent=True,
                       promise=manifest['promise'],refusal='activation requires current voter',floorRefusal='floor copy is not a governing voter',events=events),'owned cross-view exact native reopen')
    return dict(node=removed,prefixExchanges=prefix_count,ancestryExchanges=count)


def validate(directory):
    root=Path(directory);b.selection.layout(root,{'histories','transfers','receipt.json'},'owned cross-view root')
    original=x.validate(root/'histories')  # Actual votes/images/fences must pass before any copied proof.
    names=[f'size-{s}-{kind}' for s in (5,4) for kind in ('empty','backup')]
    b.selection.layout(root/'transfers',set(names),'owned cross-view profiles');rows=[]
    for name in names:
        size=int(name[5]);copies=root/'transfers'/name
        b.selection.layout(copies,{f'remove-{n}' for n in range(1,size-2)},'owned cross-view removals')
        for number in range(1,size-2):rows.append(transfer(root/'histories'/name,copies/f'remove-{number}',size,number))
    expected=dict(schema='gse-v53-owned-cross-view-v1',status='PASS',publicRuntime=False,profiles=4,historicalObservationsSupplied=False,tcpAdoptions=6,freshProcesses=6)
    same(load(root/'receipt.json',65536),expected,'owned cross-view receipt')
    return dict(status='PASS',profiles=4,tcpAdoptions=len(rows),freshProcesses=6,slots=original['slots'],publicRuntime=False,originalFirst=True)


VARIANTS={
    'scope':'owned cross-view receipt',
    'missing-profile':'context selection owned cross-view profiles inventory',
    'original-fence':'admitted exact removed-1-adopted: node-5',
    'source-packet':'owned cross-view exact source.gscp',
    'source-image':'owned cross-view exact ',
    'source-manifest':'owned cross-view exact manifest.gsr',
    'adopted':'owned cross-view exact adopted.gsr',
    'source-writes':'owned cross-view source authority writes',
    'hint':'prefix discovery original cut',
    'bytes':'prefix exact data',
    'commit':'prefix exact commit',
    'ancestry-owner':'owned cross-view ancestry correlation',
    'ancestry-truncated':'owned cross-view ancestry incomplete transcript',
    'reopen-manifest':'owned cross-view exact native reopen',
    'reopen-vote':'owned cross-view exact native reopen',
    'reopen-events':'owned cross-view reopened authority writes',
}


def qualify(directory):
    original=validate(directory);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-owned-cross-view-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target)
            root=target/'transfers/size-5-empty/remove-1'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['publicRuntime']=True;path.write_bytes(e.f.canonical(value))
            elif name=='missing-profile':shutil.rmtree(target/'transfers/size-4-backup')
            elif name=='original-fence':
                (target/'histories/size-5-empty/removed-1-adopted/node-5/grants.gsr').write_bytes(b'changed')
            elif name in ('source-packet','source-image','source-manifest','adopted'):
                path=next(root.glob('*.image')) if name=='source-image' else root/ {'source-packet':'source.gscp','source-manifest':'manifest.gsr','adopted':'adopted.gsr'}[name]
                path.write_bytes(b'changed')
            elif name=='source-writes':(root/'source-events.json').write_bytes(e.f.canonical(['PROMISE_FORCED']))
            elif name.startswith('reopen-'):
                path=root/'reopened.json';value=load(path)
                if name=='reopen-manifest':value['manifest']='a'*64
                elif name=='reopen-vote':value['basisAbsent']=False
                else:value['events'].append('PROMISE_FORCED')
                path.write_bytes(e.f.canonical(value))
            else:
                path=root/('ancestry-wire.json' if name.startswith('ancestry-') else 'prefix-wire.json');rows=load(path)
                if name=='ancestry-truncated':rows.pop()
                else:
                    index=0 if name in ('hint','ancestry-owner') else len(rows)-1 if name=='commit' else next(i for i,row in enumerate(rows) if t.t.wire(row['response'])[0]=='CHUNK')
                    kind,value=t.t.wire(rows[index]['response'])
                    if name=='hint':value['payload']['cut']['index']+=1
                    elif name=='bytes':value['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
                    elif name=='commit':value['payload']['digest']='a'*64
                    else:value['sender']=value['recipient']
                    rows[index]['response']=base64.b64encode(e.f.encode('wire',kind,value)).decode()
                path.write_bytes(e.f.canonical(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'owned cross-view unrelated negative: '+name+': '+str(error))
            else:raise ValueError('owned cross-view accepted negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');a=parser.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
