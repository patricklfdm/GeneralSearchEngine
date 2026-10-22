"""Local round/catalog composition qualification; no Java, CI or cloud work."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from . import steady_model as steady
from . import steady_oracle
from . import catalog_capsule as capsule
from . import catalog_capsule_oracle
from . import activation_research as ar
from . import integrated_research as ir
from . import recovery_research as rr
from . import transition_model as t
from .test_catalog_capsule import fixture
from .membership_model import need

CUTS=('healthy','accept-staged','accept-forced','proof-forced','prefix-forced','higher-fence','leader-restart')


def round_case(size,last,cut):
    r=steady.Round(size,last)
    for i in range(6):r.commit(t.Entry(('DATA','CONTROL','BARRIER')[i%3],payload=str(i)))
    if cut!='healthy':
        r.propose(t.Entry('DATA',payload='interrupted'))
        for n in r.owners:r.stage(n,'ACCEPT')
        if cut!='accept-staged':
            for n in r.owners:r.force(n)
        if cut not in ('accept-staged','accept-forced'):
            for n in r.owners:r.stage(n,'PROOF');r.force(n)
        if cut in ('prefix-forced','higher-fence','leader-restart'):
            cert=r.certify();r.install(r.ballot.proposer,cert)
        if cut=='higher-fence':r.observe(r.ballot.proposer,steady.a.b.Ballot(99,r.owners[-1],'higher'))
        else:r.crash(r.ballot.proposer);r.restart(r.ballot.proposer)
    record=r.evidence();steady_oracle.check(record);return record


def decode_integrated(raw):
    events=[]
    for e in raw['events']:
        e=dict(e)
        if e['event']=='activation':
            e['detail']=ar.decode(dict(root=raw['root'],old=raw['old'],input=[],events=[e['detail']]))['events'][0]
        if e['event']=='apply':
            e['certificate']=rr.decode(dict(old=raw['old'],sourceEvents=[],events=[dict(certificate=e['certificate'])]))['events'][0]['certificate']
        events.append(e)
    return dict(raw,old=tuple(raw['old']),events=events)


def decode_round(raw):
    def fields(value):
        if isinstance(value,list):return [fields(v) for v in value]
        if not isinstance(value,dict):return value
        value={k:fields(v) for k,v in value.items()}
        if set(value)=={'root','index','predecessor','generation','old','new','operation'}:
            return t.Authority(**dict(value,old=tuple(value['old']),new=tuple(value['new'])))
        if set(value)=={'counter','proposer','incarnation'}:return steady.a.b.Ballot(**value)
        return value
    return dict(seed=ar.decode(raw['seed']),events=fields(raw['events']))


def replay(examples):
    expected={f'round/{size}/{int(last)}/{cut}' for size in (3,4,5) for last in (False,True) for cut in CUTS}
    expected|={f'catalog/{size}/{kind}' for size,kind in ir.PROFILES}
    need(set(examples)==expected,'continuity inventory')
    counts=dict(histories=0,roundPublications=0,capsules=0,events=0)
    for name,raw in examples.items():
        if name.startswith('round/'):
            record=decode_round(raw);result=steady_oracle.check(record)
            size=int(name.split('/')[1]);cut=name.split('/')[-1]
            need(len(record['seed']['old'])==size and result['publications']==6,'round profile/result')
            old=record['seed']['old'];majority=size//2+1
            expected=old[:majority] if name.split('/')[2]=='0' else (old[0],)+old[-(majority-1):]
            selected=next(e['decision'] for e in record['seed']['events'] if e['event']=='selection-force')
            need(selected.owners==expected,'round selected-source label')
            final=[e['event'] for e in record['events'][-2:]]
            need((cut=='healthy' and final[-1]=='published') or (cut=='higher-fence' and final[-1]=='observe') or
                 (cut not in ('healthy','higher-fence') and final==['crash','restart']),'round cut label')
            phases=[e for e in record['events'] if e['event']=='force' and e['authority'].index==8]
            want=0 if cut in ('healthy','accept-staged') else len(record['seed']['old'])//2+1
            need(sum(e['phase']=='ACCEPT' for e in phases)==want and
                 sum(e['phase']=='PROOF' for e in phases)==(want if cut in ('proof-forced','prefix-forced','higher-fence','leader-restart') else 0),
                 'round actual force boundary')
            counts['roundPublications']+=result['publications']
        else:
            record=dict(raw,input=decode_integrated(raw['input']));result=catalog_capsule_oracle.check(record)
            size=int(name.split('/')[1]);kind=name.split('/')[2]
            need(len(record['input']['old'])==size and any(e['event']=='command' and e['command']['kind']=='RESERVE' and
                 e['command']['request']['kind']==kind for e in record['input']['events']),'catalog profile')
            counts['capsules']+=result['capsules']
        counts['histories']+=1;counts['events']+=result['events']
    return counts


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);binding=ir.binding();examples={}
    try:
        for size in (3,4,5):
            for last in (False,True):
                for cut in CUTS:examples[f'round/{size}/{int(last)}/{cut}']=round_case(size,last,cut)
        for size,kind in ir.PROFILES:
            s=fixture(size,kind);previous=None
            for cut in sorted(s.certs):previous=s.build(cut,previous)
            examples[f'catalog/{size}/{kind}']=s.evidence()
        path=args.output/'examples.json.gz';path.write_bytes(gzip.compress(t.encoded(examples).encode(),mtime=0))
        replayed=replay(json.loads(gzip.decompress(path.read_bytes())));need(binding==ir.binding(),'source changed')
        result=dict(status='PASS',schema='gse-v53-continuity-research-v1',execution='stable-round-and-catalog-reference',
                    productionQualified=False,phase0Accepted=False,replay=replayed,source=binding,
                    examplesSha256=hashlib.sha256(path.read_bytes()).hexdigest(),examplesFile=path.name,
                    excluded=['real filesystem/network','unbounded schedule exploration','production performance',
                              'automatic physical compaction','same-round operation reducer composition'])
    except Exception as error:
        result=dict(status='FAIL',source=binding,errorType=type(error).__name__,message=str(error))
    (args.output/'receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
