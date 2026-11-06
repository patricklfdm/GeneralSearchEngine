"""Whole two-JVM carried histories with seven original capture families.

Collection is inventory only. Admission first replays the entire original chain,
then each capture family's exact negatives and balanced storage-owner negatives.
The two declared axes do not establish the complete crash/resource envelope.
"""
import json
import re
from pathlib import Path
import sys
from . import joining_history_run as h
from . import native_carried_storage_coverage as storage
from . import native_carried_retirement_prefixes as retirement
from . import native_carried_floor_prefixes as floor
from . import native_carried_campaign_prefixes as campaign
from . import native_carried_vote_prefixes as vote
from . import native_carried_completion_prefixes as completion
from . import native_carried_ledger_prefixes as ledger
from . import native_carried_replay_prefixes as replay_prefixes

need=h.need
CASES={'intent-accept-halt':('INTENT','ACCEPT_RENAMED','halt'),
       'final-proof-kill':('FINAL','PROOF_RENAMED','kill')}
FAMILIES=(('prefixes',retirement),('floors',floor),('campaigns',campaign),
          ('votes',vote),('completion',completion),('ledgers',ledger),('replay',replay_prefixes))
PATHS={'replay':'.','ledgers':'previous','completion':'previous/previous',
       'votes':'previous/previous/previous','campaigns':'previous/previous/previous/previous',
       'floors':'previous/previous/previous/previous/maintenance',
       'prefixes':'previous/previous/previous/previous/maintenance/prefixes'}
OBSERVED=PATHS['prefixes']+'/observed'
TRUTHS={'prefixes':'transientRetirementBytesQualified','floors':'transientFloorBytesQualified',
        'campaigns':'transientCampaignBytesQualified','votes':'transientVoteBytesQualified',
        'completion':'applicationPublicationBytesQualified','ledgers':'transientLedgerBytesQualified',
        'replay':'controlScratchBytesQualified'}


def selected(case):
    need(type(case) is str and case in CASES,'native capture exact case');return CASES[case]


def collect(raw,case):
    kind,cut,mode=selected(case);raw=Path(raw);before=h.inventory(raw)
    history=raw/OBSERVED/'history'
    result=retirement.forces.process.read(history/'process/result.json')
    expected=dict(status='PARTIAL',producerPassed=True,phase3Complete=False,cut=cut,mode=mode,
                  oldPhase='ACCEPTED',carriedKind=kind,clientCalls=0,powerLoss=False)
    need(type(result) is dict and set(result)==set(expected)|{'children'} and
         h.snapshot.f.canonical({k:result[k] for k in expected})==h.snapshot.f.canonical(expected),
         'native capture producer scope')
    need(type(result['children']) is list and len(result['children'])==2,'native capture two children')
    for name in PATHS:
        directory=raw/PATHS[name]
        captures=directory/('retirement' if name=='prefixes' else name)
        need(captures.is_dir() and not captures.is_symlink(),'native capture family directory: '+name)
    plans={case:h.digest(h.snapshot.s.regular(history/'original-plan.gsbp',h.snapshot.MIB))}
    need(h.inventory(raw)==before,'native capture changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='whole-native-carried-process-capture-collection',plans=plans,inventory=before,captureInventory={})


def negative_cases(case):
    selected(case)
    return [dict(suite=stage,case=name,status='REJECTED',reason=reason)
            for stage,reader in FAMILIES for name,reason in reader.NEGATIVES.items()]+[
        dict(suite='ownership',case=name,status='REJECTED',reason='storage coverage original charge owner')
        for name in sorted(storage.OWNER_CASES)]


def original_chain(original):
    need(type(original) is dict and set(original)=={'status','original','coverage','capturedCallbackBytesQualified',
        'wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'},'native capture ownership result')
    parts={'ownership':original};value=original['original']
    for name in ('replay','ledgers','completion','votes','campaigns','floors','prefixes','resources',
                 'retention','maintenance','exports','network','forces'):
        need(type(value) is dict and set(value)=={'status','original',name,'phase3Complete'} and
             value['status']=='PARTIAL' and value['phase3Complete'] is False,'native capture original chain: '+name)
        parts[name]=value;value=value['original']
    need(type(value) is dict and set(value)=={'status','physical','process','phase3Complete'} and
         value['status']=='PARTIAL' and value['phase3Complete'] is False,'native capture physical/process chain')
    parts['base']=value;return parts


def compact_original(original):
    """Bound the receipt, not the original replay or its retained input bytes."""
    coverage=original['coverage']
    owners=[dict(life=v['life'],node=v['node'],callbacks=len(v['snapshots']),
                 ownerSha256=h.digest(h.snapshot.f.canonical(v)),
                 snapshotsSha256=h.digest(h.snapshot.f.canonical(v['snapshots']))) for v in coverage['owners']]
    summary=dict(schema='gse-v53-carried-owner-summary-v1',status='PARTIAL',families='all-seven',
                 expectedCallbacks=coverage['expectedCallbacks'],owners=owners,targets=storage.ownership_targets(coverage),
                 originalCoverageSha256=h.digest(h.snapshot.f.canonical(coverage)),wholeRuntimeResourcesQualified=False)
    return dict(original,coverage=summary)


def check_original(original,case,*,compact=False):
    kind,cut,mode=selected(case);parts=original_chain(original)
    # Scope flags remain those of their owning readers; a cohort cannot turn
    # component replay into public readiness or full resource/crash coverage.
    def scopes(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('phase3Complete','cohortAdmitted','wholeRuntimeResourcesQualified','publicReady',
                           'powerLoss','fullTransientBytesQualified','coreScratchInventoryReplay','postCutTailObserved'):
                    need(item is False,'native capture overclaimed scope: '+key)
                scopes(item)
        elif isinstance(value,list):
            for item in value:scopes(item)
    scopes(original)
    need(original['status']=='PARTIAL' and original['capturedCallbackBytesQualified'] is True,
         'native capture original ownership binding')
    process=parts['base']['process'];physical=parts['base']['physical']
    expected=dict(status='PARTIAL',kind=kind,cut=cut,mode=mode,clientCalls=0,freshGroupJvms=2,
                  survivingOriginalOwners=0,componentChecks='PASS',processObservations=True,originalPrefixReplayed=True)
    need(h.snapshot.f.canonical({k:process.get(k) for k in expected})==h.snapshot.f.canonical(expected),
         'native capture exact original process')
    need(physical.get('kind')==kind and physical.get('cut')==cut and physical.get('originalPrefixReplayed') is True
         and physical.get('snapshotByteReplay') is True and h.snapshot.f.canonical(physical.get('publishedSlots'))==
         h.snapshot.f.canonical(list(range(5 if kind=='INTENT' else 6,8))),'native capture original physical replay')
    for name,flag in (('forces','observedStorageCallbacks'),('exports','observedExportAuthorityQualified'),
                      ('maintenance','completeCopyFloorLifetimesQualified'),('retention','retentionRevisionCompositionQualified')):
        need(parts[name][name].get(flag) is True,'native capture prerequisite replay: '+name)
    total=0;identities=None
    for name,_ in FAMILIES:
        value=parts[name][name];lives=value.get('lifetimes')
        need(value.get('status')=='PARTIAL' and value.get(TRUTHS[name]) is True and type(lives) is list and len(lives)==2,
             'native capture family replay: '+name)
        for life,row in enumerate(lives,1):
            need(type(row.get('life')) is int and row['life']==life and type(row.get('pid')) is int and row['pid']>0 and
                 type(row.get('capturedPrefixes')) is int and row['capturedPrefixes']>=0 and
                 row.get('terminal')==('CUT_PREFIX' if life==1 else 'CLOSED'),'native capture family lifetimes')
        need(lives[0]['pid']!=lives[1]['pid'] and type(value.get('capturedPrefixes')) is int and
             0<value['capturedPrefixes']==sum(v['capturedPrefixes'] for v in lives),'native capture family count')
        actual=[v['pid'] for v in lives]
        need(identities is None or actual==identities,'native capture same original children');identities=actual
        total+=value['capturedPrefixes']
    coverage=original['coverage'];resources=parts['resources']['resources']
    need(coverage.get('status')=='PARTIAL' and coverage.get('families')=='all-seven' and
         type(coverage.get('expectedCallbacks')) is int and coverage['expectedCallbacks']==total and
         type(coverage.get('owners')) is list and len(coverage['owners'])==8 and
         resources.get('observedAccountingQualified') is True and type(resources.get('ownerLifetimes')) is int and
         resources['ownerLifetimes']==8,'native capture complete original owner coverage')
    need(all(type(v.get('life')) is int for v in coverage['owners']) and {(v['life'],v['node']) for v in coverage['owners']}==
         {(life,'node-'+str(node)) for life in (1,2) for node in range(1,5)},'native capture exact owner lifetimes')
    if compact:
        need(set(coverage)=={'schema','status','families','expectedCallbacks','owners','targets',
                            'originalCoverageSha256','wholeRuntimeResourcesQualified'} and
             coverage['schema']=='gse-v53-carried-owner-summary-v1' and
             type(coverage['originalCoverageSha256']) is str and
             re.fullmatch('[0-9a-f]{64}',coverage['originalCoverageSha256']) is not None,
             'native capture bounded ownership summary')
        for owner in coverage['owners']:
            need(set(owner)=={'life','node','callbacks','ownerSha256','snapshotsSha256'} and
                 type(owner['callbacks']) is int and owner['callbacks']>=0 and
                 all(type(owner[k]) is str and re.fullmatch('[0-9a-f]{64}',owner[k])
                     for k in ('ownerSha256','snapshotsSha256')),'native capture original owner digest')
        need(sum(v['callbacks'] for v in coverage['owners'])==total and type(coverage['targets']) is dict and
             set(coverage['targets'])==storage.OWNER_CASES,'native capture exact summarized coverage')
        for target in coverage['targets'].values():
            need(type(target) is dict and set(target)=={'life','node','unit','owner','eventIndex','point'} and
                 type(target['life']) is int and target['life'] in (1,2) and target['node'] in ('node-1','node-2','node-3','node-4') and
                 type(target['eventIndex']) is int and target['eventIndex']>=0 and
                 all(type(target[k]) is str and target[k] for k in ('unit','owner','point')),'native capture original mutation target')
        projected=dict(owners=[dict(life=v['life'],node=v['node'],snapshots=[dict(eventIndex=v['eventIndex'],point=v['point'],
            required=[dict(unit=v['unit'],owner=v['owner'])])]) for v in coverage['targets'].values()])
        need(h.snapshot.f.canonical(storage.ownership_targets(projected))==h.snapshot.f.canonical(coverage['targets']),
             'native capture exact mutation owner categories')
    else:storage.ownership_targets(coverage)
    return parts


def check_result(value,case):
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and
         value['originalPreserved'] is True,'native capture preserved original replay')
    check_original(value['original'],case,compact=True)
    need(h.snapshot.f.canonical(value['negatives'])==h.snapshot.f.canonical(negative_cases(case)),
         'native capture exact negative qualification')


def replay(raw,case):
    raw=Path(raw);before=collect(raw,case)
    original=storage.validate(raw)  # Complete unmodified original before ANY mutation.
    parts=check_original(original,case);rows=[]
    for name,reader in (*FAMILIES,('ownership',storage)):
        value=reader.qualify(raw/PATHS[name] if name!='ownership' else raw)
        need(h.snapshot.f.canonical(value['original'])==h.snapshot.f.canonical(parts[name]),
             'native capture original stage drift: '+name)
        need(value.get('originalStorageUnchanged') is True and value.get('mutatedPrerequisiteReplayed') is False,
             'native capture negative preservation: '+name)
        rows.extend(dict(suite=name,**{k:v[k] for k in ('case','status','reason')}) for v in value['negatives'])
        print(json.dumps(dict(stage='native-carried-capture-qualified',case=case,suite=name,
                              negatives=len(value['negatives']))),file=sys.stderr,flush=True)
    need(collect(raw,case)==before,'native capture original or captures changed in reader')
    result=dict(original=compact_original(original),negatives=rows,originalPreserved=True);check_result(result,case);return result
