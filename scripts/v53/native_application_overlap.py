"""Observed simultaneous file-owner saturation in one application-crash original.

The nine-family physical/resource prerequisite runs first. A witness always
belongs to one original owner, callback and accounting sequence. Independent
maxima are never added; reservations, empty directories and equal-content files
are not substituted for nonempty physical owners. This is not byte-bound or
refusal qualification, and it cannot close the full resource obligation.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
from . import native_carried_application_capture_history as admission
from .remove_process_hosted import progress

h=admission.h;need=h.need;storage=admission.storage;t=storage.coverage.t
SCHEMA='gse-v53-native-application-overlap-v1'
COUNTS={k:t.COUNTS[k] for k in ('GENERATION','SOURCE','APPLICATION')}
METRICS=('physicalBytes','physicalMetadataBytes','physicalApplicationBytes','physicalStagingBytes',
         'reservedMetadataBytes','reservedStagingBytes','reservedQueuedBytes')
FALSES=('byteLimitQualified','atOrOverBoundRefusalQualified','crossOwnerSimultaneousPeak',
        'unobservedWritesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete')


def point(row,snapshot,state,limits,trace_sha):
    need(all(snapshot.get(k)==row.get(k) and type(row.get(k)) is int and type(snapshot.get(k)) is int for k in ('life','eventIndex')) and
         all(snapshot.get(k)==row.get(k) for k in ('node','point')),'overlap original callback identity')
    need(type(snapshot.get('sequence')) is int and snapshot['sequence']>=0,'overlap original accounting sequence')
    # Recompute grouping and file extents from the admitted original inventory.
    # Retirement image ordinals come from the full original transaction, not a
    # partial directory listing at this callback.
    physical=storage.coverage.compare(row['files'],state,row['ordinals'])
    need(h.snapshot.f.canonical({k:snapshot[k] for k in physical})==h.snapshot.f.canonical(physical),
         'overlap original physical binding')
    usage=t.usage(state,limits);t.same_usage(snapshot['usage'],usage)
    extents=Counter();counts=Counter()
    for charge in physical['required']:
        extents[charge['unit']]+=charge['bytes']
        if charge['bytes']>0:counts[charge['unit']]+=1
    protected=sum(v['bytes'] for v in state.values() if v['unit'] in t.PROTECTED)
    need(protected<=36*t.MIB,'overlap bounded protected headroom')
    fields=dict(physicalBytes=physical['physicalBytes'],physicalMetadataBytes=sum(extents[k] for k in t.META),
        physicalApplicationBytes=extents['APPLICATION'],physicalStagingBytes=sum(extents[k] for k in t.STAGING),
        reservedMetadataBytes=usage['metadata'],reservedStagingBytes=usage['staging'],reservedQueuedBytes=usage['queued'])
    return dict(life=row['life'],node=row['node'],eventIndex=row['eventIndex'],point=row['point'],sequence=snapshot['sequence'],
        inventorySha256=h.digest(h.snapshot.f.canonical(row['files'])),snapshotSha256=h.digest(h.snapshot.f.canonical(snapshot)),
        resourceTraceSha256=trace_sha,nonemptyPhysicalOwnerCounts=dict(sorted(counts.items())),
        chargedCounts=usage['counts'],physicalFiles=physical['physicalFiles'],physicalDirectories=physical['physicalDirectories'],
        unboundReservationCount=len(physical['unboundCharges']),limits=dict(zip(('metadata','staging','queued'),limits)),
        unspentProtectedHeadroomBytes=36*t.MIB-protected,**fields)


def summarize(points):
    need(type(points) is list and points,'overlap nonempty original callbacks')
    keys=[(p['life'],p['node'],p['eventIndex']) for p in points]
    need(keys==sorted(set(keys)),'overlap ordered unique original callbacks')
    # Every peak is the entire first original point attaining that metric.
    peaks={k:copy.deepcopy(max(points,key=lambda p:p[k])) for k in METRICS}
    saturated=[p for p in points if all(p['nonemptyPhysicalOwnerCounts'].get(k,0)==v for k,v in COUNTS.items())]
    owners=[]
    for life in (1,2):
        for n in range(1,5):
            node='node-'+str(n);own=[p for p in points if p['life']==life and p['node']==node]
            hits=[p for p in saturated if p['life']==life and p['node']==node]
            owners.append(dict(life=life,node=node,callbacks=len(own),callbacksSha256=h.digest(h.snapshot.f.canonical(own)),
                simultaneousSaturatedCallbacks=len(hits),firstSimultaneousSaturation=copy.deepcopy(hits[0]) if hits else None))
    return dict(schema=SCHEMA,status='PARTIAL',scope='one-owner-original-callback-nonempty-file-extents',
        callbacks=len(points),callbacksSha256=h.digest(h.snapshot.f.canonical(points)),ownerLifetimes=owners,
        requiredSimultaneousCounts=dict(COUNTS),simultaneousSaturatedCallbacks=len(saturated),
        simultaneousCountsObserved=bool(saturated),peaks=peaks,**dict.fromkeys(FALSES,False))


def derive(raw,original):
    observed=Path(raw)/admission.OBSERVED;model=admission.transients
    parts,_=model.model.plans(observed)
    rows,_=model.combine(dict(model.prerequisite.application_plans(observed),**parts))
    ordinals=storage.coverage.ordinal_plans(rows)
    snapshots={(o['life'],o['node']):o['snapshots'] for o in original['coverage']['owners']}
    need(set(snapshots)=={(life,'node-'+str(n)) for life in (1,2) for n in range(1,5)},'overlap exact original owners')
    points=[]
    for (life,node),observations in sorted(snapshots.items()):
        directory=observed/f'resources/life-{life}'
        data,trace=t.read(directory/(node+'.json'));t.replay(trace,require_closed=life==2)
        limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
        selected=[r for r in rows if r['life']==life and r['node']==node]
        need(len(selected)==len(observations),'overlap complete original callbacks')
        state={};cursor=0;trace_sha=h.digest(data)
        for row,snapshot in zip(selected,observations):
            seq=snapshot['sequence']
            need(type(seq) is int and cursor-1<=seq<len(trace['changes']),'overlap original trace cursor')
            while cursor<=seq:
                change=trace['changes'][cursor]
                for old in change['removed']:del state[t.key(old)]
                for new in change['added']:state[t.key(new)]=new
                cursor+=1
            points.append(point(dict(row,ordinals=ordinals[life,node,row['eventIndex']]),snapshot,state,limits,trace_sha))
    need(len(points)==original['coverage']['callbacks'],'overlap complete nine-family callbacks')
    return summarize(points)


def check_claim(claim,expected):
    need(type(claim) is dict and set(claim)==set(expected) and claim.get('schema')==SCHEMA and claim.get('status')=='PARTIAL' and
         claim.get('scope')==expected['scope'] and all(claim.get(k) is False for k in FALSES),'overlap claim scope')
    def same(a,b):return h.snapshot.f.canonical(a)==h.snapshot.f.canonical(b)
    need(same(claim['requiredSimultaneousCounts'],expected['requiredSimultaneousCounts']),'overlap frozen count vector')
    need(all(same(claim[k],expected[k]) for k in ('callbacks','callbacksSha256')),'overlap complete callback binding')
    need(all(same(claim[k],expected[k]) for k in ('simultaneousSaturatedCallbacks','simultaneousCountsObserved')),
         'overlap same-callback saturation')
    need(same(claim['ownerLifetimes'],expected['ownerLifetimes']),'overlap original owner witnesses')
    need(same(claim['peaks'],expected['peaks']),'overlap original complete peak witness')


NEGATIVES={
    'full-envelope-claim':'overlap claim scope',
    'byte-bound-claim':'overlap claim scope',
    'refusal-claim':'overlap claim scope',
    'cross-owner-claim':'overlap claim scope',
    'empty-scope':'overlap claim scope',
    'relaxed-count-vector':'overlap frozen count vector',
    'callback-omitted':'overlap complete callback binding',
    'callback-inventory':'overlap complete callback binding',
    'invented-saturation':'overlap same-callback saturation',
    'boolean-count':'overlap same-callback saturation',
    'owner-omitted':'overlap original owner witnesses',
    'foreign-owner':'overlap original owner witnesses',
    'wrong-lifetime':'overlap original owner witnesses',
    'later-checkpoint':'overlap original owner witnesses',
    'empty-file-counted':'overlap original owner witnesses',
    'deduplicated-identical-copies':'overlap original owner witnesses',
    'summed-independent-maxima':'overlap original complete peak witness',
    'reservation-as-file-bytes':'overlap original complete peak witness',
    'peak-inventory':'overlap original complete peak witness',
    'peak-trace':'overlap original complete peak witness',
}


def mutate(claim,name):
    need(name in NEGATIVES,'overlap known negative');peaks=claim['peaks'];owners=claim['ownerLifetimes']
    if name=='full-envelope-claim':claim['wholeRuntimeResourcesQualified']=True
    elif name=='byte-bound-claim':claim['byteLimitQualified']=True
    elif name=='refusal-claim':claim['atOrOverBoundRefusalQualified']=True
    elif name=='cross-owner-claim':claim['crossOwnerSimultaneousPeak']=True
    elif name=='empty-scope':claim['scope']=''
    elif name=='relaxed-count-vector':claim['requiredSimultaneousCounts']['APPLICATION']+=1
    elif name=='callback-omitted':claim['callbacks']-=1
    elif name=='callback-inventory':claim['callbacksSha256']='0'*64
    elif name=='invented-saturation':claim['simultaneousSaturatedCallbacks']+=1
    elif name=='boolean-count':claim['simultaneousSaturatedCallbacks']=True
    elif name=='owner-omitted':owners.pop()
    elif name in ('foreign-owner','wrong-lifetime','later-checkpoint','empty-file-counted','deduplicated-identical-copies'):
        row=next(v['firstSimultaneousSaturation'] for v in owners if v['firstSimultaneousSaturation'] is not None)
        if name=='foreign-owner':row['node']='node-9'
        elif name=='wrong-lifetime':row['life']=3
        elif name=='later-checkpoint':row['sequence']+=1
        elif name=='empty-file-counted':row['nonemptyPhysicalOwnerCounts']['SOURCE']+=1
        else:row['nonemptyPhysicalOwnerCounts']['APPLICATION']=1
    elif name=='summed-independent-maxima':peaks['physicalBytes']['physicalBytes']=sum(v['physicalBytes'] for v in peaks.values())
    elif name=='reservation-as-file-bytes':peaks['physicalMetadataBytes']['physicalMetadataBytes']=peaks['physicalMetadataBytes']['reservedMetadataBytes']
    elif name=='peak-inventory':peaks['physicalBytes']['inventorySha256']='0'*64
    elif name=='peak-trace':peaks['physicalBytes']['resourceTraceSha256']='0'*64


def validate(raw,case):
    before=admission.collect(Path(raw),case)
    original=admission.transients.validate(raw)
    admission.check_original(original,case)
    result=derive(raw,original)
    check_claim(result,result)
    need(admission.collect(Path(raw),case)==before,'overlap original changed')
    return dict(status='PARTIAL',case=case,original=admission.compact_original(original),overlap=result,
        originalInventorySha256=h.digest(h.snapshot.f.canonical(before['inventory'])),originalPreserved=True,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def qualify(raw,case):
    before=admission.collect(Path(raw),case);original=validate(raw,case)
    expected=original['overlap']
    need(expected['simultaneousCountsObserved'] is True,'overlap negatives require observed saturation')
    rows=[]
    for name,reason in NEGATIVES.items():
        # Claims are derived from, and compared with, the fully qualified raw
        # original. These are summary/selection attacks, not new file mutations.
        changed=copy.deepcopy(expected);mutate(changed,name)
        try:check_claim(changed,expected)
        except ValueError as error:need(str(error)==reason,'overlap unrelated negative '+name+': '+str(error))
        else:raise ValueError('overlap accepted negative '+name)
        rows.append(dict(case=name,status='REJECTED',reason=reason,mutationScope='in-memory-derived-witness'))
    need(admission.collect(Path(raw),case)==before,'overlap qualification changed original')
    return dict(original=original,negatives=rows,originalPreserved=True)


def run(raw,case,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',phase3Complete=False)
    try:
        with progress('native-application-overlap',case):value=qualify(Path(raw),case)
        h.save(output/'qualification.json',value)
        from .remove_process_matrix import read
        need(read(output/'qualification.json')==value,'overlap bounded receipt round trip')
        result=value['original']['overlap']
        receipt.update(status='PARTIAL',case=case,observedCallbacks=result['callbacks'],
            simultaneousSaturatedCallbacks=result['simultaneousSaturatedCallbacks'],negativeCases=len(value['negatives']),
            originalPreserved=True,wholeRuntimeResourcesQualified=False,cohortAdmitted=False)
    except BaseException as error:receipt.update(failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('raw');parser.add_argument('--case',choices=admission.CASES,required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args();print(json.dumps(run(args.raw,args.case,args.output),sort_keys=True))
