"""Additional actual-transport invariants for the complete owned canonical lane."""
from pathlib import Path
from . import guest_owned_canonical as run, cloud_package as package, guest_bootstrap as boot
from . import performance_model as m, remote_command as c, guest_workload_spec as workload


def audit(root,services,probe,endpoints,submissions,lost,views):
    m.need(views is not None and len(services.groups)==17 and probe.cells==list(run.CELLS),
           'canonical independent mounts/complete cell coverage')
    identifiers=[v['request']['commandId'] for v in submissions]
    m.need(len(set(identifiers))==len(identifiers) and len(set(lost))==len(lost) and set(lost)<=set(identifiers),
           'canonical duplicate submission/lost reply')
    for mode,cell in run.TAPES:
        group=services.groups[run.key(mode,cell)];configs=[cfg for _,_,cfg in group.clients]
        selected=dict(cell=cell,preset='canonical',repetition=services.repetition)
        rows=[v for v in submissions if v['mode']==mode and v.get('workload')==selected]
        active=probe.probes[run.key(mode,cell)].active[0]
        if mode!=package.MODES[2]:m.need(active==services.repetition,'canonical actual control host')
        for command,count in (('window',len(workload.specs(configs[0]))),('backup',int(mode in package.MODES[1:])),('restore-backup',int(mode in package.MODES[1:]))):
            issued=[v for v in rows if v['request']['command']==command]
            m.need(len(issued)==count and all(v['node']=='node-'+str(active) and v['request']['commandId'] in lost for v in issued),
                   'canonical original workload/backup lost reply coverage')
        activations=[v for v in rows if v['request']['command']=='fault' and v['request']['payload']==dict(action='activate')]
        m.need(len(activations)==int(mode==package.MODES[1]) and all(v['node']=='node-'+str(services.repetition) and v['request']['commandId'] in lost for v in activations),
               'canonical configured activation owner')
        for node,_,cfg in group.clients:
            path=views.root/('node-'+str(node))/Path(cfg['root']).relative_to(views.cell)
            m.need((path/boot.LOCAL_READY).is_file() and all(not (path/('node-'+str(n))).exists() for n in (1,2,3) if n!=node),
                   'canonical live neighbour authority')
            if mode==package.MODES[0]:
                m.need(not any((path/('node-'+str(n))).exists() for n in (1,2,3)),'canonical local replication storage')
                for other in (1,2,3):
                    if other!=node:m.need(not (views.root/('node-'+str(other))/Path(cfg['root']).relative_to(views.cell)).exists(),
                                         'canonical local ran on an idle host')
    m.need(all(v['request']['commandId'] in lost for v in submissions if 'faultCell' in v),'canonical fault lost reply coverage')
    for endpoint in endpoints:
        node=endpoint.value['binding']['node'];groups=[services.groups[run.key(mode,cell)] for mode,cell in run.TAPES]
        groups=[g for g in groups if any(cfg['binding']['node']==node for _,_,cfg in g.clients)];uses=len(groups)
        for phase in ('install','seal'):
            m.need(sum(v['action']=='bootstrap-'+phase for v in endpoint.calls)==uses and
                   sum(v['action']=='bootstrap-query-'+phase for v in endpoint.calls)==2*uses,'canonical bootstrap consumed/queries')
        chunks=sum(len(c.read(g.root/'bootstrap'/(node+'-transfer/descriptor.json'))['chunks']) for g in groups)
        counts={k:sum(v['action']=='source-'+k for v in endpoint.calls) for k in ('begin','chunk','finish','query')}
        m.need(counts==dict(begin=uses,chunk=chunks,finish=uses,query=4*uses),'canonical transfer consumed/queries')
        producer=sum(v['action']=='producer-prepare' for v in endpoint.calls)
        m.need(producer==int(node=='node-'+str(services.repetition)),'canonical exactly one seed producer')
    first=services.groups[run.key(package.MODES[0],'healthy')].root/'bootstrap/producer/original'
    record=c.read(first/'receipt.json');node='node-'+str(services.repetition)
    endpoint=next(ep for ep in endpoints if ep.value['binding']['node']==node)
    chunks=len(c.read(first/(node+'-descriptor.json'))['chunks'])
    counts={k:sum(v['action']=='producer-'+k for v in endpoint.calls) for k in ('prepare','query','manifest','chunk')}
    m.need(counts==dict(prepare=1,query=2,manifest=1,chunk=chunks+1) and record['readFailures']==1,
           'canonical original producer download coverage')
    producer=views.root/node/(endpoint.value['binding']['attempt']+'-'+node)/'source-producer'
    m.need((producer/'hidden-exports').is_dir() and not (producer/'exports').exists(),'canonical producer path isolation')
    c.write_once(root/'workload-submissions.json',submissions)
