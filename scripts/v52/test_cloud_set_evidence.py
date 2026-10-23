"""Complete-set orchestration models; physical replay is qualified separately."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_set_evidence as s,cloud_prepared as prepared
from .test_cloud_prepared import arguments
from .test_cloud_preflight import configuration
from .test_cloud_authority import completion
from .test_measurement_m01_set import fixtures as m01_fixtures


def fixture():
    values=[];replayed={};ledger=s.a.empty_ledger(domain='native');source=arguments()['proof']['source'];cfg=configuration()
    m01_bindings,m01_members=m01_fixtures();counter=0
    for number,name in enumerate(s.suite.MEMBERS,1):
        args=arguments(member=name,attempt=f'{number:032x}');req=prepared.prepare(**args)['request']
        # Use the same external configuration as each independently admitted plan.
        cfg.update(layout=args['resource_layout'],policy=args['ownership_policy']);cfg['projectNumber']=args['project_number']
        completed=completion(req);ledger=s.a.finish(s.a.reserve(ledger,req,previous_cost=(number-1)*4_000_000,cost=4_000_000),req,completed)
        values.append(dict(root='/fixtures/'+name,request=req,manifest={},completed=completed,cleanup={}))
        lease=s.a.lease(req,1001);lease['phase']='ACTIVE'
        for i,row in enumerate(lease['resources']):row.update(attempted=True,id=str(number*100+i))
        claim=s.a.resource_claim(lease);invocation=dict(run=str(1000+number),attempt=1);histories={};bindings={}
        for key,spec in req['selection']['member']['profiles'].items():
            counter+=1;family=spec['family']
            if family=='M01':
                binding=deepcopy(m01_bindings[key]);binding.update(source,**invocation)
                result=deepcopy(m01_members[key]['result']);reads,updates=1801,180
            else:
                binding=dict(source,**invocation);result={'status':'PASS'}
                if family=='UNTIMED':reads,updates=11,3
                elif family=='M04':reads,updates=4,4
                else:reads,updates=spec['profile']['readCount']+1+(family=='M03'),3+spec['profile']['releaseUpdate']
            binding['remoteHostDomains']=dict(nodes={f'node-{i}':dict(bootId=f'boot-{number}-{i}') for i in (1,2,3)})
            if family!='UNTIMED':result['negatives']=s.suite.load()['formalNegativeRules'][key]
            bindings[key]=binding;histories[key]=dict(result=result,reads=reads,updates=updates,
                domain=dict(groupId=f'group-{counter}',historyId=f'history-{counter}'),manifestSha256=f'{counter:064x}')
        replayed[name]=dict(status='MEMBER_REPLAYED_NOT_QUALIFIED',selection=req['selection'],source=source,
            configurationSha256=s.authority.preflight.configuration(cfg),fullRemoteQualification=False,paidCloud=False,
            histories=histories,bindings=bindings,claim=claim,invocation=invocation,accounting=dict(reservedCostMicrousd=4_000_000))
    return values,replayed,source,cfg,ledger


class SetTest(unittest.TestCase):
    def setUp(self):
        self.values,self.replayed,self.source,self.cfg,self.ledger=fixture()
        self.selected=s.suite.complete_selection([v['request']['selection'] for v in self.values])
    def reduce(self):return s.results(self.replayed,self.selected,self.source,self.cfg,self.ledger)

    def test_all_nine_executions_have_exact_full_counts_and_remain_unqualified(self):
        value=self.reduce();self.assertEqual('COMPLETE_SET_REPLAYED_NOT_QUALIFIED',value['status'])
        self.assertEqual(27428,value['totals']['reads']);self.assertEqual(2760,value['totals']['updates'])
        self.assertEqual(2700,value['m01']['nominalOfferedSeconds']);self.assertEqual(29700,value['m01']['completedOfferedCalls'])
        self.assertEqual(36_000_000,value['selectedReservedCostMicrousd']);self.assertFalse(value['fullRemoteQualification'])

    def test_missing_mixed_or_failed_members_reject_before_physical_replay(self):
        for mutate,reason in (
            (lambda v:v.pop(),'nine original'),
            (lambda v:v[-1]['request']['selection']['binding'].update(sequence='f'*32),'mixed source'),
            (lambda v:v[-1].update(root=v[0]['root']),'overlapping'),
            (lambda v:v[-1]['request']['selection']['binding'].update(checkoutSha256='f'*64),'external source')):
            values=deepcopy(self.values);mutate(values)
            with patch.object(s.member,'replay') as replay,self.assertRaisesRegex(ValueError,reason):
                s.replay(values,self.source,self.cfg,self.ledger,'unused')
            replay.assert_not_called()
        self.ledger['entries'][-1]['status']='FAIL'
        with self.assertRaisesRegex(ValueError,'terminal successes'):s.inputs(self.values,self.source,self.cfg,self.ledger)

    def test_any_member_can_be_first_and_every_original_is_replayed_once(self):
        for first in range(5):
            with tempfile.TemporaryDirectory() as directory:
                order=self.values[first:]+self.values[:first];calls=[]
                def replay(root,req,manifest,completed,clean,ledger,source,cfg,output,**kw):
                    name=req['selection']['member']['name'];calls.append(name);Path(output).mkdir()
                    s.artifacts.save(Path(output)/'receipt.json',dict(status='modeled-original-replay'))
                    return deepcopy(self.replayed[name])
                with patch.object(s.member,'replay',side_effect=replay):
                    result=s.replay(order,self.source,self.cfg,self.ledger,Path(directory)/'set')
                self.assertEqual([v['request']['selection']['member']['name'] for v in order],calls)
                self.assertEqual(calls,result['completedMembers']);self.assertEqual(9,len(result['memberReceiptHashes']))

    def test_failed_original_stops_without_retry_or_success_fragment_stitching(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'set';calls=[]
            def replay(root,req,*args,**kwargs):
                name=req['selection']['member']['name'];calls.append(name)
                if len(calls)==3:raise ValueError('original physical failure')
                return self.replayed[name]
            with patch.object(s.member,'replay',side_effect=replay),self.assertRaisesRegex(ValueError,'original physical failure'):
                s.replay(self.values,self.source,self.cfg,self.ledger,output)
            self.assertEqual(list(s.suite.MEMBERS)[:3],calls)
            self.assertEqual(list(s.suite.MEMBERS)[:2],s.artifacts.read(output/'receipt.json')['completedMembers'])

    def test_duplicate_run_resources_boots_and_each_history_identifier_reject(self):
        original=deepcopy(self.replayed);first,second=list(self.replayed)[:2]
        for mutate,reason in (
            (lambda v:v[second].update(invocation=v[first]['invocation']),'invocation'),
            (lambda v:v[second]['claim']['firewalls'][0].update(id=v[first]['claim']['firewalls'][0]['id']),'resources'),
            (lambda v:next(iter(v[second]['bindings'].values())).update(remoteHostDomains=next(iter(v[first]['bindings'].values()))['remoteHostDomains']),'boots'),
            (lambda v:next(iter(v[second]['histories'].values()))['domain'].update(groupId=next(iter(v[first]['histories'].values()))['domain']['groupId']),'history/group'),
            (lambda v:next(iter(v[second]['histories'].values()))['domain'].update(historyId=next(iter(v[first]['histories'].values()))['domain']['historyId']),'history/group'),
            (lambda v:next(iter(v[second]['histories'].values())).update(manifestSha256=next(iter(v[first]['histories'].values()))['manifestSha256']),'history/group')):
            self.replayed=deepcopy(original);mutate(self.replayed)
            with self.assertRaisesRegex(ValueError,reason):self.reduce()

    def test_count_negative_and_compiled_consumer_drift_reject(self):
        original=deepcopy(self.replayed)
        for mutate,reason in (
            (lambda v:next(iter(v['experiment']['histories'].values())).update(reads=0),'total counts'),
            (lambda v:next(iter(v['failure-drill-m02-below']['histories'].values()))['result']['negatives'].pop(),'original negatives'),
            (lambda v:next(iter(v['canonical-3']['bindings'].values()))['classes'].update(extra='f'*64),'mixed artifact'),
            (lambda v:next(iter(v['canonical-3']['bindings'].values())).update(run='999'),'admitted invocation')):
            self.replayed=deepcopy(original);mutate(self.replayed)
            with self.assertRaisesRegex(ValueError,reason):self.reduce()

    def test_failed_attempt_cost_remains_in_ledger_without_counting_as_success(self):
        req=prepared.prepare(**arguments(member='experiment',attempt='f'*32))['request']
        failed=s.a.finish(s.a.reserve(s.a.empty_ledger(domain='native'),req,previous_cost=0,cost=4_000_000),req,completion(req,'FAIL'))
        self.ledger['entries']=failed['entries']+self.ledger['entries']
        value=self.reduce();self.assertEqual(40_000_000,value['ledgerReservedCostMicrousd'])
        self.assertEqual(36_000_000,value['selectedReservedCostMicrousd'])


if __name__=='__main__':unittest.main()
