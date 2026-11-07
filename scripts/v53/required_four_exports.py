"""Original content/control export authority for required-four replacement.

No alternate network admission or inferred socket observations are permitted.
Whole physical/network qualification runs before temporal capability replay.
Continuous maintenance ledgers and whole-runtime resources remain separate.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import bootstrap_replay_contract as source_policy
from . import required_four_network as network
from . import joining_profile_export_evidence as exports
from . import joining_profile_control_evidence as control

need,collection=network.need,network.collection
PROFILE=network.physical.semantic.PROFILE
NEGATIVES={**{'content/'+name:reason for name,reason in exports.NEGATIVES.items()},
           **{'control/'+name:reason for name,reason in control.NEGATIVES.items()}}


def context(root, *, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    return exports.context(root,'5-REPLACE',required_four=True,**source_args)


def control_reader(root, *, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    return control.Replay(root,'5-REPLACE',required_four=True,**source_args)


def content(root, *, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    return exports.replay(root,'5-REPLACE',required_four=True,**source_args)


def controls(root,prior, *, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    return control_reader(root,**source_args).run(prior)


def coverage(result,counts):
    need(sum(result['boundTransfers'].values())+result['unqualifiedTransfers']==counts['committedTransfers'] and
         sum(result['boundSessions'].values())+result['unqualifiedSessionCount']==
         counts['transferSessions']-counts['rejectedTransferAttempts'],
         'required-four export complete session accounting')
    # Each of the three old INTENT voters reads the actual joining ACK once.
    # Unlike the ordinary profiles this required-four producer cannot omit it.
    need(result['boundSessions'].get('pending-joining-checkpoint',0)==3,
         'required-four original pending checkpoint readers')


def validate(directory, *, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    root=Path(directory);before=collection.inventory(root)
    original=network.validate(root,**source_args);contents=content(root,**source_args);counts=original['network']
    coverage(contents,counts)
    result=controls(root,contents,**source_args)
    need(result['observedCommittedContents']==counts['committedTransfers'] and
         result['observedContentSessions']==counts['transferSessions']-counts['rejectedTransferAttempts'],
         'required-four control complete transfer coverage')
    need(collection.inventory(root)==before,'required-four export original changed')
    return source_policy.receipt(dict(status='PASS',scope='required-four-observed-temporal-content-and-control-exports',profile=PROFILE,
                precondition=original,exports=contents,controls=result,temporalContentExportsQualified=True,
                observedControlExportsQualified=True,observedLearnerRetentionQualified=True,
                allExportFamiliesQualified=False,maintenanceAndPeerCompositionQualified=False,
                wholeRuntimeResourcesQualified=False,completePhysicalQualified=False,
                processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False),bootstrap_source)


def mutate(root,case):
    need(case in NEGATIVES,'required-four declared export mutation')
    family,name=case.split('/',1)
    if family=='content':exports.e.mutate(root,name,reader=context(root))
    else:control.c.mutate(root,name,reader=control_reader(root))


def rejection_stage(root,case):
    """Earlier gates are mandatory and cannot count as the intended rejection."""
    network.replay(root)
    if case.startswith('content/') or case=='control/completion-closed-owner':
        return lambda:content(root)
    prior=content(root)
    return lambda:controls(root,prior)


def qualify(directory,progress=None):
    root=Path(directory);before=collection.inventory(root);original=validate(root);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for case,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-required-four-export-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:mutate(changed,case)
            except StopIteration as error:raise ValueError('required-four missing export mutation target: '+case) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'required-four export negative changed physical inputs')
            check=rejection_stage(changed,case)
            try:check()
            except ValueError as error:need(str(error)==reason,'required-four unrelated export negative: '+case+': '+str(error))
            else:raise ValueError('required-four export mutation accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason,networkPrecondition='PASS',
            rejectionStage='content' if case.startswith('content/') else 'owner-lifetime' if case=='control/completion-closed-owner' else 'control'))
        if progress:progress(dict(case=case,status='REJECTED',completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'required-four export qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress) if a.qualify else validate(a.root),sort_keys=True))
