"""Replay all nine complete native members, in any order, without cloud I/O.

This is an internal byte/authority validator, not a native download capability.
Only a separately authenticated collector may promote its result to acceptance.
"""
from pathlib import Path
from . import cloud_authority as a,cloud_suite as suite,cloud_member_evidence as member
from . import cloud_artifacts as artifacts,cloud_member_authority as authority
from . import measurement_m01_set as m01
from .evidence import need,encoded,digest


def inputs(values,source,cfg,ledger):
    need(type(values) is list and len(values)==len(suite.MEMBERS),'V5.2 nine original member inputs required')
    requests=[];paths=[]
    for value in values:
        a.fields(value,'root request manifest completed cleanup','retained set input')
        req=value['request'];a.validate_request(req,domain='native');requests.append(req)
        need(req['selection']['binding']['source']==source['source'] and
             req['selection']['binding']['checkoutSha256']==source['checkoutSha256'] and
             req['configurationSha256']==authority.preflight.p.config(cfg['provider']),
             'V5.2 set external source/configuration mismatch')
        paths.append(Path(value['root']).resolve())
    selected=suite.complete_selection([v['selection'] for v in requests])
    need(len(set(paths))==len(suite.MEMBERS) and not any(x in y.parents for x in paths for y in paths if x!=y),
         'V5.2 set overlapping original member roots')
    view=a.inspect_ledger(ledger,domain='native')
    need(all(view['attempts'].get(a.validate_request(req,domain='native'))==dict(request=req,status='PASS') for req in requests),
         'V5.2 set requires all nine original terminal successes')
    return selected,view,paths


def results(values,selected,source,cfg,ledger):
    """Reduce only results returned by complete member replay, not loaded receipts."""
    need(set(values)==set(suite.MEMBERS),'V5.2 incomplete replayed cloud set')
    configuration=authority.preflight.configuration(cfg)
    groups=set();histories=set();manifests=set();resources=set();boots=set();runs=set()
    expected={};m01_members={};invocations={};read_count=update_count=cost=negative_count=0
    for name in suite.MEMBERS:
        value=values[name];selection=value['selection'];chosen=suite.member(name)
        need(value['status']=='MEMBER_REPLAYED_NOT_QUALIFIED' and value['source']==source and
             value['configurationSha256']==configuration and value['fullRemoteQualification'] is False and value['paidCloud'] is False and
             selection['binding']==selected['binding'] and selection['member']==chosen and
             set(value['histories'])==set(value['bindings'])==set(chosen['histories']),
             'V5.2 original replayed member scope')
        invocation=value['invocation'];run=(invocation['run'],invocation['attempt'])
        need(run not in runs,'V5.2 set reused original invocation');runs.add(run)
        claim=value['claim'];original=[*claim['firewalls'],*[r for node in claim['nodes'].values() for r in node['identity']['resources']]]
        own={(r['spec']['kind'],r['id']) for r in original}
        need(len(own)==13 and not own&resources,'V5.2 set reused original resources');resources.update(own)
        binding=value['bindings'][chosen['histories'][0]]
        own_boots={n['bootId'] for n in binding['remoteHostDomains']['nodes'].values()}
        need(len(own_boots)==3 and not boots&own_boots,'V5.2 set reused guest boots');boots.update(own_boots)
        cost+=value['accounting']['reservedCostMicrousd']
        for key,history in value['histories'].items():
            group,history_id=(history['domain'][k] for k in ('groupId','historyId'))
            need(group not in groups and history_id not in histories and history['manifestSha256'] not in manifests,
                 'V5.2 set reused history/group/manifest')
            groups.add(group);histories.add(history_id);manifests.add(history['manifestSha256'])
            read_count+=history['reads'];update_count+=history['updates']
            spec=chosen['profiles'][key]
            if spec['family']!='UNTIMED':
                negatives=suite.load()['formalNegativeRules'][key]
                need(history['result']['negatives']==negatives,'V5.2 set incomplete original negatives')
                negative_count+=len(negatives)
            if spec['family']=='M01':
                expected[key]=value['bindings'][key];invocations[key]=invocation
                m01_members[key]=dict(status='PASS',execution='m01-portable-member',qualifiedMeasurement=False,paidCloud=False,
                    binding=expected[key],domain=history['domain'],manifestSha256=history['manifestSha256'],result=history['result'])
    totals=suite.load()['totals']
    need(len(histories)==totals['histories'] and read_count==totals['reads'] and update_count==totals['updates'] and
         negative_count==totals['formalNegativesPerLocation'],'V5.2 set original total counts')
    measured=m01.validate_results(m01_members,expected,invocations=invocations)
    need(measured['nominalOfferedSeconds']==totals['nominalM01Seconds'],'V5.2 set frozen offered duration')
    return dict(status='COMPLETE_SET_REPLAYED_NOT_QUALIFIED',execution='retained-native-set-local-replay',
        fullRemoteQualification=False,paidCloud=False,source=source,binding=selected['binding'],members=list(suite.MEMBERS),logicalMembers=list(suite.LOGICAL_MEMBERS),
        totals=totals,m01=measured,selectedReservedCostMicrousd=cost,
        ledgerReservedCostMicrousd=a.inspect_ledger(ledger,domain='native')['reservedCostMicrousd'],ledgerSha256=digest(encoded(ledger)))


def replay(values,source,cfg,ledger,output,*,progress=lambda stage,**kw:None,expected_invocations=None):
    """All members share one separately selected ledger; no fragments or retries."""
    selected,_,paths=inputs(values,source,cfg,ledger);output=Path(output)
    if expected_invocations is not None:
        need(type(expected_invocations) is dict and set(expected_invocations)==set(suite.MEMBERS),
             'V5.2 protected original invocation inventory')
    need(not any(p.is_symlink() for p in (output,*output.parents)) and all(
        output.resolve()!=p and output.resolve() not in p.parents and p not in output.resolve().parents for p in paths),
        'V5.2 set replay output overlap')
    output.mkdir(parents=True,exist_ok=False);replayed={}
    receipt=dict(status='FAIL',fullRemoteQualification=False,paidCloud=False)
    try:
        for value in values:
            name=value['request']['selection']['member']['name'];progress('member-replay',name=name,completed=len(replayed))
            replayed[name]=member.replay(value['root'],value['request'],value['manifest'],value['completed'],value['cleanup'],
                ledger,source,cfg,output/name,progress=progress)
            if expected_invocations is not None:
                need(replayed[name]['invocation']==expected_invocations[name],'V5.2 replayed member not original protected invocation')
        receipt=results(replayed,selected,source,cfg,ledger)
        receipt['memberReceiptHashes']={name:digest((output/name/'receipt.json').read_bytes()) for name in replayed}
        return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__);raise
    finally:
        receipt['completedMembers']=list(replayed);artifacts.save(output/'receipt.json',receipt)
