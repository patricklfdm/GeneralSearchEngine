"""Compose existing automatic readers; no fallback to a weaker passing model.

Known competition shapes are selected only after the complete original export /
physical / network chain passes. Inapplicable negatives stay explicit, not PASS.
"""
import json
from pathlib import Path
import sys
from . import joining_history_run as h
from . import automatic_restart_lifecycle as restart
from . import automatic_restart_current as current
from . import automatic_lifecycle as lifecycle
from . import competing_export_evidence as exports
from . import competing_pregrant_evidence as pregrant
from . import competing_local_grant_evidence as local_grant
from . import competing_campaign_prefix as prefix
from . import competing_campaign_maintenance as maintenance
from . import competing_campaign_publication as publication
from . import competing_activation_network as activation
from . import transfer_reply_lifetime as replies

need=h.need;f=h.snapshot.f
COMPETING={'prefix':prefix,'maintenance':maintenance,'publication':publication,'activation':activation,'exports':exports,'lifecycle':lifecycle,'pregrant':pregrant}
COMPETING['local-grant']=local_grant


def same(actual,expected,reason):need(f.canonical(actual)==f.canonical(expected),reason)


def suites(case):
    need(case in ('competition','higher-ballot-restart','reply-revocation'),'automatic replay case')
    return (dict(pregrant=['pregrant','exports','lifecycle'],**{'local-grant':['local-grant','exports','lifecycle']},superseded=['prefix','maintenance','publication','activation','exports','lifecycle']) if case=='competition'
            else ['current','restart'] if case=='higher-ballot-restart' else ['replies'])


def competition_branch(original):
    need(type(original) is dict and type(original.get('precondition')) is dict,'automatic competition original chain')
    losses=original['precondition'].get('pregrantLosses');sources=original.get('sourceWindows');partial=original.get('incompleteTransfers')
    need(type(losses) is list and type(sources) is int and type(partial) is int,'automatic competition derived shape')
    local=original['precondition'].get('localGrantLosses',[])
    need(type(local) is list,'automatic competition derived shape')
    if len(losses)==1 and not local and sources==2 and partial==0:return 'pregrant'
    if not losses and len(local)==1 and sources==3 and partial==0:return 'local-grant'
    if not losses and not local and sources==4 and partial==1:return 'superseded'
    raise ValueError('automatic unsupported original competition shape; preserve evidence')


def export_vector(branch):
    need(branch in ('pregrant','local-grant','superseded'),'automatic competition declared branch')
    cases=dict(exports.NEGATIVES);not_applicable={}
    if branch in ('pregrant','local-grant'):
        for name in tuple(cases):
            if name.startswith('partial-'):
                not_applicable[name]='Original history has no incomplete SELECTED transfer.';del cases[name]
        del cases['journal-after-retirement']
        not_applicable['journal-after-retirement']='Original history has no source retirement.'
        cases['journal-after-history']='joining export inactive current generation'
    return cases,not_applicable


def vector(case,original):
    stages={};not_applicable={}
    if case=='competition':
        branch=competition_branch(original['exports'])
        need(original.get('branch')==branch and original.get('firstCapture') in ('node-1','node-2','node-3'),'automatic competition original selection')
        for stage in suites(case)[branch]:
            if stage=='exports':stages[stage],not_applicable=export_vector(branch)
            elif stage=='prefix':stages[stage]={k:v.format(node=original['firstCapture']) for k,v in prefix.NEGATIVES.items()}
            else:stages[stage]=COMPETING[stage].NEGATIVES
    elif case=='higher-ballot-restart':
        if original is None:cases,absent=current.NEGATIVES,{}
        else:cases,absent=current.negative_cases(original['precondition'])
        stages={'current':cases,'restart':restart.NEGATIVES}
        not_applicable={'current/'+k:v for k,v in absent.items()}
    elif case=='reply-revocation':stages={'replies':replies.NEGATIVES}
    else:raise ValueError('automatic replay case')
    rows=[]
    for stage,values in stages.items():
        for name,reason in values.items():
            row=dict(suite=stage,case=name,status='REJECTED',reason=reason)
            if stage=='restart':row['physicalOriginalUnchanged']=True
            rows.append(row)
    return rows,not_applicable


def check_result(value,case):
    suites(case)
    need(type(value) is dict and set(value)=={'original','negatives','notApplicable','originalPreserved'} and value['originalPreserved'] is True,
         'automatic original preservation result')
    original=value['original']
    need(type(original) is dict,'automatic original result')
    if case=='competition':
        need(set(original)=={'exports','lifecycle','branch','firstCapture'},'automatic complete competition layers')
        exported=original['exports'];life=original['lifecycle'];competition_branch(exported)
        need(exported.get('status')=='PARTIAL' and exported.get('observedTemporalExportAuthorityQualified') is True and
             all(exported.get(k) is False for k in ('completeExportLifetimesQualified','processDeathQualified','finalSourceCohortQualified','phase3Complete')),
             'automatic competition export scope')
        network=exported['precondition'];published=network.get('precondition',{})
        need(network.get('fullNetworkQualified') is True and network.get('originalActivationNetworkQualified') is True and
             published.get('physicalPublicationQualified') is True and published.get('clientCompletionQualified') is True and
             type(published.get('slots')) is int and published['slots']==2 and type(published.get('clientMutations')) is int and
             published['clientMutations']==1 and published.get('scratchTransfersDrained') is True,'automatic complete competition physical/network chain')
        need(life.get('status')=='PARTIAL' and life.get('actualStateTransitionsQualified') is True and life.get('originalDeadlinePreserved') is True and
             all(life.get(k) is False for k in ('physicalNetworkQualified','lossCauseQualified','fullLifecycleQualified','finalSourceCohortQualified','phase3Complete')),
             'automatic competition lifecycle scope')
        owners=life.get('owners');need(type(owners) is list and [v.get('node') for v in owners]==['node-1','node-2','node-3'] and
             all(v.get('started') is True and v.get('drained') is True for v in owners),'automatic complete competition owner lifetimes')
    elif case=='higher-ballot-restart':
        need(original.get('status')=='PARTIAL' and original.get('scope')=='one-native-higher-ballot-observed-restart' and
             all(original.get(k) is True for k in ('actualStateTransitionsQualified','originalDeadlinePreserved','lossCauseQualified','physicalNetworkQualified')) and
             all(original.get(k) is False for k in ('fullLifecycleQualified','processRestart','finalSourceCohortQualified','phase3Complete')),
             'automatic restart complete scoped replay')
        state=original.get('state',{});need(type(state.get('rounds')) is int and state['rounds']==2 and state.get('losses')==['HIGHER_BALLOT'] and
             state.get('drained') is True and state.get('started') is True and len(state.get('readyCallbacks',[]))==2,
             'automatic restart original two rounds')
        need(type(original.get('precondition')) is dict and original['precondition'].get('phase3Complete') is False,
             'automatic restart physical/network precondition')
    else:
        need(original.get('status')=='PASS' and original.get('scope')=='native-PROMISE-export-pre-return-revocation' and
             type(original.get('caseCount')) is int and original['caseCount']==48 and
             all(original.get(k) is False for k in ('remoteElectionQualified','allExportKindsQualified','phase3Complete')) and
             original.get('clockInjection')=='explicit-offset' and original.get('higherBallotInjection')=='local-native-owner-observation',
             'automatic reply complete scoped matrix')
        cases=original.get('cases');need(type(cases) is list and len(cases)==48,'automatic reply complete cases')
        for v,(size,boundary,fault) in zip(cases,replies.CASES):
            need(type(v) is dict and set(v)=={'size','boundary','fault','attempts','materialized','delivered','refused','resources'} and
                 type(v['size']) is int and (v['size'],v['boundary'],v['fault'])==(size,boundary,fault) and
                 all(type(v[k]) is int for k in ('attempts','materialized','delivered','refused')) and
                 v['refused']==3 and v['attempts']==v['delivered']+3 and v['materialized']==v['delivered']+1>=1,'automatic reply ordered exact outcomes')
            resources=v['resources'];need(type(resources) is dict and set(resources)=={'observations','maximumObservedQueued',
                'physicalStorageBaselineDerived','observedControlChargesQualified','wholeRuntimePeakQualified','publicationCapacityQualified'} and
                resources['physicalStorageBaselineDerived'] is True and resources['observedControlChargesQualified'] is True and
                resources['wholeRuntimePeakQualified'] is False and resources['publicationCapacityQualified'] is False and
                type(resources['observations']) is int and resources['observations']==2*v['attempts']+v['materialized']+2*v['delivered'],
                'automatic reply exact resource coverage')
            maximum=resources['maximumObservedQueued'];need(type(maximum) is dict and set(maximum)=={'server','client'} and
                all(type(n) is int and 0<n<=64*1024*1024 for n in maximum.values()),'automatic reply observed queue maximum')
    expected,skipped=vector(case,original)
    same(value['negatives'],expected,'automatic exact negative vectors')
    same(value['notApplicable'],skipped,'automatic explicit inapplicable negatives')


def replay(raw,case,sidecar=None):
    suites(case);raw=Path(raw);before=h.inventory(raw);captured=h.inventory(sidecar) if sidecar is not None else None
    rows=[]
    if case=='competition':
        # No exception fallback. Complete original authority and actual lifecycle
        # must pass before selecting a declared applicable negative catalogue.
        er=exports.Replay(raw);exported=er.run();life=lifecycle.validate(raw)
        branch=competition_branch(exported)
        expected_cases,skipped=export_vector(branch);actual_cases,actual_skipped=exports.negative_cases(er)
        same((actual_cases,actual_skipped),(expected_cases,skipped),'automatic competition derived applicability')
        links=prefix.g.json_file(raw/prefix.collection.FILE)[1]
        original=dict(exports=exported,lifecycle=life,branch=branch,firstCapture=links[0]['node'])
        chains={'exports':exported,'lifecycle':life,'pregrant':exported,'local-grant':exported};value=exported
        for stage in ('activation','publication','maintenance','prefix'):
            value=value['precondition'];chains[stage]=value
        selected=suites(case)[branch]
        functions=[(stage,COMPETING[stage].qualify,(raw,)) for stage in selected]
    elif case=='higher-ballot-restart':
        need(sidecar is not None,'automatic restart captures required')
        original=restart.validate(raw,sidecar);chains={'restart':original,'current':original['precondition']}
        skipped={'current/'+k:v for k,v in current.negative_cases(original['precondition'])[1].items()}
        functions=[('current',current.qualify,(raw,)),('restart',restart.qualify,(raw,sidecar))]
    else:
        need(sidecar is None,'automatic reply unexpected sidecar')
        original=replies.validate(raw);chains={'replies':original};skipped={};functions=[('replies',replies.qualify,(raw,))]
    for stage,qualify,args in functions:
        result=qualify(*args);same(result['original'],chains[stage],'automatic original reader drift: '+stage)
        rows.extend(dict(suite=stage,**v) for v in result['negatives'])
        print(json.dumps(dict(stage='automatic-qualified',case=case,suite=stage,negatives=len(result['negatives']))),file=sys.stderr,flush=True)
    need(h.inventory(raw)==before and (sidecar is None or h.inventory(sidecar)==captured),'automatic original changed during composed replay')
    result=dict(original=original,negatives=rows,notApplicable=skipped,originalPreserved=True);check_result(result,case);return result
