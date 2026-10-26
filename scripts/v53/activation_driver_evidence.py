"""Replay automatic outgoing activation using original storage and wire bytes.

Independent physical selection/install validation is shared with the incoming
endpoint oracle. Only the concurrent control order and actual local image reuse
profile differ. Successful stable profiles are not full distributed qualification.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import activation_endpoint_evidence as endpoint
p=endpoint.p
e=endpoint.e
load=endpoint.load


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'driver evidence directory')
    names={'receipt.json'}|{f'stable-{n}' for n in (3,4,5)}|{f'stable-{n}-network.json' for n in (3,4,5)}
    e.need({p.name for p in root.iterdir()}==names,'driver complete inventory')
    cases=[endpoint.case(root,n,borrow_images=True,concurrent_controls=True,chunk_bytes=4*e.MIB) for n in (3,4,5)]
    expected=dict(schema='gse-v53-activation-driver-v1',status='PASS',cases=[v[0] for v in cases],network=True,publicRuntime=False,automaticCampaign=True)
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'driver scope/receipt')
    return dict(original=expected,sourceExchanges=sum(v[1] for v in cases))


def qualify(directory):
    original=validate(directory);results=[]
    mutations=[('scope','driver scope/receipt'),('missing-profile','driver complete inventory'),
               ('missing-ack','activation exchange inventory'),('missing-install','activation exact installed bytes'),
               ('control-delivery','endpoint original control delivery'),('missing-source','endpoint missing source transfer'),
               ('duplicate-source','endpoint unexpected/duplicate source transfer'),('wrong-source','endpoint source correlation'),
               ('changed-data','endpoint source exact data'),('missing-force','activation force order')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-endpoint-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['automaticCampaign']=False;path.write_text(json.dumps(value))
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
            except ValueError as error:e.need(reason in str(error),'driver unrelated negative: '+name+': '+str(error))
            else:raise ValueError('driver accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
