"""One complete required-four original before all three resource negative sets.

The history, live leases and custody transitions are indivisible. This entry
qualifies observed ownership; it does not claim the simultaneous byte maximum.
"""
from pathlib import Path
from . import joined_file_negatives as files
from . import joined_handoff_negatives as handoff
from . import native_resource_negatives as accounting

native=files.native
need=native.need
PROFILE='5-REPLACE-required-four'
SCHEMA='gse-v53-required-four-resources-v1'
NEGATIVES={'accounting':accounting.NEGATIVES,'handoff':handoff.NEGATIVES,'files':files.NEGATIVES}


def check_original(value):
    need(type(value) is dict and value.get('status')=='PASS' and value.get('profile')==PROFILE and
         value.get('nativeBudgetAccountingQualified') is True and
         all(value.get(k) is False for k in ('physicalPeakQualified','wholeRuntimeResourcesQualified',
                                            'finalSourceCohortQualified','phase3Complete')),
         'required-four resources complete original accounting')
    for key,flag in (('joinedHandoffResources','continuousHandoffQualified'),
                     ('joinedFileResources','originalFileCustodyQualified')):
        part=value.get(key)
        need(type(part) is dict and part.get('status')=='PASS' and part.get(flag) is True and
             part.get('phase3Complete') is False,'required-four resources complete original '+key)


def check_result(value):
    need(type(value) is dict and set(value)=={'schema','status','profile','original','negatives','originalFirst',
         'originalPreserved','combinedResourcesQualified','phase3Complete'} and value['schema']==SCHEMA and
         value['status']=='PASS' and value['profile']==PROFILE and value['originalFirst'] is True and
         value['originalPreserved'] is True and value['combinedResourcesQualified'] is False and value['phase3Complete'] is False,
         'required-four resources qualification scope')
    check_original(value['original'])
    expected={family:[dict(case=n,status='REJECTED',reason=r) for n,r in cases.items()] for family,cases in NEGATIVES.items()}
    need(value['negatives']==expected,'required-four resources exact negative families')


def qualify(root,progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,PROFILE,progress,joined_files=True)
    check_original(original)
    if progress:progress(dict(stage='complete-resource-original',status='PASS'))
    index,traces,boundaries,events=native.load(root)
    identities={v['identity']['node']:v['identity'] for v in index['owners']}
    physical=handoff.r.original(root);reader=files.maintenance.Replay(root);reader.run()
    # Derive both mappings from this original. Never use a previous run's plan.
    plan=files.r.derive(physical.owner,reader)
    cases={
        'accounting':accounting.replay((index,traces,boundaries,events),identities,index['root']),
        'handoff':handoff.replay((handoff.r.project(physical),events,traces,boundaries),progress),
        'files':files.replay((plan,events,traces,boundaries,files.r.transfers.load(root,index)),progress),
    }
    need(native.collection.inventory(root)==before,'required-four resources original changed')
    result=dict(schema=SCHEMA,status='PASS',profile=PROFILE,original=original,negatives=cases,
                originalFirst=True,originalPreserved=True,combinedResourcesQualified=False,phase3Complete=False)
    check_result(result);return result
