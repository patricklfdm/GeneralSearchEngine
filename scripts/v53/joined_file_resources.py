"""Exact placed originals, received transfer identities and custody successors.

Complete native publication/network/physical/maintenance admission must precede
this conditional binding. Matching file hashes do not merge original inodes.
The placement snapshot is one checked boundary, not every intermediate write.
"""
from collections import Counter
from . import joined_handoff_resources as handoff
from . import storage_transfer_evidence as transfers

t,need=handoff.t,handoff.need
r=handoff.physical.init.retirement
p=r.placement


def charge(unit,owner,size):return dict(unit=unit,owner=owner,bytes=size,claimSource='')


def sessions(owner,reader):
    """Resolve original wire IDs from independently admitted source bytes."""
    before=handoff.positions(reader.events,owner.replay.joining)[0];result={}
    for cut in (4,8,9):
        original=owner.history.sources[cut];found=[]
        for group in reader.groups:
            capsules=[v for v in group if v['kind']=='CAPSULE']
            if len(capsules)!=1 or capsules[0]['raw']!=original['source.gscp']:continue
            q=capsules[0]['offer']['request']
            if q['sender']==owner.joining and q['recipient']==owner.peer and capsules[0]['offer']['sent']<before:found.append(group)
        need(len(found)==1,'joined files unique original source session');group=found[0]
        images={};capsule=None;ids=set()
        for content in group:
            q=content['offer']['request'];identifier=q['payload']['id']
            need(q['sender']==owner.joining and q['recipient']==owner.peer and
                 0<=content['offer']['sent']<content['commit']['delivered']<before and identifier not in ids,
                 'joined files original transfer boundary');ids.add(identifier)
            if content['kind']=='CAPSULE':capsule=identifier
            else:
                name=p.sha(content['raw'])+'.image'
                need(content['kind']=='APPLICATION' and name not in images and original.get(name)==content['raw'],
                     'joined files original image transfer');images[name]=identifier
        need(capsule is not None and set(images)=={k for k in original if k.endswith('.image')},
             'joined files complete original image sessions')
        result[cut]=dict(capsule=capsule,images=images)
    need(len({v for s in result.values() for v in [s['capsule'],*s['images'].values()]})==
         sum(1+len(s['images']) for s in result.values()),'joined files distinct original transfers')
    return result


def derive(owner,reader):
    source=sessions(owner,reader);sources=owner.history.sources
    misc=charge('MISC','learner-plan',2*t.MIB)
    typed=charge('APPLICATION','learner-typed-backup',64*t.MIB)
    seed=charge('GENERATION','learner-prepared:'+owner.plan,r.metadata(sources[4]))
    pending=charge('SOURCE','joining-retained:'+owner.plan,r.metadata(sources[8]))
    intent=charge('LEARNER',source[9]['capsule'],r.metadata(sources[9]))
    journal=charge('JOURNAL','learner-pending-intent',r.PENDING_JOURNAL)
    voter=charge('GENERATION','learner-voter-stage',r.metadata(owner.installed)+2*64*r.KIB+r.COMPANIONS)
    images={cut:{name:charge('APPLICATION',identifier,len(sources[cut][name]))
                 for name,identifier in s['images'].items()} for cut,s in source.items()}
    voter_images={name:charge('APPLICATION','voter:'+name,len(raw)) for name,raw in owner.installed.items()
                  if raw is not None and name.endswith('.image')}
    # Independent collector order: operation/typed/seed, published intent,
    # pending parent, dormant voter. Each retained source is a sorted file map.
    originals=[misc,typed,*[images[4][n] for n in sorted(images[4])],seed,
               *[images[9][n] for n in sorted(images[9])],intent,journal,
               *[images[8][n] for n in sorted(images[8])],pending,voter,
               *[voter_images[n] for n in sorted(voter_images)]]
    need(len(originals)<=32 and len({t.key(v) for v in originals})==len(originals),
         'joined files distinct predecessor leases')
    pairs=[dict(before=v,after=dict(v,owner='learner-custody-'+str(i))) for i,v in enumerate(originals)]
    by_key={t.key(v['before']):v for v in pairs};files=[];inodes=set();amounts=Counter()
    fixed={
        'operation':{'operation.lock','learner.gslp','learner-source.gslp'},
        'replica':{'root.gsr','node.gsr','replica.lock','learner-admission.gslp'},
        'initialTyped':{'preparation.lock','preparation.json','learner.gsr','prepared.json'},
        'intent':{'intent.json'},
    }
    for family,values in sorted(owner.expected.items()):
        for name,raw in sorted(values.items()):
            if raw is None:continue
            lease=None
            for scope,prefix,cut,metadata in (('replica','learner/',4,seed),('pendingIntent','source/',8,pending),('intent','source/',9,intent)):
                if family==scope and name.startswith(prefix):
                    member=name[len(prefix):]
                    need(sources[cut].get(member)==raw,'joined files exact source member')
                    lease=images[cut].get(member,metadata)
            if lease is None:
                if family=='initialTyped' and name.startswith('backup/'):lease=typed
                elif family=='pendingIntent' and name in {'pending-intent.json','joining-ack.gsr','retained-source.json'}:lease=journal
                elif family=='voterStage' or family=='replica' and p.moved(name):lease=voter_images.get(name,voter)
                elif family=='custody' and name=='custody.json' or family=='placement' and name in {'placement.json','placed.json','joined.json'}:lease=voter
                elif name in fixed.get(family,set()):lease=misc
            need(lease is not None,'joined files unassigned original member')
            inode=owner.key(family,name)
            need(inode not in inodes,'joined files duplicate original inode');inodes.add(inode)
            key=t.key(lease);amounts[key]+=len(raw)
            files.append(dict(family=family,path=name,key=inode,bytes=len(raw),sha256=p.sha(raw),
                              predecessor=lease,custody=by_key[key]['after'],createdAfterCustody=family=='placement'))
    need(set(amounts)==set(by_key) and all(amounts[k]<=v['before']['bytes'] for k,v in by_key.items()),
         'joined files physical bytes exceed original reservations')
    return dict(node=owner.replay.joining,pairs=sorted(pairs,key=lambda v:t.order_key(v['before'])),files=files)


def replay(plan,events,traces,boundaries,captured):
    checked=transfers.all_owners(traces,captured);node=plan['node']
    points=handoff.positions(events,node);sequence=boundaries[points[1]]['sequence']
    actual=checked[node]
    need(len(actual)==1 and actual[0]['resourceSequence']==sequence,
         'joined files exact custody transfer')
    need(actual[0]['moves']==plan['pairs'],'joined files exact predecessor successor pairs')
    # Native handoff continuity is separately checked by joined_handoff_resources.
    files=plan['files'];images=[v for v in files if v['path'].endswith('.image')]
    return dict(status='PASS',scope='original-placed-files-and-actual-custody-transfer',node=node,
                custodySequence=sequence,predecessorLeases=len(plan['pairs']),originalFiles=len(files),
                postCustodyCompletionFiles=sum(v['createdAfterCustody'] for v in files),
                originalFileBytes=sum(v['bytes'] for v in files),distinctImageFiles=len(images),
                distinctImageDigests=len({v['sha256'] for v in images}),
                mappingSha256=p.sha(p.f.canonical(plan)),
                originalFileCustodyQualified=True,intermediateFileLifetimesQualified=False,
                physicalPeakQualified=False,wholeRuntimeResourcesQualified=False,
                finalSourceCohortQualified=False,phase3Complete=False)
