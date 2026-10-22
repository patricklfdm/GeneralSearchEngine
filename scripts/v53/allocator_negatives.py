"""Original-first, reason-specific evidence corruption for allocator qualification."""
from pathlib import Path
import shutil
import tempfile
from . import allocator_evidence as e
from . import format_fixture as f
from .membership_model import need

CASES=(
    ('rolled-back-counter','clean','none','allocator durable counter'),
    ('foreign-owner','clean','none','allocator record owner'),
    ('foreign-root','clean','none','foreign root'),
    ('genesis-replaced','clean','none','allocator genesis identity'),
    ('missing-directory-force','clean','none','allocator return before complete forces'),
    ('wrong-crash-cut','kill','ALLOCATOR_FORCED','allocator crash cut mismatch'),
    ('mutated-lock-conflict','lock','none','lock conflict changed bytes'),
    ('repaired-torn-pending','halt','ALLOCATOR_CREATED','expected empty interrupted pending'),
    ('false-return','halt','ALLOCATOR_BEFORE_RETURN','allocator callback after crash'),
    ('runtime-relabel','clean','none','allocator runtime scope'),
)


def edit_record(path, kind, **changes):
    value=f.decode(path.read_bytes(),'records',kind);value.update(changes);path.write_bytes(f.encode('records',kind,value))


def mutate(directory,name):
    if name=='rolled-back-counter':edit_record(directory/'final/allocator.gsr','ALLOCATOR',counter=0)
    elif name=='foreign-owner':edit_record(directory/'final/allocator.gsr','ALLOCATOR',node='node-2')
    elif name=='foreign-root':edit_record(directory/'final/node.gsr','NODE',root='00'*32)
    elif name=='genesis-replaced':edit_record(directory/'final/genesis.gsr','GENESIS',application='00'*32)
    elif name in ('missing-directory-force','wrong-crash-cut','false-return'):
        path=directory/('first.stdout' if name=='missing-directory-force' else 'fault.stdout')
        rows=[e.json.loads(v) for v in path.read_text().splitlines()]
        if name=='missing-directory-force':rows=[r for r in rows if r.get('event')!='ALLOCATOR_DIRECTORY_FORCED']
        elif name=='wrong-crash-cut':rows[0]['event']='ALLOCATOR_CREATED'
        else:rows.append(dict(status='PASS',counter=10))
        path.write_bytes(b''.join(f.canonical(r)+b'\n' for r in rows))
    elif name=='mutated-lock-conflict':edit_record(directory/'blocked/allocator.gsr','ALLOCATOR',counter=1)
    elif name=='repaired-torn-pending':(directory/'final/allocator.pending.gsr').unlink()
    elif name=='runtime-relabel':
        path=directory/'case.json';row=e.load(path);row['runtimeEnabled']=True;path.write_bytes(f.canonical(row))
    else:raise ValueError('unknown allocator negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    with tempfile.TemporaryDirectory(prefix='v53-allocator-negatives-') as temp:
        for name,mode,cut,reason in CASES:
            case=next(c for c in e.cases() if c['size']==3 and c['mode']==mode and c['cut']==cut)
            target=Path(temp)/name;shutil.copytree(original/case['name'],target);mutate(target,name)
            try:e.validate_case(target,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated allocator negative rejection: '+name+': '+str(error))
                results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted allocator negative: '+name)
    return results
