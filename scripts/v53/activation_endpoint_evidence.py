"""Replay original installed storage and all receiver-owned TCP exchanges.

These same-view bootstrap histories do not qualify automatic election or READY.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import promised_source_evidence as p

a=p.a
e=p.e
c=p.c
b=p.b
load=p.load


def case(root,size,*,borrow_images=False,concurrent_controls=False,chunk_bytes=1024):
    directory=root/f'stable-{size}';result=a.case(directory,size)
    before=b.original(directory,size,False);_,initial,packet=c.current(before['node-1'])
    selected=(directory/'selected.gsr').read_bytes();selection=e.f.decode(selected,'records','SELECTED')
    names=[v['voter'] for v in selection['sources']]
    identities={n:e.f.decode(v['node.gsr'],'records','NODE')['identity'] for n,v in before.items()}
    records={}
    for node in names:
        rows=c.journal((directory/'installed'/node/'grants.gsr').read_bytes(),selection['root'],node)
        records[node]={kind:raw for kind,raw,_ in rows[-3:]}
    controls=load(directory/'wire.json');control_trace=p.t.wire(controls[0]['request'])[1]['trace']
    groups={}
    for row in load(root/f'stable-{size}-network.json'):
        e.need(set(row)=={'request','response'},'endpoint network row')
        _,request=p.t.wire(row['request']);groups.setdefault(request['trace'],[]).append(row)
    observed=groups.pop(control_trace,None)
    if concurrent_controls and observed is not None:
        observed=sorted(observed,key=lambda row:p.t.wire(row['request'])[1]['sequence'])
    e.need(observed==controls,'endpoint original control delivery')
    # Expected transfers are derived from original owners and the fixed selection,
    # not from whatever references happen to be offered in the network trace.
    expected={}
    for receiver in names[1:]:
        expected[(receiver,'node-1',e.digest(records['node-1']['PROMISE']))]=[(e.digest(records['node-1']['PROMISE']),records['node-1']['PROMISE'],'RECORD')]
        expected[(receiver,'node-1',e.digest(selected))]=[(e.digest(selected),selected,'RECORD')]
        for reader,source,with_images in [('node-1',receiver,not borrow_images)]+[(receiver,source,False) for source in names if source!=receiver]:
            values=[(e.digest(records[source][kind]),records[source][kind],'RECORD') for kind in ('BASIS','PROMISE')]
            values.append((e.digest(packet['capsuleBytes']),initial['source.gscp'],'CAPSULE'))
            if with_images:values.extend((h,initial[h+'.image'],'APPLICATION') for h in sorted(packet['images']))
            expected[(reader,source,values[0][0])]=values
    count=0
    for rows in groups.values():
        kind,request=p.t.wire(rows[0]['request']);e.need(kind=='CHUNK','endpoint transfer first kind')
        key=(request['sender']['node'],request['recipient']['node'],request['payload']['digest'])
        # The independent format uses full immutable identities in transcript().
        e.need(key in expected,'endpoint unexpected/duplicate source transfer')
        contents=expected.pop(key)
        count+=p.transcript(rows,contents,selection['root'],selection['view'],selection['ballot'],identities[key[0]],identities[key[1]],'endpoint source',chunk_bytes=chunk_bytes)
    e.need(not expected,'endpoint missing source transfer')
    return dict(size=size,selected=result['selected'],installed=result['installed']),count


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'endpoint evidence directory')
    names={'receipt.json'}|{f'stable-{n}' for n in (3,4,5)}|{f'stable-{n}-network.json' for n in (3,4,5)}
    e.need({p.name for p in root.iterdir()}==names,'endpoint complete inventory')
    cases=[case(root,n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-activation-endpoint-v1',status='PASS',cases=[v[0] for v in cases],network=True,publicRuntime=False,automaticCampaign=False)
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'endpoint scope/receipt')
    return dict(original=expected,sourceExchanges=sum(v[1] for v in cases))


def qualify(directory):
    original=validate(directory);results=[]
    mutations=[('scope','endpoint scope/receipt'),('missing-profile','endpoint complete inventory'),
               ('missing-ack','activation exchange inventory'),('missing-install','activation exact installed bytes'),
               ('control-delivery','endpoint original control delivery'),('missing-source','endpoint missing source transfer'),
               ('duplicate-source','endpoint unexpected/duplicate source transfer'),('wrong-source','endpoint source correlation'),
               ('changed-data','endpoint source exact data'),('missing-force','activation force order')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-endpoint-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['automaticCampaign']=True;path.write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='missing-ack':
                path=member/'wire.json';value=load(path);value.pop();path.write_text(json.dumps(value))
            elif name=='missing-install':(member/'installed/node-2/selector.gsr').unlink()
            elif name=='missing-force':
                path=member/'events.json';value=load(path);value[1]['events'].remove('INSTALL_BEFORE_RETURN');path.write_text(json.dumps(value))
            else:
                path=target/'stable-3-network.json';rows=load(path)
                trace=p.t.wire(rows[0]['request'])[1]['trace']
                if name=='control-delivery':rows=[v for v in rows if p.t.wire(v['request'])[0]!='SELECTED']
                elif name=='missing-source':rows=[v for v in rows if p.t.wire(v['request'])[1]['trace']!=trace]
                elif name=='duplicate-source':
                    import uuid
                    new=str(uuid.uuid4())
                    for row in list(rows):
                        if p.t.wire(row['request'])[1]['trace']==trace:
                            copy={}
                            for side in ('request','response'):
                                kind,frame=p.t.wire(row[side]);frame['trace']=new;copy[side]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                            rows.append(copy)
                else:
                    index=next(i for i,row in enumerate(rows) if p.t.wire(row['response'])[0]=='CHUNK');kind,frame=p.t.wire(rows[index]['response'])
                    if name=='wrong-source':frame['sender']=p.t.wire(rows[index]['request'])[1]['sender']
                    else:frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    rows[index]['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'endpoint unrelated negative: '+name+': '+str(error))
            else:raise ValueError('endpoint accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
