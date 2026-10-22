"""Finite global-promise/activation schedules; local research only."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from . import activation_model as a
from . import activation_oracle as o
from . import recovery_research as rr
from . import transition_research as tr
from . import transition_model as t
from .membership_model import NODES,need

CUTS=('allocation-staged','allocation-forced','grant-forced','basis-forced','selection-forced',
      'installation-forced','accept-forced','proof-forced','publication-staged','healthy')
FILES=rr.FILES+('scripts/v53/activation_model.py','scripts/v53/activation_oracle.py',
                'scripts/v53/activation_research.py','scripts/v53/test_activation_model.py')


def begin(engine,node):
    observed=max((r.fence for r in engine.roots.values() if r.fence),default=None)
    engine.allocate(node,observed);engine.force_allocation(node);return engine.start(node)


def votes_for(engine,node,last=False):
    choices=[q for q in tr.quorums(engine.world.authority(node)) if node in q]
    return choices[-1 if last else 0]


def prepare(engine,handle,node,fetch=True):
    result=engine.prepare(handle,node)
    if result=='STAGED':engine.force_grant(node);engine.force_basis(node)
    if fetch:engine.fetch(handle,node)


def selected(engine,handle,votes):
    for node in (handle[1].proposer,)+tuple(n for n in votes if n!=handle[1].proposer):prepare(engine,handle,node)
    engine.select(handle,votes);engine.force_selection(handle)


def installed(engine,handle,votes):
    for node in votes:
        engine.stage_install(handle,node);engine.force_install(node);engine.install_ack(handle,node)


def exchange(engine,handle,phase,votes):
    for mid in engine.send(handle,phase,votes):
        node=engine.world.slots[handle[0]].messages[mid].voter
        engine.deliver(handle,mid);engine.force_vote(handle,node)
        engine.deliver(handle,engine.world.slots[handle[0]].next_message)


def finish(engine,handle,votes):
    installed(engine,handle,votes);exchange(engine,handle,'accept',votes);exchange(engine,handle,'proof',votes)
    engine.certify(handle);engine.stage_publication(handle);return engine.published(handle)


def synchronize(engine):
    chain=max((replica.chain for replica in engine.world.nodes.values()),key=len)
    for node in NODES:
        if engine.world.nodes[node].chain!=chain:engine.sync(node,chain)


def recover_ready(engine):
    synchronize(engine)
    for _ in range(3):
        authority=engine.world.authority(NODES[0]);node=sorted(authority.voters)[0]
        handle=begin(engine,node);votes=votes_for(engine,node,last=True)
        selected(engine,handle,votes);ready=finish(engine,handle,votes);synchronize(engine)
        if ready:return handle
    raise ValueError('bounded activation did not finish')


def scenario(before,after,view,tail,cut):
    source,owner=rr.fixture(before,after,view,tail);engine=a.Engine(source.world)
    try:
        engine.allocate(owner)
        if cut!='allocation-staged':
            engine.force_allocation(owner)
        if cut not in ('allocation-staged','allocation-forced'):
            handle=engine.start(owner);votes=votes_for(engine,owner)
            engine.prepare(handle,owner);engine.force_grant(owner)
            if cut!='grant-forced':
                engine.force_basis(owner)
            if cut not in ('grant-forced','basis-forced'):
                engine.fetch(handle,owner)
                for node in votes:
                    if node!=owner:prepare(engine,handle,node)
                engine.select(handle,votes);engine.force_selection(handle)
                if cut!='selection-forced':
                    installed(engine,handle,votes)
                    if cut!='installation-forced':
                        exchange(engine,handle,'accept',votes)
                        if cut!='accept-forced':
                            exchange(engine,handle,'proof',votes)
                            if cut!='proof-forced':
                                engine.certify(handle);engine.stage_publication(handle)
                                if cut=='healthy':engine.published(handle)
        for node in NODES:engine.crash(node);engine.restart(node)
        recover_ready(engine)
        record=dict(engine.evidence(),profile=(before,after),view=view,tail=tail,cut=cut)
        result=o.check(record);need(result['activations']>=1,'no final activation')
        return record,result
    except Exception as error:
        error.research_case=dict(engine.evidence(),profile=(before,after),view=view,tail=tail,cut=cut)
        raise


def run(limit=None):
    if limit is not None:need(type(limit) is int and limit>=0,'matrix limit')
    counts=dict(cases=0,expectedCases=len(tr.PROFILES)*3*2*len(CUTS),events=0,campaigns=0,publications=0,activations=0)
    result=dict(schema='gse-v53-activation-research-v1',execution='global-promise-adapter',counts=counts,
                productionQualified=False,phase0Accepted=False,allInterleavings=False,cuts=CUTS)
    examples={};digest=hashlib.sha256()
    for before,after in tr.PROFILES:
        for view in rr.VIEWS:
            for tail in (False,True):
                for cut in CUTS:
                    if limit is not None and counts['cases']>=limit:return dict(result,status='INCOMPLETE',traceSha256=digest.hexdigest())
                    record,audit=scenario(before,after,view,tail,cut)
                    digest.update((t.encoded(record)+'\n').encode());counts['cases']+=1
                    for key in ('events','campaigns','publications','activations'):counts[key]+=audit[key]
                    examples.setdefault(f'{view}/tail-{int(tail)}/{cut}',record)
        print(json.dumps(dict(stage='activation-matrix',profile=(before,after),cases=counts['cases'])),flush=True)
    return dict(result,status='PASS',traceSha256=digest.hexdigest(),examples=examples,
                assumptions=['authentic identities and atomic force','verified complete predecessor chain',
                             'serialized prefix synchronization and one unresolved slot','fresh ballot per recovered slot'],
                excluded=['application bytes','real disk/wire faults','automatic source discovery/fairness',
                          'unlimited authority retention','service read/write leases','production performance'])


def decode(raw):
    # Reuse only the existing immutable record decoder, not any live recovery state.
    def row(event):
        return rr.decode(dict(old=raw['old'],sourceEvents=[],events=[event]))['events'][0]
    def ballot(value):return None if value is None else a.b.Ballot(**value)
    def decision(value):
        converted=row(dict(authority=value['authority'],ballot=value['ballot'],bases=value['bases']))
        return a.Decision(converted['authority'],converted['ballot'],converted['bases'],value['value'])
    events=[]
    for item in raw['events']:
        item=dict(item)
        for key in ('observed','ready'):
            if key in item and isinstance(item[key],dict):item[key]=ballot(item[key])
        if 'decision' in item:item['decision']=decision(item['decision'])
        if 'basis' in item:item['basis']=row(dict(bases=[item['basis']]))['bases'][0]
        # Avoid sending already decoded records back through the structural decoder.
        extra={key:item.pop(key) for key in ('observed','ready','decision','basis') if key in item}
        events.append(dict(row(item),**extra))
    decoded=rr.decode(dict(old=raw['old'],sourceEvents=raw['input'],events=[]))
    return dict(raw,old=tuple(raw['old']),input=decoded['sourceEvents'],events=events)


def replay(examples):
    expected={f'{v}/tail-{int(tail)}/{cut}' for v in rr.VIEWS for tail in (False,True) for cut in CUTS}
    need(set(examples)==expected,'activation replay inventory')
    counts=dict(histories=0,events=0,activations=0)
    for name,raw in examples.items():
        record=decode(raw)
        need(name==f"{record['view']}/tail-{int(record['tail'])}/{record['cut']}" and
             tuple(record['profile'])==tr.PROFILES[0],'activation replay label')
        # The original transition input determines view and unresolved-tail presence.
        from .recovery_oracle import Input
        observed=Input(record['root'],record['old'],record['input'])
        chain=observed.prefixes[NODES[0]]
        need(record['old']==NODES[:3] and len(chain)==rr.VIEWS.index(record['view'])+1 and
             (len(chain)==1 or t.Entry.read(chain[1].value).target==NODES[1:4]) and type(record['tail']) is bool and
             any(index==len(chain)+1 for _,index in observed.accepted)==record['tail'],'activation replay coverage')
        audit=o.check(record);need(audit['activations']>=1,'missing activation result')
        counts['histories']+=1;counts['events']+=audit['events'];counts['activations']+=audit['activations']
    return counts


def source():
    root=Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--max-cases',type=int)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False);binding=source()
    try:
        result=run(args.max_cases);need(source()==binding,'model source changed')
        path=args.output/'examples.json.gz';path.write_bytes(gzip.compress((t.encoded(result.pop('examples',{}))+'\n').encode(),mtime=0))
        result.update(examplesFile=path.name,examplesSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if result['status']=='PASS':result['replay']=replay(json.loads(gzip.decompress(path.read_bytes())))
    except Exception as error:
        result=dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            path=args.output/'failed-case.json.gz';path.write_bytes(gzip.compress(t.encoded(error.research_case).encode(),mtime=0))
            result['failedCaseSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['source']=binding;(args.output/'receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
