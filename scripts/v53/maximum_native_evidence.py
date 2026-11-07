"""Bind the maximum native backup to one complete default-staging history.

This entry does not infer simultaneous metadata/image/queue maxima, a recovery
SLA, whole-reader memory, or final-source cohort qualification.
"""
from pathlib import Path
import re
from uuid import UUID
from . import bootstrap_replay_contract as source_policy
from . import maximum_application_evidence as maximum
from . import native_resource_policy as resources
from . import required_four_resources as complete
from . import joining_grant_captures as captures
from . import bootstrap_plan_evidence as plans
from . import native_retirement_storage as storage

need=maximum.e.need
DIRECTORY='maximum-native-seed'
SCHEMA='gse-v53-maximum-native-resources-v2'
PROFILE='maximum-application-required-four-backup-segmented'
SOURCE_OPTIONS=dict(bootstrap_source=source_policy.BACKUP,wire_layout=source_policy.SEGMENTED)


def binding(digest,extra,bootstrap_history,bootstrap_digest):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest) and
         type(extra) is int and 0<extra<=65531,'maximum native seed identity')
    need(type(bootstrap_history) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',bootstrap_history) and
         UUID(bootstrap_history).int!=0 and bootstrap_history!=maximum.HISTORY and
         type(bootstrap_digest) is str and re.fullmatch('[0-9a-f]{64}',bootstrap_digest) and bootstrap_digest!=digest,
         'maximum native new bootstrap history')
    return dict(schema='gse-v53-maximum-native-seed-v2',status='PARTIAL',
                bootstrapSource=source_policy.BACKUP,wireLayout=source_policy.SEGMENTED,
                resourceProfile=resources.DEFAULT,stagingLimit=resources.LIMITS[resources.DEFAULT],
                applicationBytes=maximum.NATIVE_MAXIMUM,applicationSha256=digest,
                history=maximum.HISTORY,applicationSequence=41,extra=extra,phase3Complete=False,
                bootstrapHistory=bootstrap_history,bootstrapApplicationSha256=bootstrap_digest)


def check_binding(value):
    need(type(value) is dict,'maximum native exact seed binding')
    expected=binding(value.get('applicationSha256'),value.get('extra'),value.get('bootstrapHistory'),value.get('bootstrapApplicationSha256'))
    need(value==expected and value['phase3Complete'] is False and
         all(type(value[k]) is int for k in ('stagingLimit','applicationBytes','applicationSequence','extra')),
         'maximum native exact seed binding')


def seed(root,*,size=5):
    need(type(size) is int and size in (4,5),'maximum native explicit topology')
    root=Path(root);directory=root/DIRECTORY
    maximum.selection.layout(directory,{'calibration.image','source.image','source-backup','binding.json'},'maximum native seed layout')
    _,value=captures.json_file(directory/'binding.json')
    image,extra=maximum.source(directory)
    check_binding(value)
    need(len(image)==maximum.NATIVE_MAXIMUM and value['applicationSha256']==maximum.e.digest(image) and
         value['extra']==extra,'maximum native exact seed binding')
    bootstrapped=plans.read(root/'original-application.image',maximum.MAXIMUM)
    plan=plans.decode(plans.read(root/'original-plan.gsbp',2*maximum.e.MIB),bootstrapped,
                      size=size,source=source_policy.BACKUP,details=True)
    history=plan['root']['historyId']
    need(plan['root']['baseSequence']==41,'maximum native bootstrap application sequence')
    expected=binding(maximum.e.digest(image),extra,history,maximum.e.digest(bootstrapped))
    need(len(image)==len(bootstrapped)==maximum.NATIVE_MAXIMUM and value==expected,'maximum native exact seed binding')
    maximum.application(bootstrapped,history,41,maximum.documents(extra))
    original=maximum.c.inventory(directory/'source-backup')
    inventory=[dict(path=n,kind=1,size=len(v),sha256=maximum.e.digest(v)) for n,v in sorted(original.items())]
    need(plan['plan']['descriptor']['sourceInventory']==inventory,'maximum native original source inventory')
    return expected


def qualify(root,progress=None):
    root=Path(root)
    # The seed observation is inside the same original. Its bytes count against
    # the shared budget and are covered by both inventory checks.
    before=source_policy.inventory(root,**SOURCE_OPTIONS)
    original=seed(root)
    result=complete.qualify_default_staging_backup(root,progress)
    complete.check_default_staging_backup_result(result)
    simultaneous=storage.derive(root,application_bytes=original['applicationBytes'],
        application_sha256=original['bootstrapApplicationSha256'],resource_profile=resources.DEFAULT,**SOURCE_OPTIONS)
    storage.check_result(simultaneous,application_bytes=original['applicationBytes'],
                         application_sha256=original['bootstrapApplicationSha256'])
    if progress:progress(dict(stage='maximum-native-simultaneous-images',status='PASS',
                              callbacks=simultaneous['matchingCallbacks']))
    need(seed(root)==original and source_policy.inventory(root,**SOURCE_OPTIONS)==before,
         'maximum native original changed during replay')
    value=dict(schema=SCHEMA,status='PASS',profile=PROFILE,seed=original,resources=result,simultaneousImageStorage=simultaneous,
                originalFirst=True,originalPreserved=True,maximumNativeHistoryQualified=True,
                combinedResourcesQualified=False,wholeReaderMemoryQualified=False,
                finalSourceCohortQualified=False,phase3Complete=False)
    check_result(value);return value


def check_result(value):
    fields={'schema','status','profile','seed','resources','simultaneousImageStorage','originalFirst','originalPreserved',
            'maximumNativeHistoryQualified','combinedResourcesQualified','wholeReaderMemoryQualified',
            'finalSourceCohortQualified','phase3Complete'}
    need(type(value) is dict and set(value)==fields and value['schema']==SCHEMA and
         value['status']=='PASS' and value['profile']==PROFILE and
         all(value[k] is True for k in ('originalFirst','originalPreserved','maximumNativeHistoryQualified')) and
         all(value[k] is False for k in ('combinedResourcesQualified','wholeReaderMemoryQualified','finalSourceCohortQualified','phase3Complete')),
         'maximum native qualification scope')
    check_binding(value['seed']);complete.check_default_staging_backup_result(value['resources'])
    storage.check_result(value['simultaneousImageStorage'],application_bytes=value['seed']['applicationBytes'],
                         application_sha256=value['seed']['bootstrapApplicationSha256'])
