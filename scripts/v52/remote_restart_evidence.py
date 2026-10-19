"""Portable original crash, retained bytes and second-generation correlation."""
from pathlib import Path
from . import remote_voter as v,remote_restart_guest as guest,remote_voter_lifecycle_evidence as lifecycle
from .evidence import need,digest,encoded

FILE='restart-control.json'


def validate(root,binding):
    root=Path(root);scope=v.scope
    need(scope.domains.matches(binding,'remoteRestart',scope.RESTART_EXECUTION) and scope.history(binding)['case']==scope.RESTART_CASE,
         'restart retained scope')
    value=v.c.read(root/FILE);scenario=v.c.read(root/'scenario.json');node=scenario['leader']
    need(type(value) is dict and set(value)=={'schema','case','node','crash','restart'} and
         value['schema']=='gse-v52-restart-controller-v1' and value['case']==scope.RESTART_CASE and value['node']==node,
         'restart controller identity')
    old=root/scope.control_name(node);new=root/scope.control_name(node,2)
    config=v.c.read(old/'config.json',v.c.REQUEST_BYTES);second=v.c.read(new/'config.json',v.c.REQUEST_BYTES)
    sha=digest(encoded(config));new_sha=digest(encoded(second))
    need(config['binding']==second['binding']==binding and config['root']==second['root'] and config['node']==second['node']==node and
         scope.generation(config)==1 and scope.generation(second)==2 and config['session']!=second['session'] and
         config['socket']!=second['socket'],'restart retained generations')
    original=guest.crash_receipt(root,config,sha)
    preparation=v.c.read(old/'preparation.json',v.c.REQUEST_BYTES)
    need(set(preparation)=={'node','binding','session','host','generation'},'restart original preparation fields')
    lifecycle.configuration(config,preparation,config['root'])
    stopped=v.c.read(old/'stopped.json');exited=v.c.read(old/'exited.json')
    need(stopped['exitCode']==-9 and stopped['failure'] is None and exited==dict(configSha256=sha,
         service=original['identity']['service'],exitCode=0),'restart incomplete original exit')
    need(not (old/'lifecycle.json').exists(),'restart duplicate original export')
    need(scenario['crash']==dict(node=node,pid=original['identity']['jvm']['pid'],generation=1,exitCode=-9,preReopen=original['preReopen']) and
         guest.inventory(root/'pre-reopen'/node)==original['preReopen'],'restart scenario retained bytes')
    crash=value['crash'];restart=value['restart']
    need(type(crash) is dict and set(crash)=={'configSha256','submissionCount','terminalReplyLost','startNanos','endNanos','answerSha256'} and
         crash['configSha256']==sha and type(crash['submissionCount']) is int and crash['submissionCount']==1 and
         type(crash['terminalReplyLost']) is bool,'restart original crash count')
    event=None
    with (old/'events.jsonl').open('rb') as stream:
        while row:=v.receive(stream):event=row
    need(event and crash['answerSha256']==digest(encoded(dict(crash=original,event=event))),'restart original terminal digest')
    need(type(restart) is dict and set(restart)=={'configSha256','generation','startNanos','endNanos'} and
         restart['configSha256']==new_sha and restart['generation']==2,'restart generation observation')
    times=[scenario['killIssuedNanos'],crash['startNanos'],crash['endNanos'],scenario['exitObservedNanos'],
           scenario['restartIssuedNanos'],restart['startNanos'],restart['endNanos'],scenario['restartStartedNanos']]
    need(all(type(t) is int and t>0 for t in times) and all(a<b for a,b in zip(times,times[1:])),
         'restart whole-history milestone order')
    return dict(status='PASS',node=node,generations=2,retainedFiles=len(original['preReopen']))
