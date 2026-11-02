"""Complete selected installation writes within their original causal interval.

Members come from independently derived installed bytes. These successful
transactions do not establish interrupted-install recovery or global callback
coverage. Publication and adoption have their own complete transaction readers.
"""
from .generation_install_evidence import transaction
from .joining_slot_storage import CURRENT, exact
from .membership_model import need


def sequence(members):
    return [*transaction(members)[0], *CURRENT, 'INSTALL_BEFORE_RETURN']


def interval(events, node, scope, lower, upper, members, selections, reason):
    # Prefix matching rejects unknown callbacks as well as omitted, reordered,
    # duplicated or foreign-owner writes. Selection persistence is bound by the
    # caller; include its required return/force markers without ignoring writes.
    return exact(events, node, scope, lower+1, upper-1,
                 [*selections, *sequence(members)], ('INSTALL_', 'CURRENT_', *selections), reason)


WRITES = ('INSTALL_DIRECTORY_CREATED', 'INSTALL_MANIFEST_WRITTEN', 'INSTALL_IMAGE_WRITTEN',
          'INSTALL_MEMBER_WRITTEN', 'INSTALL_SELECTOR_WRITTEN', 'CURRENT_VALIDATED')
SPECS = {**{'missing-'+point.lower().replace('_','-'):(point,'missing') for point in WRITES},
         'duplicate-write':('INSTALL_MANIFEST_WRITTEN','duplicate'),
         'write-after-force':('INSTALL_MANIFEST_WRITTEN','reorder'),
         'foreign-write-scope':('INSTALL_MANIFEST_WRITTEN','scope'),
         'extra-write-field':('INSTALL_MANIFEST_WRITTEN','shape'),
         'unknown-install':('INSTALL_MANIFEST_WRITTEN','unknown-install'),
         'unknown-current':('INSTALL_MANIFEST_WRITTEN','unknown-current')}
REASONS = {'proposer':'joining network proposer complete installation order',
           'remote':'joining network durable installation order',
           'recovery':'joining network recovery local installation order'}
NEGATIVES = {'install-'+role+'-'+name:REASONS[role] for role in ('proposer','remote') for name in SPECS}
RECOVERY_NEGATIVES = {'install-recovery-'+name:REASONS['recovery'] for name in SPECS}


def mutate(events, name):
    need(name in {**NEGATIVES, **RECOVERY_NEGATIVES}, 'joining install unknown mutation')
    _, role, suffix = name.split('-',2); point, mode = SPECS[suffix]
    if role=='recovery':
        start=max(i for i,v in enumerate(events) if v['event']=='INSTALL_RESERVED' and v.get('scope')=='continuation-owner')
    else:
        node='node-1' if role=='proposer' else 'node-2'
        start=next(i for i,v in enumerate(events) if v['event']=='INSTALL_RESERVED' and v.get('node')==node)
    node=events[start]['node']
    end=next(i for i,v in enumerate(events) if i>start and v.get('node')==node and v['event']=='INSTALL_BEFORE_RETURN')
    at=next(i for i,v in enumerate(events) if start<i<end and v.get('node')==node and v['event']==point)
    if mode=='missing':events.pop(at)
    elif mode=='duplicate':events.insert(at,dict(events[at]))
    elif mode=='scope':events[at]['scope']='foreign-owner'
    elif mode=='shape':events[at]['claimedWritten']=True
    elif mode=='reorder':
        after=next(i for i,v in enumerate(events) if i>at and v.get('node')==node and v['event']=='INSTALL_MANIFEST_FORCED')
        events[at],events[after]=events[after],events[at]
    else:events.insert(at,dict(events[at],event='INSTALL_UNKNOWN' if mode=='unknown-install' else 'CURRENT_UNKNOWN'))
