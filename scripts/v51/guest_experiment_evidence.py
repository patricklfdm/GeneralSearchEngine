"""Independent, portable all-cell acceptance; partial scopes cannot close a preset."""
from pathlib import Path
from . import performance_model as m, remote_command as c, remote_collection as parts, cloud_authority as a
from . import guest_three_mode_evidence as healthy, guest_fault_evidence as faults, cloud_package as package
from .guest_owned_experiment import CELLS, FAULTS, SCOPE
from . import native_experiment_timing as limits


def contract(root, *, authority=a):
    m.need({p.name for p in root.iterdir()} <= {'plan.json','validation.json',*CELLS,*(cell+'-timeline.json' for cell in CELLS)},'owned experiment extra root input')
    plan=c.read(root/'plan.json');req=plan['request'];sha=authority.validate_request(req);service=plan['services']
    m.need(plan['scope']==SCOPE and req['member']=='experiment' and service['status']=='PASS' and service['requestSha256']==sha and
           [v['case'] for v in service['cells']]==list(FAULTS) and all(v['receipt']['status']=='PASS' and v['receipt']['requestSha256']==sha for v in service['cells']), 'owned experiment service set')
    hp=c.read(root/'healthy/plan.json')
    m.need(hp['request']==req and hp['services']==service['healthy'],'owned experiment healthy request/service binding')
    previous=0;manifest=None;groups=set()
    for cell in CELLS:
        row=c.read(root/(cell+'-timeline.json'));start,end=row['startNanos'],row['endNanos']
        m.need(row['cell']==cell and row['status']=='PASS' and type(start) is int and type(end) is int and
               previous<=start<end and end-start<=limits.cell(req,cell)*10**9,'owned experiment cell order/budget')
        previous=end
        timing=c.read(root/cell/('timeline.json' if cell=='healthy' else 'receipt.json'))
        m.need(start<=timing['startNanos']<=timing['endNanos']<=end,'owned experiment original cell interval')
        if cell=='healthy':
            paths=[root/'healthy'/mode/'plan.json' for mode in package.MODES]
        else:paths=[root/cell/'plan.json']
        for path in paths:
            value=c.read(path);m.need(value['request']==req,'owned experiment mixed source/request')
            configs=value['configs'];identities={cfg['groupId'] for cfg in configs}
            m.need(len(identities)==1 and not groups.intersection(identities),'owned experiment reused group')
            groups.update(identities)
            digests={cfg['packageManifestSha256'] for cfg in configs}
            m.need(len(digests)==1 and (manifest is None or digests=={manifest}),'owned experiment mixed package')
            manifest=next(iter(digests))
    m.need(len(groups)==6,'owned experiment group coverage')
    return req


def validate(root, output, *, authority=a):
    root=c.directory(root);output=Path(output);output.mkdir(mode=0o700,parents=True,exist_ok=False);parts.inventory(root)
    req=contract(root,authority=authority);healthy_result=healthy.validate(root/'healthy',output/'healthy',authority=authority);budgets=dict(healthy_result['budgets'])
    reports=[dict(cell='healthy',result=healthy_result)]
    for cell in FAULTS:reports.append(dict(cell=cell,result=faults.replay_case(root/cell,output/cell,req,budgets,authority=authority)))
    m.need(all(budgets[k]<=parts.LIMITS[k] for k in budgets),'owned experiment combined evidence budget')
    return dict(status='PASS',scope=SCOPE,cells=reports,budgets=budgets,healthyCalls=270,paidCloud=False,
        fullRemoteQualification=False,ownedExperimentQualified=True,requestSha256=authority.validate_request(req))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    print(m.canonical(validate(args.input,args.output)).decode())
