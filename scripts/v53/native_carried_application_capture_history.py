"""Four indivisible application-ACK death/recovery histories with nine captures.

A full original replay precedes every negative. Bounded summaries retain hashes
of both owner projections; the original files and callbacks remain in the raw
archive. This adapter does not grant whole-runtime or Phase 3 qualification.
"""
from pathlib import Path
import re
from . import joining_history_run as h
from . import native_carried_application_transient_prefixes as transients

need=h.need;storage=transients.shared
CASES={kind+'-application-'+mode:(kind.upper(),transients.model.protocol.application.CUT,mode)
       for kind in ('intent','final') for mode in ('halt','kill')}
OBSERVED='previous/previous/previous/observed'
MAINTENANCE=transients.prerequisite.prerequisite
RETIREMENT=MAINTENANCE.prerequisite
APPLICATION=RETIREMENT.prerequisite
STAGES=(('transients',transients,'.'),('maintenance',MAINTENANCE,'previous'),
        ('old-end',RETIREMENT,'previous/previous'),('application',APPLICATION,'previous/previous/previous'))
PATHS={**{name:'transients/'+name for name in transients.FAMILIES},
       **{name:'previous/maintenance/'+name for name in MAINTENANCE.FAMILIES},
       'old-end':'previous/previous/retirement','application':'previous/previous/previous/application'}
SUMMARY='gse-v53-application-owner-summary-v1'


def selected(case):
    need(type(case) is str and case in CASES,'application capture exact case');return CASES[case]


def collect(raw,case):
    kind,cut,mode=selected(case);raw=Path(raw);before=h.inventory(raw);history=raw/OBSERVED/'history'
    result=storage.r.forces.process.read(history/'process/result.json')
    expected=dict(status='PARTIAL',producerPassed=True,phase3Complete=False,cut=cut,mode=mode,
                  oldPhase='ACCEPTED',carriedKind=kind,clientCalls=0,powerLoss=False)
    need(type(result) is dict and set(result)==set(expected)|{'children'} and
         h.snapshot.f.canonical({k:result[k] for k in expected})==h.snapshot.f.canonical(expected),
         'application capture producer scope')
    need(type(result['children']) is list and len(result['children'])==2,'application capture two children')
    for name,path in PATHS.items():
        directory=raw/path
        need(directory.is_dir() and not directory.is_symlink(),'application capture family directory: '+name)
    plans={case:h.digest(h.snapshot.s.regular(history/'original-plan.gsbp',h.snapshot.MIB))}
    need(h.inventory(raw)==before,'application capture changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='whole-native-carried-application-capture-collection',plans=plans,inventory=before,captureInventory={})


def negative_cases(case):
    selected(case)
    return [dict(suite=name,case=label,status='REJECTED',reason=reason)
            for name,reader,_ in STAGES for label,reason in reader.NEGATIVES.items()]+[
        dict(suite='ownership',case=name,status='REJECTED',reason='storage coverage original charge owner')
        for name in sorted(storage.OWNER_CASES)]


def original_chain(original):
    need(type(original) is dict and set(original)=={'status','original','captures','ledger','coverage',
        'duplicateReplayCallbacks','applicationTransientCompositionQualified','fullTransientBytesQualified',
        'wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'},'application capture original envelope')
    parts={'transients':original};value=original['original']
    need(type(value) is dict and set(value)=={'status','original','coverage','capturedCallbackBytesQualified',
        'captureScope','allSevenFamiliesCaptured','applicationAndRetirementChargeBindingQualified',
        'wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'},'application capture nested ownership')
    parts['ownership-five']=value;value=value['original']
    for name,field in (('maintenance','maintenance'),('old-end','retirement'),('application','application'),
                       ('resources','resources'),('retention','retention'),('floors','maintenance'),
                       ('exports','exports'),('protocol','protocol')):
        need(type(value) is dict and set(value)=={'status','original',field,'phase3Complete'} and
             value['status']=='PARTIAL' and value['phase3Complete'] is False,'application capture original chain: '+name)
        parts[name]=value;value=value['original']
    need(type(value) is dict and set(value)=={'status','physical','process','phase3Complete'} and
         value['status']=='PARTIAL' and value['phase3Complete'] is False,'application capture physical/process chain')
    parts['base']=value;return parts


def compact_coverage(coverage):
    return dict(schema=SUMMARY,status='PARTIAL',callbacks=sum(len(v['snapshots']) for v in coverage['owners']),
        owners=[dict(life=v['life'],node=v['node'],callbacks=len(v['snapshots']),
            ownerSha256=h.digest(h.snapshot.f.canonical(v)),snapshotsSha256=h.digest(h.snapshot.f.canonical(v['snapshots'])))
            for v in coverage['owners']],targets=storage.ownership_targets(coverage),
        originalCoverageSha256=h.digest(h.snapshot.f.canonical(coverage)),wholeRuntimeResourcesQualified=False)


def compact_original(original):
    # Do not retain the nested five-family arrays in the bounded hosted receipt.
    nested=original['original']
    return dict(original,coverage=compact_coverage(original['coverage']),
                original=dict(nested,coverage=compact_coverage(nested['coverage'])))


def check_coverage(coverage,total,*,compact):
    need(coverage.get('status')=='PARTIAL' and type(coverage.get('owners')) is list and len(coverage['owners'])==8,
         'application capture owner coverage')
    owners=coverage['owners']
    need(all(type(v.get('life')) is int for v in owners) and {(v['life'],v.get('node')) for v in owners}==
         {(life,'node-'+str(node)) for life in (1,2) for node in range(1,5)},'application capture exact owner lifetimes')
    if compact:
        need(set(coverage)=={'schema','status','callbacks','owners','targets','originalCoverageSha256','wholeRuntimeResourcesQualified'} and
             coverage['schema']==SUMMARY and type(coverage['callbacks']) is int and coverage['callbacks']==total and
             digest(coverage['originalCoverageSha256']),'application capture bounded coverage')
        for row in owners:
            need(set(row)=={'life','node','callbacks','ownerSha256','snapshotsSha256'} and
                 type(row['callbacks']) is int and row['callbacks']>=0 and digest(row['ownerSha256']) and digest(row['snapshotsSha256']),
                 'application capture owner digest')
        need(sum(v['callbacks'] for v in owners)==total and type(coverage['targets']) is dict and
             set(coverage['targets'])==storage.OWNER_CASES,'application capture summarized totals/targets')
        for row in coverage['targets'].values():
            need(type(row) is dict and set(row)=={'life','node','unit','owner','eventIndex','point'} and
                 type(row['life']) is int and row['life'] in (1,2) and row['node'] in ('node-1','node-2','node-3','node-4') and
                 type(row['eventIndex']) is int and row['eventIndex']>=0 and
                 all(type(row[k]) is str and row[k] for k in ('unit','owner','point')),'application capture mutation target')
        projected=dict(owners=[dict(life=v['life'],node=v['node'],snapshots=[dict(eventIndex=v['eventIndex'],point=v['point'],
            required=[dict(unit=v['unit'],owner=v['owner'])])]) for v in coverage['targets'].values()])
        need(h.snapshot.f.canonical(storage.ownership_targets(projected))==h.snapshot.f.canonical(coverage['targets']),
             'application capture exact target categories')
    else:
        count=coverage.get('callbacks',coverage.get('expectedCallbacks'))
        need(type(count) is int and count==total and sum(len(v['snapshots']) for v in owners)==total,
             'application capture full coverage totals')
        storage.ownership_targets(coverage)


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def check_original(original,case,*,compact=False):
    kind,cut,mode=selected(case);parts=original_chain(original)
    def scopes(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('phase3Complete','cohortAdmitted','wholeRuntimeResourcesQualified','publicReady','powerLoss',
                           'fullTransientBytesQualified','coreScratchInventoryReplay','postCutTailObserved','fullForceReplay',
                           'fullWireReplay','processHistoryQualified','completePhysicalReplay'):
                    need(item is False,'application capture overclaimed scope: '+key)
                scopes(item)
        elif isinstance(value,list):
            for item in value:scopes(item)
    scopes(original)
    need(original['status']=='PARTIAL' and original['applicationTransientCompositionQualified'] is True,
         'application capture full original composition')
    own=parts['ownership-five']
    need(own['status']=='PARTIAL' and own['capturedCallbackBytesQualified'] is True and
         own['captureScope']=='application-five-captured-families' and own['allSevenFamiliesCaptured'] is False and
         own['applicationAndRetirementChargeBindingQualified'] is True,'application capture five-family binding')
    expected=dict(status='PARTIAL',kind=kind,cut=cut,mode=mode,clientCalls=0,freshGroupJvms=2,
                  survivingOriginalOwners=0,componentChecks='PASS',processObservations=True,originalPrefixReplayed=True)
    process=parts['base']['process'];physical=parts['base']['physical']
    need(h.snapshot.f.canonical({k:process.get(k) for k in expected})==h.snapshot.f.canonical(expected),
         'application capture exact original process')
    need(physical.get('status')=='PARTIAL' and physical.get('kind')==kind and physical.get('cut')==cut and
         all(physical.get(k) is True for k in ('originalPrefixReplayed','snapshotByteReplay','freshStableBarrier')),
         'application capture original physical replay')
    for name,field,flag in (('exports','exports','observedExportAuthorityQualified'),
                           ('floors','maintenance','completeCopyFloorLifetimesQualified'),
                           ('retention','retention','retentionRevisionCompositionQualified'),
                           ('resources','resources','observedAccountingQualified'),
                           ('maintenance','maintenance','maintenanceTransientBytesQualified'),
                           ('old-end','retirement','retiredApplicationBytesQualified'),
                           ('application','application','interruptedApplicationBytesQualified')):
        need(parts[name][field].get(flag) is True,'application capture prerequisite replay: '+name)
    protocol=parts['protocol']['protocol']
    need(protocol.get('callbacks',{}).get('observedStorageCallbacks') is True and
         protocol.get('network',{}).get('status')=='PARTIAL','application capture protocol replay')
    resources=parts['resources']['resources']
    need(type(resources.get('ownerLifetimes')) is int and resources['ownerLifetimes']==8,'application capture resource owners')
    captures=original['captures'];maintenance=parts['maintenance']['maintenance']
    need(set(captures)==set(transients.FAMILIES) and set(maintenance['families'])==set(MAINTENANCE.FAMILIES),
         'application capture exact family set')
    app=parts['application']['application'];end=parts['old-end']['retirement']['lifetime']
    pids={1:app.get('pid'),2:end.get('pid')}
    need(all(type(v) is int and v>0 for v in pids.values()) and pids[1]!=pids[2],'application capture two distinct children')
    def lifetime(row,life):
        need(type(row.get('life')) is int and row['life']==life and type(row.get('pid')) is int and row['pid']==pids[life] and
             type(row.get('capturedPrefixes')) is int and row['capturedPrefixes']>=0 and
             row.get('terminal')==('CUT_PREFIX' if life==1 else 'CLOSED'),'application capture exact family lifetime')
    lifetime(app,1);lifetime(end,2)
    need(app['capturedPrefixes']>0 and end['capturedPrefixes']>0,'application capture first ACK and old end')
    counts={'application':app['capturedPrefixes'],'old-end':end['capturedPrefixes']}
    flags=dict(retirement='transientRetirementBytesQualified',floors='transientFloorBytesQualified',campaigns='transientCampaignBytesQualified',
               votes='transientVoteBytesQualified',ledgers='transientLedgerBytesQualified',replay='controlScratchBytesQualified')
    for family,value in dict(maintenance['families'],**captures).items():
        lives=value.get('lifetimes');expected_lives=(2,) if family=='completion' else (1,2)
        need(value.get('status')=='PARTIAL' and type(lives) is list and len(lives)==len(expected_lives) and
             (family=='completion' or value.get(flags[family]) is True),'application capture family qualified: '+family)
        for row,life in zip(lives,expected_lives):lifetime(row,life)
        count=value.get('capturedPrefixes')
        need(type(count) is int and 0<count==sum(v['capturedPrefixes'] for v in lives),'application capture family count')
        counts[family]=count
    need(type(maintenance['capturedPrefixes']) is int and maintenance['capturedPrefixes']==sum(counts[k] for k in MAINTENANCE.FAMILIES),
         'application capture maintenance total')
    overlap=original['duplicateReplayCallbacks']
    need(type(overlap) is int and 0<overlap<=min(counts['old-end'],counts['replay']),'application capture exact replay overlap count')
    check_coverage(original['coverage'],sum(counts.values())-overlap,compact=compact)
    check_coverage(own['coverage'],sum(counts[k] for k in (*MAINTENANCE.FAMILIES,'application','old-end')),compact=compact)
    return parts


def check_result(value,case):
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'application capture preserved original replay')
    check_original(value['original'],case,compact=True)
    need(h.snapshot.f.canonical(value['negatives'])==h.snapshot.f.canonical(negative_cases(case)),
         'application capture exact negative vector')


def owner_negatives(raw,original):
    observed=Path(raw)/OBSERVED;parts,_=transients.model.plans(observed)
    rows,_=transients.combine(dict(transients.prerequisite.application_plans(observed),**parts))
    ordinals=storage.coverage.ordinal_plans(rows);results=[]
    for case,target in sorted(storage.ownership_targets(original['coverage']).items()):
        life,node=target['life'],target['node'];directory=observed/f'resources/life-{life}'
        events=storage.resource.read(directory,'events.json',32*1024*1024)
        boundaries=storage.resource.read(directory,'boundaries.json',32*1024*1024)
        _,trace=storage.coverage.t.read(directory/(node+'.json'));changed=storage.rename_owner(trace,target['unit'],target['owner'])
        need(storage.coverage.t.replay(changed,require_closed=life==2)==storage.coverage.t.replay(trace,require_closed=life==2),
             'application capture owner mutation changed totals')
        try:storage.coverage.bind(rows,changed,events,boundaries,node,life,closed=life==2,ordinals=ordinals)
        except ValueError as error:need(str(error)=='storage coverage original charge owner','application capture unrelated owner negative: '+str(error))
        else:raise ValueError('application capture accepted owner negative: '+case)
        results.append(dict(suite='ownership',case=case,status='REJECTED',reason='storage coverage original charge owner'))
    return results


def replay(raw,case):
    raw=Path(raw);before=collect(raw,case)
    original=transients.validate(raw)  # All nine families and both owner projections before any mutation.
    parts=check_original(original,case);rows=[]
    for name,reader,path in STAGES:
        value=reader.qualify(raw/path)
        need(h.snapshot.f.canonical(value['original'])==h.snapshot.f.canonical(parts[name]),
             'application capture original stage drift: '+name)
        need(value.get('originalStorageUnchanged') is True and value.get('mutatedPrerequisiteReplayed') is False,
             'application capture negative preservation: '+name)
        rows.extend(dict(suite=name,**{k:v[k] for k in ('case','status','reason')}) for v in value['negatives'])
    rows.extend(owner_negatives(raw,original))
    need(collect(raw,case)==before,'application capture original or captures changed in reader')
    result=dict(original=compact_original(original),negatives=rows,originalPreserved=True);check_result(result,case);return result
