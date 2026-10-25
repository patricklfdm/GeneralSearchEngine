"""Exact unchanged-owner audit; historical prefixes remain conditional fixtures."""
from pathlib import Path
import hashlib,json,shutil,tempfile


def need(value,message):
    if not value:raise ValueError(message)


def inventory(root):
    result={}
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(),'refusal symlink')
        need(len(result)<4096,'refusal file count')
        if path.is_dir():result[str(path.relative_to(root))]=None
        elif path.is_file():
            need(path.stat().st_size<=64*1024*1024,'refusal file size')
            result[str(path.relative_to(root))]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        else:raise ValueError('refusal nonregular file')
    return result


def validate_voter(path):
    need({v.name for v in path.iterdir()}=={'before','after','receipt.json'},'refusal evidence inventory')
    before=inventory(path/'before');need(before==inventory(path/'after'),'refusal changed original bytes')
    need('pending.accept' in before and 'selector.gsr' in before and 'grants.gsr' in before,'refusal incomplete original')
    value=json.loads((path/'receipt.json').read_text())
    need(value==dict(status='REJECTED',reason='CAPACITY_EXCEEDED',outcome='NOT_SUBMITTED',events=[],leasesAfterClose=0,reopenedRefusal=True,conditionalPrefix=True),'refusal receipt')
    return len(before)


def validate(root):
    root=Path(root);need({p.name for p in root.iterdir()}=={'reserve-refusal','intent-refusal'},'refusal case inventory')
    rows=[]
    for case in ('reserve-refusal','intent-refusal'):
        path=root/case;need({p.name for p in path.iterdir()}=={'node-1','node-2','node-3'},'refusal voter inventory')
        for name in ('node-1','node-2','node-3'):
            rows.append(dict(case=case,node=name,files=validate_voter(path/name),status='PASS'))
    return dict(status='PASS',cases=rows,scope='unchanged conditional-prefix owner files; no public lifetime claim')


def qualify(root):
    root=Path(root);result=validate(root);rows=[]
    for name,reason in [('changed-original','refusal changed original bytes'),('lost-original','refusal changed original bytes'),
                        ('write-event','refusal receipt'),('lease','refusal receipt'),('outcome','refusal receipt'),('symlink','refusal symlink')]:
        with tempfile.TemporaryDirectory(prefix='v53-capacity-negative-') as temp:
            copy=Path(temp)/'node';shutil.copytree(root/'reserve-refusal/node-1',copy)
            if name=='changed-original':(copy/'after/grants.gsr').write_bytes(b'changed')
            elif name=='lost-original':(copy/'after/pending.accept').unlink()
            elif name=='symlink':(copy/'after/alias').symlink_to('grants.gsr')
            else:
                p=copy/'receipt.json';value=json.loads(p.read_text())
                if name=='write-event':value['events']=['ACCEPT_VALIDATED']
                elif name=='lease':value['leasesAfterClose']=1
                else:value['outcome']='SUCCESS'
                p.write_text(json.dumps(value))
            try:validate_voter(copy)
            except ValueError as error:need(str(error)==reason,'unrelated capacity negative: '+name+': '+str(error))
            else:raise ValueError('capacity mutation accepted: '+name)
        rows.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negativeCases=rows,originalFirst=True)


if __name__=='__main__':
    import sys
    print(json.dumps(qualify(sys.argv[1]),sort_keys=True))
