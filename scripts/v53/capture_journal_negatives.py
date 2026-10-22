"""Original-first rejection of torn journal rewrites and lost recovery forces."""
import json
from pathlib import Path
import shutil
import tempfile
from . import capture_journal_evidence as e
from . import capture_recovery_negatives as original
from .membership_model import need

CASES=original.CASES+(('journal-prefix','capture exact crash snapshot'),('recovery-prefix','capture exact recovery crash snapshot'),
                     ('recovery-force','capture repeated recovery force order'),('recovery-parent-force','capture repeated recovery force order'))


def selected(name):
    if name in ('journal-prefix','recovery-prefix','recovery-force','recovery-parent-force'):
        cut='BASIS_RECOVERY_PARENT_FORCED' if name=='recovery-parent-force' else 'BASIS_RECOVERY_FORCED' if name=='recovery-force' else 'BASIS_RECOVERY_PREFIX_WRITTEN'
        return next(c for c in e.cases() if c['mode']=='recover-halt' and c['cut']==cut)
    return original.selected(name)


def mutate(root,name):
    if name in ('journal-prefix','recovery-prefix'):
        path=root/('crash' if name=='journal-prefix' else 'recovery-crash')/'grants.gsr';raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    elif name in ('recovery-force','recovery-parent-force'):
        path=root/'recovery-fault.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()];point='BASIS_RECOVERY_FORCED' if name=='recovery-force' else 'BASIS_RECOVERY_PARENT_FORCED';rows=[r for r in rows if r.get('event')!=point];path.write_bytes(b''.join(e.g.f.canonical(r)+b'\n' for r in rows))
    else:original.mutate(root,name)


def run(original_path):
    original_path=Path(original_path);e.validate(original_path);result=[]
    with tempfile.TemporaryDirectory(prefix='v53-capture-journal-negatives-') as temp:
        for name,reason in CASES:
            case=selected(name);root=Path(temp)/name;shutil.copytree(original_path/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated capture journal negative: '+name+': '+str(error));result.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted capture journal negative: '+name)
    return result
