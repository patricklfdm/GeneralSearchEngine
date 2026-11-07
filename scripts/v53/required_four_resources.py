"""One complete required-four original before every resource negative family.

The history, live leases and custody transitions are indivisible. This entry
qualifies observed ownership; it does not claim the simultaneous byte maximum.
"""
from pathlib import Path
from . import wire_archive
from . import bootstrap_replay_contract as source_policy
from . import joining_catalog_evidence as bootstrap_catalog
from . import joined_file_negatives as files
from . import joined_handoff_negatives as handoff
from . import native_resource_negatives as accounting
from . import owner_close_negatives as network_close
from . import joining_owner_close_negatives as joining_close
from . import export_allocation_negatives as exports
from . import control_close_evidence
from . import voting_control_resource_negatives as voting
from . import slot_control_resource_negatives as slot
from . import activation_control_resource_negatives as activation

native=files.native
need=native.need
PROFILE='5-REPLACE-required-four'
SCHEMA='gse-v53-required-four-resources-v2'
BACKUP_SCHEMA='gse-v53-backup-required-four-resources-v1'
BACKUP_PROFILE=PROFILE+'-backup'
SOURCE_NEGATIVE=dict(case='declared-empty',status='REJECTED',reason='bootstrap plan source profile')
LAYOUT_NEGATIVE=dict(case='declared-json',status='REJECTED',reason='segmented wire unexpected layout')
NEGATIVES={'accounting':accounting.NEGATIVES,'handoff':handoff.NEGATIVES,'files':files.NEGATIVES,
           'network-close':network_close.NEGATIVES,'joining-close':joining_close.NEGATIVES,
           'export-allocations':exports.NEGATIVES,
           'voting-control':voting.NEGATIVES,'slot-control':slot.NEGATIVES,'activation-control':activation.NEGATIVES}


def check_original(value,*,bootstrap_source='EMPTY', wire_layout='JSON'):
    source_policy.check_receipt(value,bootstrap_source,wire_layout)
    need(type(value) is dict and value.get('status')=='PASS' and value.get('profile')==PROFILE and
         value.get('nativeBudgetAccountingQualified') is True and
         all(value.get(k) is False for k in ('physicalPeakQualified','wholeRuntimeResourcesQualified',
                                            'finalSourceCohortQualified','phase3Complete')),
         'required-four resources complete original accounting')
    for key,flag in (('joinedHandoffResources','continuousHandoffQualified'),
                     ('joinedFileResources','originalFileCustodyQualified'),
                     ('ownerCloseResources','ownerCloseIntervalsQualified'),
                     ('joinedOwnerCloses','joiningCloseIntervalsQualified'),
                     ('sourceCleanupIntervals','nativeServiceCleanupIntervalsQualified'),
                     ('exportAllocationCoverage','allObservedExportAllocationsQualified'),
                     ('votingControlResources','incomingVotingResourcesQualified'),
                     ('slotControlResources','slotResourcesQualified'),
                     ('activationControlResources','activationResourcesQualified')):
        part=value.get(key)
        need(type(part) is dict and part.get('status')=='PASS' and part.get(flag) is True and
             part.get('phase3Complete') is False,'required-four resources complete original '+key)
    coverage=value['exportAllocationCoverage'];scopes=coverage.get('byScope')
    need(type(scopes) is dict and set(scopes)==set(exports.r.SCOPES) and
         all(type(v) is int and v>0 for v in scopes.values()) and
         type(coverage.get('allocations')) is int and coverage['allocations']==sum(scopes.values()) and
         coverage.get('unclaimedAllocations')==[] and
         all(coverage.get(k) is False for k in ('failedConstructorExportsQualified','allExportFailurePathsQualified','wholeRuntimeResourcesQualified')),
         'required-four resources complete original export scope')


def _check_result(value,bootstrap_source,wire_layout='JSON'):
    source_args=source_policy.options(bootstrap_source,wire_layout);backup=bootstrap_source==source_policy.BACKUP
    fields={'schema','status','profile','original','negatives','originalFirst',
            'originalPreserved','combinedResourcesQualified','phase3Complete'}
    if backup:fields.add('bootstrapSource')
    if wire_layout==source_policy.SEGMENTED:fields.add('wireLayout')
    need(type(value) is dict and set(value)==fields and value['schema']==(BACKUP_SCHEMA if backup else SCHEMA) and
         value['status']=='PASS' and value['profile']==(BACKUP_PROFILE if backup else PROFILE) and value['originalFirst'] is True and
         value['originalPreserved'] is True and value['combinedResourcesQualified'] is False and value['phase3Complete'] is False,
         'required-four resources qualification scope')
    source_policy.check_receipt(value,bootstrap_source,wire_layout)
    check_original(value['original'],**source_args)
    expected={family:[dict(case=n,status='REJECTED',reason=r) for n,r in cases.items()] for family,cases in NEGATIVES.items()}
    if backup:expected['bootstrap-source']=[SOURCE_NEGATIVE]
    if wire_layout==source_policy.SEGMENTED:expected['wire-layout']=[LAYOUT_NEGATIVE]
    need(value['negatives']==expected,'required-four resources exact negative families')


def check_result(value):
    _check_result(value,source_policy.EMPTY)


def check_backup_result(value,*,wire_layout='JSON'):
    _check_result(value,source_policy.BACKUP,wire_layout)


def _qualify(root,progress,bootstrap_source,wire_layout='JSON'):
    source_args=source_policy.options(bootstrap_source,wire_layout);backup=bootstrap_source==source_policy.BACKUP
    root=Path(root);before=native.collection.inventory(root)
    bindings={}
    original=native.validate(root,PROFILE,progress,joined_files=True,joined_closes=True,complete_exports=True,
                             activation_control=True,export_bindings_out=bindings,**source_args)
    check_original(original,**source_args)
    if progress:progress(dict(stage='complete-resource-original',status='PASS'))
    index,traces,boundaries,events=native.load(root)
    closes=control_close_evidence.load(root,index)
    coverage=exports.r.replay(traces,closes,bindings)
    need(coverage==original['exportAllocationCoverage'],'required-four resources original export binding output')
    identities={v['identity']['node']:v['identity'] for v in index['owners']}
    physical=handoff.r.original(root,**source_args);reader=files.maintenance.Replay(root,**source_args);reader.run()
    # Derive both mappings from this original. Never use a previous run's plan.
    plan=files.r.derive(physical.owner,reader)
    cases={
        'accounting':accounting.replay((index,traces,boundaries,events),identities,index['root']),
        'handoff':handoff.replay((handoff.r.project(physical),events,traces,boundaries),progress),
        'files':files.replay((plan,events,traces,boundaries,files.r.transfers.load(root,index)),progress),
        'network-close':network_close.replay((index,traces,boundaries,events,set(identities)-{plan['node']}),progress),
        'joining-close':joining_close.replay((events,traces,boundaries,plan['node']),progress),
        'export-allocations':exports.replay(traces,closes,bindings,progress),
    }
    wires=wire_archive.read(root,'wire.json',bootstrap_source=bootstrap_source,layout=wire_layout)
    base=(events,wires,traces,boundaries,identities,index['root'])
    published=slot.r.required_four_publications(reader.model,identities)
    complete=(*base,published,native.publication.collect(root,events))
    for name,module,data,key in (('voting-control',voting,base,'votingControlResources'),
                                ('slot-control',slot,complete,'slotControlResources'),
                                ('activation-control',activation,complete,'activationControlResources')):
        result=module.replay(data,progress)
        need(result['original']==original[key],'required-four resources original control binding output')
        cases[name]=result['negatives']
        if progress:progress(dict(stage=name+'-negatives',status='PASS',cases=len(cases[name])))
    if backup:
        try:bootstrap_catalog.Replay(root,size=5,kind='REPLACE',required_four=True)
        except ValueError as error:need(str(error)==SOURCE_NEGATIVE['reason'],'required-four backup exact source rejection')
        else:raise ValueError('required-four backup accepted by EMPTY contract')
        cases['bootstrap-source']=[dict(SOURCE_NEGATIVE)]
        if progress:progress(dict(stage='bootstrap-source-negatives',status='PASS',cases=1))
    if wire_layout==source_policy.SEGMENTED:
        try:wire_archive.read(root,'wire.json',bootstrap_source=bootstrap_source)
        except ValueError as error:need(str(error)==LAYOUT_NEGATIVE['reason'],'required-four backup exact layout rejection')
        else:raise ValueError('required-four segmented wire accepted by JSON contract')
        cases['wire-layout']=[dict(LAYOUT_NEGATIVE)]
        if progress:progress(dict(stage='wire-layout-negatives',status='PASS',cases=1))
    need(native.collection.inventory(root)==before,'required-four resources original changed')
    result=source_policy.receipt(dict(schema=BACKUP_SCHEMA if backup else SCHEMA,status='PASS',profile=BACKUP_PROFILE if backup else PROFILE,
                original=original,negatives=cases,originalFirst=True,originalPreserved=True,
                combinedResourcesQualified=False,phase3Complete=False),bootstrap_source,wire_layout)
    _check_result(result,bootstrap_source,wire_layout);return result


def qualify(root,progress=None):
    """Existing cohort entry is permanently EMPTY; input receipts cannot opt in."""
    return _qualify(root,progress,source_policy.EMPTY)


def qualify_backup(root,progress=None,*,wire_layout='JSON'):
    """Separate backup entry; neither a replacement EMPTY slot nor a maximum gate."""
    return _qualify(root,progress,source_policy.BACKUP,wire_layout)
