"""Original-first, exact-reason rejection of current generation and ownership substitutions."""
import json
from pathlib import Path
import shutil
import tempfile
from . import current_generation_evidence as e
from .membership_model import need

CASES=(('selector','current selector manifest binding'),('node','current selector node'),('inactive','current selected inventory'),
       ('packet','current file bytes'),('missing-tail','current file inventory'),('tail','current owned tail copy'),
       ('omitted-tail','current materialization inventory'),('promise','current promise journal binding'),('cut','current capsule binding'),
       ('owned-observation','current local ownership observation'),('returned-tail','current returned tail'),
       ('missing-force','current force order'),('runtime-relabel','current runtime scope'))


def rewrite(path,change):
    manifest=path/'generations/a/generation.gsr';value=e.f.decode(manifest.read_bytes(),'records','GENERATION');change(value)
    raw=e.f.encode('records','GENERATION',value);manifest.write_bytes(raw)
    selector=path/'selector.gsr';value=e.f.decode(selector.read_bytes(),'records','SELECTOR');value['digest']=e.sha(raw);selector.write_bytes(e.f.encode('records','SELECTOR',value))


def mutate(root,name):
    if name=='runtime-relabel':
        path=root/'case.json';row=json.loads(path.read_text());row['remoteOwnershipVerified']=True;path.write_bytes(e.f.canonical(row));return
    if name in ('owned-observation','returned-tail','missing-force'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='owned-observation':rows[-1]['ownedTail']['storage']='00000000-0000-0000-0000-000000000009'
        elif name=='returned-tail':rows[-1]['accepted']=None
        else:rows=[row for row in rows if row.get('event')!='CURRENT_SELECTOR_FORCED']
        path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows));return
    path=root/'initial';generation=path/'generations/a'
    if name in ('selector','node'):
        file=path/'selector.gsr';value=e.f.decode(file.read_bytes(),'records','SELECTOR');value['digest' if name=='selector' else 'node']='00'*32 if name=='selector' else 'node-2';file.write_bytes(e.f.encode('records','SELECTOR',value))
    elif name=='inactive':(path/'generations/b').mkdir()
    elif name=='packet':
        file=generation/'source.gscp';raw=bytearray(file.read_bytes());raw[-1]^=1;file.write_bytes(raw)
    elif name=='missing-tail':(generation/'owned-tail.gsr').unlink()
    elif name=='tail':rewrite(path,lambda value:value.update(ownedTail='00'*32))
    elif name=='omitted-tail':rewrite(path,lambda value:value.update(ownedTail=None))
    elif name=='promise':rewrite(path,lambda value:value.update(promise='00'*32))
    elif name=='cut':rewrite(path,lambda value:value['cut'].update(entry='00'*32))
    else:raise ValueError('unknown current mutation')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['tail'] and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-current-negatives-') as temp:
        for name,reason in CASES:
            path=Path(temp)/name;shutil.copytree(original/case['name'],path);mutate(path,name)
            try:e.validate_case(path,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated current negative rejection: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted current negative: '+name)
    return results
