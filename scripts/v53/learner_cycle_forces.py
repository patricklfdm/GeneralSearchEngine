"""Exact successful force/delete traces, delimited by original snapshots.

Counts come from independently matched original inventories. These are observed
force calls, not process-death or power-loss qualification.
"""
from . import learner_typed_evidence as t
need=t.need


def write(prefix,*,created=True,resume=False):
    suffix=('_FORCED','_PARENT_FORCED') if resume else (
        ('_CREATED',) if created else ())+('_PREFIX_WRITTEN','_WRITTEN','_FORCED','_PARENT_FORCED')
    return [prefix+s for s in suffix]


def source(original):
    members=sum(n!='source.gscp' and not n.endswith('.image') for n in original)
    return ['LEARNER_SOURCE_METADATA_RESERVED']+[
        'LEARNER_SOURCE_MEMBER'+s for s in ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED')]*members+['LEARNER_SOURCE_DIRECTORY_FORCED']


def admission():
    return ['LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN',
            'LEARNER_RETENTION_ACTIVE_FORCED','LEARNER_RETENTION_ACTIVE_PARENT_FORCED','LEARNER_RETENTION_BEFORE_RETURN']


def deletion(prefix,count,present):
    return [prefix+s for s in ('_BEFORE_DELETE',)+(('_MEMBER_DELETED',) if present else ())+('_MEMBER_PARENT_FORCED',)]*count


def seed_retire(count,*,resume=False):
    result=[] if resume else write('LEARNER_RETIRE_DECISION')
    return result+write('LEARNER_HEAD_ACTIVE',resume=True)+write('LEARNER_RETIRE_DECISION',resume=True)+deletion('LEARNER_RETIRE',count,not resume)+[
        'LEARNER_RETIRE_PARENTS_FORCED','LEARNER_RETIRE_RELEASED']


def clear(*,resume=False):
    result=[] if resume else ['LEARNER_SLOT_CLEAR_CANDIDATE_CREATED']
    result+=['LEARNER_SLOT_CLEAR_PARENTS_FORCED']
    if not resume:result+=write('LEARNER_SLOT_CLEAR_CANDIDATE',created=False)+['LEARNER_SLOT_CLEAR_RENAMED']
    return result+write('LEARNER_SLOT_CLEAR_ACTIVE',resume=True)


def retire(count,*,resume=False):
    return write('LEARNER_SLOT_HEAD_ACTIVE',resume=True)+deletion('LEARNER_SLOT_RETIRE',count,not resume)+[
        'LEARNER_SLOT_RETIRE_PARENTS_FORCED']+clear(resume=resume)+['LEARNER_SLOT_RETIRE_RELEASED']


def reopen(count):
    # A complete retirement opens the immutable admission read-only, then
    # authenticates/reseals the independent current head before reclaiming.
    return ['LEARNER_REPLICA_LOCKED']+write('LEARNER_SLOT_HEAD_ACTIVE',resume=True)+clear(resume=True)+[
        'LEARNER_SLOT_INITIAL_RETIREMENT_FORCED']+retire(count,resume=True)+['LEARNER_STORE_BEFORE_RETURN']+t.trace(True)


def install(original,sequence):
    result=source(original)
    if sequence==1:result+=['LEARNER_SLOT_DIRECTORY_FORCED']+write('LEARNER_SLOT_PLAN')
    else:result+=['LEARNER_SLOT_REUSE_PLAN_CREATED']+write('LEARNER_SLOT_REUSE_PLAN',created=False)
    result+=write('LEARNER_SLOT_CANDIDATE',resume=True)+['LEARNER_SLOT_PLAN_RENAMED']+write('LEARNER_SLOT_ACTIVE',resume=True)
    if sequence>2:result+=['LEARNER_SLOT_OLD_INSTALL_DELETED','LEARNER_SLOT_OLD_INSTALL_PARENT_FORCED']
    return result+['LEARNER_SLOT_SOURCE_MOVED','LEARNER_SLOT_SOURCE_PARENTS_FORCED']+write('LEARNER_SLOT_INSTALL')+['LEARNER_SLOT_BEFORE_RETURN']


def select(sequence):
    if sequence==1:
        return t.trace(True)+['LEARNER_SLOT_HEAD_CANDIDATE_CREATED']+write('LEARNER_SLOT_HEAD_CANDIDATE',created=False)+[
            'LEARNER_SLOT_HEAD_RENAMED']+write('LEARNER_SLOT_HEAD_ACTIVE',resume=True)+['LEARNER_SLOT_HEAD_BEFORE_RETURN']
    return ['LEARNER_SLOT_ROLLING_HEAD_CREATED']+write('LEARNER_SLOT_ROLLING_HEAD_CANDIDATE',created=False)+[
        'LEARNER_SLOT_ROLLING_HEAD_RENAMED']+write('LEARNER_SLOT_HEAD_ACTIVE',resume=True)+['LEARNER_SLOT_ROLLING_HEAD_BEFORE_RETURN']


def expected(originals,snapshots):
    """One expected interval for each successful original snapshot boundary."""
    initial=snapshots['before-seed-handoff']
    old_count=len(originals[1])+1+len(initial.files['initial-typed'])
    # Derive the typed member count from the matched original, not an event row.
    typed_count=len(initial.files['seed-typed'])
    count=lambda revision:len(originals[revision])+1+typed_count
    start=list(t.s.p.CUTS)+source(originals[1])+admission()[:3]+write('LEARNER_RETENTION')+[
        'LEARNER_RETENTION_RESEAL_FORCED','LEARNER_RETENTION_RESEAL_PARENT_FORCED','LEARNER_RETENTION_RENAMED']+admission()[3:]+[
        'LEARNER_REPLICA_CREATED','LEARNER_REPLICA_LOCKED']+write('LEARNER_ROOT')+write('LEARNER_NODE')+[
        'LEARNER_SOURCE_MOVED','LEARNER_SOURCE_RETAINED_DIRECTORY_FORCED','LEARNER_SOURCE_MOVE_PARENTS_FORCED']+write('LEARNER_ADMISSION')+[
        'LEARNER_STORE_BEFORE_RETURN']+t.trace(False)+write('LEARNER_PREPARED')+[
        'LEARNER_PREPARED_BEFORE_SELECT','LEARNER_PREPARED_BEFORE_RETURN']+source(originals[2])+[
        'LEARNER_SUCCESSOR_DIRECTORY_FORCED']+write('LEARNER_SUCCESSOR_PLAN')+write('LEARNER_SUCCESSOR_CANDIDATE',resume=True)+[
        'LEARNER_SUCCESSOR_PLAN_RENAMED']+write('LEARNER_SUCCESSOR_ACTIVE',resume=True)+[
        'LEARNER_SUCCESSOR_SOURCE_MOVED','LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED']+write('LEARNER_SUCCESSOR_SELECT')+[
        'LEARNER_SUCCESSOR_BEFORE_RETURN']+t.trace(False)
    rows={
        'before-seed-handoff':start,
        'selected-seed-head':write('LEARNER_HEAD_CANDIDATE')+['LEARNER_HEAD_RENAMED']+write('LEARNER_HEAD_ACTIVE',resume=True)+['LEARNER_HEAD_BEFORE_RETURN'],
        'retired-seed-predecessor':seed_retire(old_count),
        'before-slot-selection':['LEARNER_REPLICA_LOCKED']+seed_retire(old_count,resume=True)+[
            'LEARNER_STORE_BEFORE_RETURN']+write('LEARNER_HEAD_ACTIVE',resume=True)+t.trace(True)+install(originals[3],1)+t.trace(False),
        'selected-slot-head':select(1),'retired-slot-seed':retire(count(2)),'reopened-slot-head':reopen(count(2)),
    }
    for revision in range(4,7):
        prefix=f'cycle-{revision}-';sequence=revision-2
        rows.update({prefix+'before-transfer':reopen(count(revision-2)),prefix+'installed':install(originals[revision],sequence),
                     prefix+'before-selection':t.trace(False),prefix+'selected':select(sequence),
                     prefix+'retired':retire(count(revision-1)),prefix+'reopened':reopen(count(revision-1))})
    return rows


def validate(events,positions,originals,snapshots):
    start=0
    for stage,trace in expected(originals,snapshots).items():
        end=positions[stage]['events']
        need(events[start:end]==trace,'learner cycles exact force interval: '+stage)
        start=end
    need(start==len(events),'learner cycles trailing force events')
