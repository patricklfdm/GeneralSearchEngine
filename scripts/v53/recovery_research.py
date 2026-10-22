"""Bounded checkpoint/retirement force-cut matrix; no production or cloud work."""
import argparse
import copy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from . import ballot_model as b
from . import transition_model as t
from . import transition_research as tr
from . import recovery_model as m
from . import recovery_oracle as o
from .membership_model import NODES, need

VIEWS=('old','joint','new')
FILES=tuple(dict.fromkeys(tr.FILES+('scripts/v53/recovery_model.py','scripts/v53/recovery_oracle.py',
                                  'scripts/v53/recovery_research.py','scripts/v53/test_recovery_model.py')))


def fixture(before=3,after=4,view='joint',tail=True):
    need(view in VIEWS,'unknown recovery view')
    old=NODES[:before];target=NODES[:after] if before!=after else NODES[1:after+1]
    world=t.World(old);chain=tr.commit(world,(),t.Entry('DATA',payload='before-checkpoint'))
    if view!='old':chain=tr.commit(world,chain,t.Entry('INTENT','operation-A',target))
    if view=='new':chain=tr.commit(world,chain,t.Entry('FINAL','operation-A',target))
    authority=world.authority(target[0]);votes=tr.quorums(authority)[0];owner=votes[0]
    if tail:
        entry=t.Entry('FINAL','operation-A',target) if view=='joint' else t.Entry('DATA',payload='unresolved')
        handle=world.start(owner,entry)
        tr.exchange(world,handle,'prepare',tuple(sorted(authority.voters)));world.select(handle)
        tr.exchange(world,handle,'accept',tuple(sorted(authority.voters)))
        # Chosen ACCEPT with no PROOF/publication. The next slot must retain it.
    return m.AuthoritySource(world),owner


def steps(store):
    yield 'initial'
    old=store.current()
    store.advance_promise(b.Ballot(store.promise.counter+1,store.owner,'root-promise'))
    yield 'root-promise'
    store.begin(replace(old,generation='b-1',snapshot=old.chain,suffix=()))
    yield 'generation-start'
    for name in m.FILES:
        store.force_file(name);yield 'generation-'+name
    store.stage_selector();yield 'selector-staged'
    store.force_selector();yield 'selector-forced'
    view=store.source.validate(store.current());votes=tr.quorums(view)[0]
    packets=[]
    for owner in votes:
        if owner==store.owner:packets.append(store.current())
        else:
            other=m.Store(store.source,owner).current()
            packets.append(replace(other,generation='b-1',snapshot=other.chain,suffix=()))
    store.prepare_floor(tuple(packets));yield 'floor-staged'
    for packet in packets:
        for name in m.FILES:
            store.force_source(packet.owner,name);yield 'floor-'+packet.owner+'-'+name
    store.force_floor();yield 'floor-forced'
    store.stage_retirement();yield 'retirement-staged'
    store.force_retirement();yield 'retirement-forced'
    for name in m.FILES:
        store.delete_file(name);yield 'delete-'+name
    store.delete_directory();yield 'delete-directory'
    store.clear_retirement();yield 'retirement-cleared'


def crash_copy(store):
    # Immutable packets and input execution are shared. crash/reopen only change
    # these scalar fields or replace floor_copies; file bytes are never modified.
    result=copy.copy(store);result.events=list(store.events)
    result.crash();result.reopen()
    return result


def observations(source, owner):
    world=source.world;store=m.Store(source,owner);cut='initial'
    try:
        observer=o.Input(world.root,world.initial,world.events)
        for cut in steps(store):
            observed=crash_copy(store)
            record=dict(root=world.root,old=world.initial,sourceEvents=world.events,
                        events=observed.events,cut=cut)
            try:audit=observer.check(observed.events)
            except Exception as error:
                error.research_case=record;raise
            yield record,audit
    except Exception as error:
        if not hasattr(error,'research_case'):
            error.research_case=dict(root=world.root,old=world.initial,sourceEvents=world.events,
                                     events=store.events,cut=cut)
        raise


def run(limit=None):
    if limit is not None:need(type(limit) is int and limit>=0,'matrix limit')
    expected=sum(2*(17+3*len(tr.quorums(
        t.Authority('count',1,'0'*64,0,NODES[:a] if v!='new' else (NODES[:z] if a!=z else NODES[1:z+1]),
                    NODES[:a] if v=='old' else (NODES[:z] if a!=z else NODES[1:z+1]),
                    'op' if v=='joint' else ''))[0])) for a,z in tr.PROFILES for v in VIEWS)
    # 17 fixed boundaries plus three forced files for each source in the first
    # minimal quorum. Each boundary gets a fresh crash/reopen observation.
    counts=dict(expectedCases=expected,cases=0,events=0,deletedFiles=0,fixtures=0)
    result=dict(schema='gse-v53-recovery-research-v1',execution='abstract-checkpoint-retirement',
                productionQualified=False,phase0Accepted=False,allInterleavings=False,counts=counts,
                bounds=dict(certificates=m.MAX_CERTIFICATES,changes=m.MAX_CHANGES,
                            packetBytes=m.MAX_PACKET_BYTES,retainedBytes=m.MAX_RETAINED_BYTES))
    digest=hashlib.sha256();examples={}
    for before,after in tr.PROFILES:
        for view in VIEWS:
            for tail in (False,True):
                source,owner=fixture(before,after,view,tail)
                name=f'{before}-{after}/{view}/tail-{int(tail)}';counts['fixtures']+=1
                cuts=[]
                for record,audit in observations(source,owner):
                    if limit is not None and counts['cases']>=limit:
                        return dict(result,status='INCOMPLETE',traceSha256=digest.hexdigest())
                    record.update(profile=(before,after),view=view,tail=tail);cut=record['cut']
                    digest.update(m.raw(record)+b'\n');cuts.append(cut)
                    counts['cases']+=1;counts['events']+=audit['events'];counts['deletedFiles']+=audit['deletedFiles']
                    if cut=='retirement-cleared':examples[name]=record
                need(len(cuts)==len(set(cuts)),'duplicate cut')
                if len(examples)%14==0:
                    print(json.dumps(dict(stage='recovery-matrix',fixtures=counts['fixtures'],cases=counts['cases'])),flush=True)
    need(counts['cases']==counts['expectedCases'],'recovery matrix inventory')
    return dict(result,status='PASS',traceSha256=digest.hexdigest(),examples=examples,
                assumptions=['authentic complete source packets and trusted genesis','atomic whole-file force and selector force',
                             'immutable input history during one checkpoint','one unresolved slot',
                             'separate monotonic root promise and immutable retained basis'],
                excluded=['application data bytes','real disk atomicity','unbounded or elided configuration history',
                          'concurrent campaigns during checkpoint','production global-promise/activation integration',
                          'liveness or timing qualification'])


def decode(record):
    def authority(row):return t.Authority(**dict(row,old=tuple(row['old']),new=tuple(row['new'])))
    def ballot(row):return None if row is None else b.Ballot(**row)
    def accepted(row):return None if row is None else b.Accepted(ballot(row['ballot']),row['value'])
    def message(row):
        return b.Message(**dict(row,context=authority(row['context']),ballot=ballot(row['ballot']),
                                accepted=accepted(row['accepted']),evidence=tuple(message(x) for x in row['evidence'])))
    def certificate(row):
        return t.Certificate(**dict(row,authority=authority(row['authority']),ballot=ballot(row['ballot']),
                                    accepts=tuple(message(x) for x in row['accepts']),proofs=tuple(message(x) for x in row['proofs'])))
    def tail(row):
        return None if row is None else m.Tail(**dict(row,authority=authority(row['authority']),ballot=ballot(row['ballot'])))
    def packet(row):
        return m.Packet(**dict(row,snapshot=tuple(certificate(x) for x in row['snapshot']),
                               suffix=tuple(certificate(x) for x in row['suffix']),tail=tail(row['tail'])))
    def event(row):
        row=dict(row)
        for key,convert in (('authority',authority),('ballot',ballot),('promise',ballot),('accepted',accepted),
                            ('message',message),('certificate',certificate),('packet',packet),('tail',tail),('detail',event)):
            if key in row:row[key]=convert(row[key])
        for key,convert in (('chain',certificate),('bases',message),('packets',packet)):
            if key in row:row[key]=tuple(convert(x) for x in row[key])
        return row
    return dict(record,old=tuple(record['old']),sourceEvents=[event(x) for x in record['sourceEvents']],
                events=[event(x) for x in record['events']])


def replay(examples):
    expected={f'{a}-{z}/{v}/tail-{tail}' for a,z in tr.PROFILES for v in VIEWS for tail in (0,1)}
    need(set(examples)==expected,'recovery replay inventory')
    count=dict(histories=0,events=0,deletedFiles=0)
    for name,raw in examples.items():
        record=decode(raw)
        need(name==f"{record['profile'][0]}-{record['profile'][1]}/{record['view']}/tail-{int(record['tail'])}" and
             record['cut']=='retirement-cleared','recovery replay identity')
        observer=o.Input(record['root'],record['old'],record['sourceEvents'])
        audit=observer.check(record['events'])
        packet=record['events'][0]['packet'];view=observer.packet(packet)
        before,after=record['profile'];old=NODES[:before]
        target=NODES[:after] if before!=after else NODES[1:after+1]
        phase=record['view']
        need(record['old']==old and len(packet.chain)==VIEWS.index(phase)+1 and
             view.old==(target if phase=='new' else old) and view.new==(old if phase=='old' else target) and
             bool(view.operation)==(phase=='joint') and type(record['tail']) is bool and
             bool(packet.tail)==record['tail'], 'recovery replay coverage mismatch')
        need(audit['deletedFiles']==3,'incomplete retirement replay')
        count['histories']+=1;count['events']+=audit['events'];count['deletedFiles']+=audit['deletedFiles']
    return count


def source():
    root=Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--max-cases',type=int);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);binding=source()
    try:
        result=run(a.max_cases);need(source()==binding,'model source changed')
        path=a.output/'examples.json.gz';path.write_bytes(gzip.compress(m.raw(result.pop('examples',{}))+b'\n',mtime=0))
        result.update(examplesFile=path.name,examplesSha256=m.sha(path.read_bytes()))
        if result['status']=='PASS':result['replay']=replay(json.loads(gzip.decompress(path.read_bytes())))
    except Exception as error:
        result=dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            path=a.output/'failed-case.json.gz';path.write_bytes(gzip.compress(m.raw(error.research_case),mtime=0))
            result['failedCaseSha256']=m.sha(path.read_bytes())
    result['source']=binding;(a.output/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
