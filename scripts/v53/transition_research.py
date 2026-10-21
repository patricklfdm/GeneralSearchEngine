"""Finite transition schedules. PASS applies only to the declared research matrix."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import subprocess

from . import transition_model as t
from .membership_model import NODES, need

CUTS = ('prepare-staged', 'prepare-forced', 'accept-staged', 'accept-forced',
        'proof-staged', 'proof-partial', 'proof-forced')
PROFILES = ((3,3),(3,4),(4,3),(4,4),(4,5),(5,4),(5,5))
FILES = ('scripts/v53/__init__.py', 'scripts/v53/membership_model.py', 'scripts/v53/ballot_model.py',
         'scripts/v53/transition_model.py', 'scripts/v53/transition_research.py',
         'scripts/v53/test_transition_model.py')


def quorums(authority):
    family = authority.oracle_quorums()
    return sorted(tuple(sorted(q)) for q in family if not any(p < q for p in family))


def install_all(world, chain, nodes=NODES):
    for node in nodes:
        world.install(node, chain); world.force_install(node)


def exchange(world, handle, phase, nodes):
    authority, _ = handle
    model = world.slots[authority]
    for message_id in world.send(handle, phase, nodes):
        node = model.messages[message_id].voter
        need(world.deliver(authority,message_id), 'scheduled local rejection')
        need(model.voters[node].pending is not None, 'scheduled ballot rejection')
        world.force(authority,node)
        world.deliver(authority,model.next_message)


def commit(world, chain, entry, *, last=False):
    authority = t.fold(world.root,world.initial,chain,world.verify)
    votes = quorums(authority)[-1 if last else 0]
    handle = world.start(votes[0],entry)
    exchange(world,handle,'prepare',votes);world.select(handle)
    exchange(world,handle,'accept',votes);exchange(world,handle,'proof',votes)
    certificate = world.certificate(handle)
    result = chain+(certificate,)
    install_all(world,result)
    return result


def cut_campaign(world, handle, votes, cut):
    phase, boundary = cut.split('-',1)
    authority, _ = handle
    model = world.slots[authority]
    if phase != 'prepare':
        exchange(world,handle,'prepare',votes);world.select(handle)
    if phase == 'proof':
        exchange(world,handle,'accept',votes)
    requests = world.send(handle,phase,votes)
    late = [model.duplicate(message_id) for message_id in requests]
    world.flush(authority)
    for index,message_id in enumerate(requests):
        node = model.messages[message_id].voter
        world.deliver(authority,message_id)
        if boundary == 'forced' or (boundary == 'partial' and index < len(votes)-1):
            world.force(authority,node)
    for node in NODES:
        world.crash(node);world.restart(node)
    for message_id in list(model.messages):
        if message_id not in late:
            model.drop(message_id)
    world.flush(authority)
    return late


def scenario(old, target, boundary, cut, reverse=False):
    world = t.World(old)
    try:
        chain = commit(world,(),t.Entry('DATA',payload='before'))
        intent = t.Entry('INTENT','operation-A',target)
        if boundary == 'final':
            chain = commit(world,chain,intent)
        authority = t.fold(world.root,old,chain,world.verify)
        first,last = quorums(authority)[0],quorums(authority)[-1]
        if reverse:first,last=last,first
        requested = intent if boundary == 'intent' else t.Entry('FINAL','operation-A',target)
        handle = world.start(first[0],requested)
        late = cut_campaign(world,handle,first,cut)
        contender = t.Entry('INTENT','operation-B',target) if boundary == 'intent' else requested
        recovered = world.start(last[0],contender)
        exchange(world,recovered,'prepare',last)
        selected = world.select(recovered)
        if cut in ('accept-forced','proof-staged','proof-partial','proof-forced'):
            need(selected == requested, 'lost transition result discarded chosen entry')
        exchange(world,recovered,'accept',last);exchange(world,recovered,'proof',last)
        certificate = world.certificate(recovered)
        chain += (certificate,)
        install_all(world,chain)
        # Every old duplicate is delivered after the new local prefix is forced.
        for message_id in late:
            world.deliver(authority,message_id)
        if boundary == 'intent':
            chain = commit(world,chain,t.Entry('FINAL',selected.operation,target),last=True)
        chain = commit(world,chain,t.Entry('DATA',payload='after'),last=True)
        need(world.authority(target[0]).old == target, 'final membership not installed')
        result = t.check_history(world.root,old,world.events)
        need(result['longestPrefix'] == 4, 'incomplete multi-slot scenario')
        return world,result
    except Exception as error:
        error.research_case = dict(old=old,target=target,boundary=boundary,cut=cut,reverse=reverse,
                                   root=world.root,events=world.events)
        raise


def walk():
    world=t.World(NODES[:3]);chain=commit(world,(),t.Entry('DATA',payload='start'))
    for number,size in enumerate((4,5,4,3),1):
        target=NODES[:size];operation='walk-'+str(number)
        chain=commit(world,chain,t.Entry('INTENT',operation,target))
        chain=commit(world,chain,t.Entry('FINAL',operation,target),last=True)
        chain=commit(world,chain,t.Entry('BARRIER',payload='after-'+str(number)))
    return world,t.check_history(world.root,world.initial,world.events)


def run(limit=None):
    if limit is not None:need(type(limit) is int and limit >= 0,'matrix limit')
    counts=dict(expectedCases=len(PROFILES)*2*len(CUTS)*2,cases=0,events=0,publications=0)
    result=dict(schema='gse-v53-transition-research-v1',productionQualified=False,phase0Accepted=False,
                allInterleavings=False,execution='sequential-certificate-chain-model',counts=counts,
                profiles=PROFILES,cuts=CUTS)
    digest=hashlib.sha256();examples={}
    for before,after in PROFILES:
        old=NODES[:before];target=NODES[:after] if before!=after else NODES[1:after+1]
        for boundary in ('intent','final'):
            for cut in CUTS:
                for reverse in (False,True):
                    if limit is not None and counts['cases']>=limit:
                        return dict(result,status='INCOMPLETE',traceSha256=digest.hexdigest())
                    world,audit=scenario(old,target,boundary,cut,reverse)
                    record=dict(root=world.root,old=old,target=target,boundary=boundary,cut=cut,
                                reverse=reverse,events=world.events)
                    digest.update(t.encoded(record).encode()+b'\n')
                    counts['cases']+=1;counts['events']+=audit['events'];counts['publications']+=audit['publications']
                    examples.setdefault(boundary+'/'+cut,record)
    world,audit=walk()
    examples['size-walk']=dict(root=world.root,old=world.initial,events=world.events)
    return dict(result,status='PASS',traceSha256=digest.hexdigest(),examples=examples,walk=audit,
                assumptions=['atomic forced prefix installation; full authority chain retained',
                             'authentic ACKs and immutable genesis',
                             'one unresolved slot; no leader pipelining or lease reads',
                             'unique ballot allocation; finite named voters'],
                excluded=['application-state transfer','snapshot compaction','disk/wire bytes','liveness',
                          'production recovery integration','operation cancellation/idempotency','physical qualification'])


def replay(raw):
    """Reconstruct portable JSON histories; never consult a live World."""
    expected={boundary+'/'+cut for boundary in ('intent','final') for cut in CUTS}|{'size-walk'}
    need(set(raw)==expected, 'transition replay inventory')

    def authority(row):
        return t.Authority(**dict(row,old=tuple(row['old']),new=tuple(row['new'])))

    def ballot(row):
        return t.b.Ballot(**row)

    def accepted(row):
        return None if row is None else t.b.Accepted(ballot(row['ballot']),row['value'])

    def message(row):
        return t.b.Message(**dict(row,context=authority(row['context']),ballot=ballot(row['ballot']),
                                  accepted=accepted(row['accepted']),
                                  evidence=tuple(message(item) for item in row['evidence'])))

    def certificate(row):
        return t.Certificate(**dict(row,authority=authority(row['authority']),ballot=ballot(row['ballot']),
                                    accepts=tuple(message(item) for item in row['accepts']),
                                    proofs=tuple(message(item) for item in row['proofs'])))

    def slot_detail(row):
        row=dict(row)
        if 'message' in row:row['message']=message(row['message'])
        if 'ballot' in row:row['ballot']=ballot(row['ballot'])
        if 'accepted' in row:row['accepted']=accepted(row['accepted'])
        if 'bases' in row:row['bases']=tuple(message(item) for item in row['bases'])
        return row

    counts=dict(histories=0,events=0,publications=0)
    for name,record in raw.items():
        if name!='size-walk':
            need(name==record['boundary']+'/'+record['cut'], 'replay scenario identity')
        events=[]
        for row in record['events']:
            row=dict(row)
            if 'authority' in row:row['authority']=authority(row['authority'])
            if 'message' in row:row['message']=message(row['message'])
            if 'detail' in row:row['detail']=slot_detail(row['detail'])
            if 'certificate' in row:row['certificate']=certificate(row['certificate'])
            if 'chain' in row:row['chain']=tuple(certificate(item) for item in row['chain'])
            events.append(row)
        audit=t.check_history(record['root'],tuple(record['old']),events)
        need(audit['longestPrefix']==(13 if name=='size-walk' else 4), 'replay complete prefix')
        counts['histories']+=1;counts['events']+=audit['events'];counts['publications']+=audit['publications']
    return counts


def source():
    root=Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)),
                files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--max-cases',type=int)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False);binding=source()
    try:
        result=run(args.max_cases)
        need(source()==binding,'model source changed')
        examples=args.output/'examples.json.gz'
        examples.write_bytes(gzip.compress((t.encoded(result.pop('examples',{}))+'\n').encode(),mtime=0))
        result['examplesFile']=examples.name
        result['examplesSha256']=hashlib.sha256(examples.read_bytes()).hexdigest()
        if result['status']=='PASS':result['replay']=replay(json.loads(gzip.decompress(examples.read_bytes())))
    except Exception as error:
        result=dict(status='FAIL',errorType=type(error).__name__,message=str(error),productionQualified=False)
        if hasattr(error,'research_case'):
            failed=args.output/'failed-case.json';failed.write_text(t.encoded(error.research_case)+'\n')
            result['failedCaseSha256']=hashlib.sha256(failed.read_bytes()).hexdigest()
    result['source']=binding
    (args.output/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
