"""Finite capsule and learner schedules, with portable independent replay."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from . import admission_model as m
from . import admission_oracle as o
from . import transition_model as t
from . import transition_research as tr
from .membership_model import NODES, need

PROFILES = ((3,3),(3,4),(4,4),(4,5),(5,5))
LENGTHS = (1,8)
CUTS = tuple(f'{phase}-{boundary}' for phase in ('reservation','image','receipt','joint','final')
             for boundary in ('stage','force')) + ('healthy',)
FILES = tuple('scripts/v53/'+name+'.py' for name in (
    '__init__','membership_model','ballot_model','transition_model','transition_research',
    'recovery_model','recovery_oracle','recovery_research','admission_model','admission_oracle',
    'admission_research','test_admission_model'))


def fixture(before=3, after=4, length=1):
    world = t.World(NODES[:before]); chain = ()
    def commit(chain, entry):
        authority = t.fold(world.root,world.initial,chain,world.verify)
        # The source fixture must not assume this still-empty learner has voted
        # or installed anything. Existing voters can form both majorities for
        # every allowed one-member add/replace profile in this finite matrix.
        votes = next(q for q in tr.quorums(authority) if set(q) <= set(world.initial))
        handle = world.start(votes[0],entry)
        tr.exchange(world,handle,'prepare',votes);world.select(handle)
        tr.exchange(world,handle,'accept',votes);tr.exchange(world,handle,'proof',votes)
        result = chain+(world.certificate(handle),)
        tr.install_all(world,result,nodes=world.initial)
        return result
    for i in range(length): chain = commit(chain,t.Entry('DATA',payload='value-'+str(i)))
    target = NODES[:after] if before != after else NODES[1:after+1]
    joining = next(iter(set(target)-set(world.initial)))
    request = dict(root=world.root, operation='membership-1', expected=m.plain(world.authority(NODES[0])),
                   target=list(target), joining=m.descriptor(joining))
    chain = commit(chain,t.Entry('INTENT',t.digest(request),target))
    chain = commit(chain,t.Entry('FINAL',t.digest(request),target))
    return m.Source(world, chain), request, [m.descriptor(n) for n in world.initial]


def scenario(before, after, length, last, cut):
    source, request, identities = fixture(before, after, length)
    learner = m.Learner(source, request, identities)
    image, joint, final = (source.capsule(length+i, last=last) for i in range(3))
    phases = (('reservation',learner.reserve), ('image',lambda:learner.image(image)),
              ('receipt',learner.receipt), ('joint',lambda:learner.adopt(joint)),
              ('final',lambda:learner.adopt(final)))
    try:
        for name, action in phases:
            action()
            if cut == name+'-stage': break
            learner.force()
            if name in ('joint','final'): learner.vote(learner.durable['authority']['next'], request['joining'], learner.session)
            if cut == name+'-force': break
        learner.crash(); learner.restart()
        if 'reservation' not in learner.durable: learner.reserve(); learner.force()
        if 'image' not in learner.durable: learner.image(image); learner.force()
        if 'receipt' not in learner.durable: learner.receipt(); learner.force()
        if 'authority' not in learner.durable: learner.adopt(joint); learner.force()
        if learner.durable['authority']['next']['operation']: learner.adopt(final); learner.force()
        learner.vote(final['next'], request['joining'], learner.session)
        record = dict(learner.evidence(), profile=[before,after], length=length, last=last, cut=cut)
        coverage(record)
        audit = o.check(record); need(audit['final'] and audit['eligible'] > 0, 'missing final eligibility')
        return record, audit
    except Exception as error:
        error.research_case = learner.evidence()
        raise


def name(record):
    return f"{record['profile'][0]}-{record['profile'][1]}/{record['length']}/{int(record['last'])}/{record['cut']}"


def coverage(record):
    events = record['events']
    crashes = [i for i,e in enumerate(events) if e['event']=='crash']
    need(len(crashes)==1 and sum(e['event']=='restart' for e in events)==1, 'admission crash coverage')
    writes = [e for e in events[:crashes[0]] if e['event'] in ('stage','force')]
    need(bool(writes), 'missing pre-crash write')
    event = writes[-1]; phase = event['kind']
    if phase == 'authority': phase = 'joint' if event['value']['next']['operation'] else 'final'
    expected = 'final-force' if record['cut']=='healthy' else record['cut']
    need(phase+'-'+event['event']==expected, 'admission crash cut relabelled')
    for event in record['source']['events']:
        if event['event'] != 'capsule': continue
        for item in event['packet']['items']:
            if item['kind'] != 'gap': continue
            voters = item['statement']['start']['old']; majority = len(voters)//2+1
            owners = voters[-majority:] if record['last'] else voters[:majority]
            need(item['owners']==owners, 'admission quorum relabelled')


def replay(examples):
    expected = {f'{a}-{z}/1/0/{cut}' for a,z in PROFILES for cut in CUTS}
    need(set(examples) == expected, 'admission replay inventory')
    counts = dict(histories=0,events=0,eligible=0)
    for label, record in examples.items():
        need(name(record) == label and type(record['last']) is bool, 'admission replay label')
        coverage(record)
        a,z = record['profile']; old = list(NODES[:a]); target = list(NODES[:z] if a!=z else NODES[1:z+1])
        need(record['source']['old'] == old and record['request']['target'] == target and
             record['request']['expected']['index'] == record['length']+1, 'admission replay coverage')
        audit = o.check(record); need(audit['final'] and audit['eligible'] > 0, 'incomplete replay')
        counts['histories'] += 1
        for key in ('events','eligible'): counts[key] += audit[key]
    return counts


def source_binding():
    root = Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})


def run(limit=None):
    if limit is not None: need(type(limit) is int and limit >= 0, 'matrix limit')
    counts = dict(cases=0,expectedCases=len(PROFILES)*len(LENGTHS)*2*len(CUTS),events=0,capsules=0,eligible=0)
    result = dict(schema='gse-v53-admission-research-v1', execution='authority-capsule-learner-model',
                  productionQualified=False, phase0Accepted=False, allInterleavings=False, counts=counts,
                  cuts=CUTS, assumptions=['authentic records and identities','atomic force and exclusive disk ownership',
                    'already certified source history','abstract application hash'],
                  excluded=['real application bytes','cryptographic authentication','cloned disk detection',
                    'physical deletion','concurrent membership operations','global ballot adapter integration',
                    'unbounded membership lifetime','production performance'])
    digest = hashlib.sha256(); examples = {}
    for before,after in PROFILES:
        for length in LENGTHS:
            for last in (False,True):
                for cut in CUTS:
                    if limit is not None and counts['cases'] >= limit:
                        return dict(result,status='INCOMPLETE',traceSha256=digest.hexdigest(),examples=examples)
                    record,audit = scenario(before,after,length,last,cut)
                    digest.update((t.encoded(record)+'\n').encode()); counts['cases'] += 1
                    for key in ('events','capsules','eligible'): counts[key] += audit[key]
                    if length == 1 and not last: examples[name(record)] = record
        print(json.dumps(dict(stage='admission-matrix',profile=[before,after],cases=counts['cases'])),flush=True)
    return dict(result,status='PASS',traceSha256=digest.hexdigest(),examples=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--max-cases',type=int)
    args = parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False); binding = source_binding()
    try:
        result = run(args.max_cases); need(source_binding() == binding, 'model source changed')
        path = args.output/'examples.json.gz'
        path.write_bytes(gzip.compress((t.encoded(result.pop('examples'))+'\n').encode(),mtime=0))
        result.update(examplesFile=path.name,examplesSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if result['status'] == 'PASS': result['replay'] = replay(json.loads(gzip.decompress(path.read_bytes())))
    except Exception as error:
        result = dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            path = args.output/'failed-case.json.gz'
            path.write_bytes(gzip.compress(t.encoded(error.research_case).encode(),mtime=0))
            result['failedCaseSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['source'] = binding
    (args.output/'receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__': raise SystemExit(main())
