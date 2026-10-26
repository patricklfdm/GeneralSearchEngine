"""Independent authority/correlation models, not native workload evidence."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_member_authority as auth,cloud_member_evidence as e,cloud_retention as retention
from . import test_cloud_native_runner as native_fixture,test_cloud_volume as volumes
from .test_cloud_identity import public_key
from .test_remote_java import fixture as java_fixture
from .evidence import encoded,digest


class RetainedFixture:
    """Actual native admission artifacts; external provider and history are modeled."""
    def __init__(self):
        native_fixture.NativeRunnerTest.setUpClass();self.base=native_fixture.NativeRunnerTest();self.base.setUp()
        try:self.prepare()
        except BaseException:self.close();raise
    def close(self):self.base.doCleanups()
    def prepare(self):
        self.session=self.base.open();session=self.session;session.heartbeat.close()
        self.root=self.base.root/'evidence';self.root.mkdir();self.request=session.owner.request
        self.claim=session.checkpoint();self.cfg=session.api.admission.cfg;self.source=session.api.admission.proof['source']
        shutil.copyfile(session.package,self.root/'inputs.tar.gz')
        # Select only files admitted by retention, excluding optional collection diagnostics.
        for source,target,names in ((session.output/'build-provenance','provenance',retention.BUILD_FILES),
                (session.output/'recent-cleanup','recent-cleanup',('observation.json','cleanup.zip','receipt.json'))):
            for name in names:
                destination=self.root/target/name;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/name,destination)
        guests=dict(provider={},guests={});storage=dict(records={},python={},java={},javaDescriptor=java_fixture(self.source)[0])
        for number,node in enumerate(auth.domains.topology.NODES,1):
            resources=self.claim['nodes'][node]['identity']['resources'];vm=next(r for r in resources if r['spec']['kind']=='instance')
            self.base.case.server.host_keys[vm['spec']['name']]=dict(queryPath='hostkeys/',queryValue=dict(items=[
                dict(namespace='hostkeys',key='ssh-ed25519',value=public_key(number+4).split()[1])]))
            row=auth.identity.observe(session.owner.provider,self.claim,node,deadline=session.api.clock()+30);guests['provider'][node]=row
            g=dict(schema=auth.guest.SCHEMA,instanceId=row['facts']['instanceId'],privateAddress=row['facts']['privateAddress'],
                user=self.request['guestAccess']['user'],bootId=f'00000000-0000-4000-8000-{number:012d}',uid=1001,gid=1002)
            guests['guests'][node]=g;facts=row['facts']
            req=dict(schema=auth.volume.SCHEMA,source=self.claim['source'],requestSha256=self.claim['requestSha256'],
                resourceClaimSha256=digest(encoded(self.claim)),resourceIdentitySha256=row['resourceIdentitySha256'],
                attempt=self.claim['attempt'],node=number,instanceId=facts['instanceId'],diskId=facts['dataDiskId'],bootDiskId=facts['bootDiskId'],
                sizeGiB=facts['dataDiskGiB'],bootSizeGiB=self.request['layout']['bootDiskGiB'],guest=g,publicKey=self.request['guestAccess']['publicKey'])
            model=volumes.VolumeTest();model.setUp()
            try:
                model.value=req;model.block=volumes.Block(req);model.token=model.grant();model.call('prepare')
                storage['records'][node]=model.call('check',model.grant())
            finally:model.doCleanups()
            own=dict(bootId=g['bootId'],uid=g['uid'],parentDevice=os.makedev(8,16),parentInode=100+number)
            storage['python'][node]=dict(schema=auth.python.RECEIPT,host=own,root=auth.volume.MOUNT+'/python-'+'d'*64,
                descriptorSha256='e'*64,filesSha256='f'*64)
            desc=storage['javaDescriptor'];storage['java'][node]=dict(schema=auth.java_image.RECEIPT,host=own,
                root=auth.volume.MOUNT+'/java-'+desc['sha256'],descriptorSha256=digest(encoded(desc)),filesSha256=digest(encoded(desc['files'])),java=self.source['java'])
        self.value=dict(schema='gse-v52-native-member-authority-v1',request=deepcopy(self.request),configuration=self.cfg,
            plan=session.api.admission.plan,approval=session.api.admission.approval,inputs=session.api.admission.proof,
            build=session.api.admission.build,observations=session.api.admission.observations,recentCleanup=session.api.admission.clean,
            claim=self.claim,guestIdentity=guests,storage=storage,placements={})
        # Generate expected topology from original resource identities; no test workload is run.
        for name in self.request['selection']['member']['histories']:
            history=digest(encoded([self.claim['requestSha256'],name]))
            transport=dict(schema=auth.routes.SCHEMA,execution=auth.routes.BOUND_EXECUTION,nodes={n:dict(host='127.0.0.1',
                port=31000+i,user=self.request['guestAccess']['user'],alias=guests['provider'][n]['alias'],
                hostPinSha256=guests['provider'][n]['sshHostPinSha256']) for i,n in enumerate(auth.domains.topology.NODES)})
            self.value['placements'][name]=dict(self.source,remoteTopology=dict(schema=auth.domains.topology.SCHEMA,placement='owned-private-hosts',
                groupId=str(auth.uuid.UUID(hex=history[:32])),members=[dict(node=n,host=guests['guests'][n]['privateAddress'],port=self.cfg['provider']['port']) for n in auth.domains.topology.NODES]),
                remoteHostDomains=dict(schema=auth.domains.SCHEMA,source=self.claim['source'],attempt=self.claim['attempt'],leaseSha256=digest(encoded(self.claim)),
                    nodes={n:dict(resourceIdentitySha256=guests['provider'][n]['resourceIdentitySha256'],privateAddress=guests['guests'][n]['privateAddress'],
                        bootId=guests['guests'][n]['bootId'],uid=guests['guests'][n]['uid'],sshHostPinSha256=guests['provider'][n]['sshHostPinSha256']) for n in auth.domains.topology.NODES}),remoteVoterTransport=transport)
        auth.artifacts.save(self.root/'authority.json',self.value)


class AuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=RetainedFixture();cls.addClassCleanup(cls.original.close)
    def setUp(self):self.value=deepcopy(self.original.value)
    def replay(self):return auth.replay(self.original.root,self.value,self.original.request,self.original.source,self.original.cfg)
    def test_original_provenance_guest_volume_and_history_bindings_replay_without_network(self):
        with patch.object(auth.identity.p.Store,'get',side_effect=AssertionError('replay attempted provider read')):
            result=self.replay()
        self.assertEqual(set(self.value['placements']),set(result['placements']))
        self.assertEqual(8,len(result['files']));self.assertEqual(13,len(result['lease']['resources']))
    def test_changed_external_source_request_configuration_or_approval_is_rejected(self):
        changes=[lambda v:v['request'].update(createdAt=v['request']['createdAt']+1),
            lambda v:v['configuration']['provider'].update(project='foreign'),lambda v:v['inputs']['source'].update(source='f'*40),
            lambda v:v['approval'].update(confirmed=False),lambda v:v['observations'].update(execution='offline-v52-provider-observations')]
        for change in changes:
            self.value=deepcopy(self.original.value);change(self.value)
            with self.subTest(change=change),self.assertRaises(ValueError):self.replay()
    def test_resource_id_alias_and_claim_hash_drift_are_rejected(self):
        for change in (lambda v:v['claim']['nodes']['node-1']['identity']['resources'][0].update(id='1234567'),
                       lambda v:v['claim']['firewalls'].pop(),
                       lambda v:v['guestIdentity']['provider']['node-1'].update(alias='gse-v52-'+'f'*32),
                       lambda v:v['guestIdentity']['provider']['node-1']['facts'].update(dataDiskId='7654321')):
            self.value=deepcopy(self.original.value);change(self.value)
            with self.assertRaises(ValueError):self.replay()
    def test_wrong_guest_boot_shared_host_or_root_volume_is_rejected(self):
        for change in (lambda v:v['guestIdentity']['guests']['node-2'].update(bootId=v['guestIdentity']['guests']['node-1']['bootId']),
            lambda v:v['storage']['records']['node-1']['startup'].update(status='FAIL'),
            lambda v:v['storage']['python']['node-1']['host'].update(parentDevice=os.makedev(8,1)),
            lambda v:v['storage']['java']['node-1'].update(root='/tmp/fallback-java')):
            self.value=deepcopy(self.original.value);change(self.value)
            with self.assertRaises(ValueError):self.replay()
    def test_different_history_group_ssh_pin_or_missing_placement_is_rejected(self):
        name=next(iter(self.value['placements']))
        for change in (lambda v:v['placements'][name]['remoteTopology'].update(groupId=str(auth.uuid.uuid4())),
            lambda v:v['placements'][name]['remoteVoterTransport']['nodes']['node-1'].update(hostPinSha256='f'*64),
            lambda v:v['placements'].pop(name)):
            self.value=deepcopy(self.original.value);change(self.value)
            with self.assertRaises(ValueError):self.replay()

    def member_case(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.parent=Path(temporary.name);self.root=self.parent/'retained';shutil.copytree(self.original.root,self.root)
        admitted=self.replay();self.actual={};rows=[];self.retained={}
        req=self.original.request;storage=self.value['storage'];invocation=admitted['preflight']['credentialContext']
        for number,name in enumerate(req['selection']['member']['histories'],1):
            spec=e.history.specification(name);binding=deepcopy(admitted['placements'][name])
            version='5.1.0' if spec['mode'].startswith('published') else e.inputs.VERSION
            names={f'general-search-engine-{version}.jar',f'general-search-engine-replication-{version}.jar','general-search-engine-4.4.0.jar'}
            binding.update(mode=spec['mode'],run=str(invocation['runId']),attempt=invocation['runAttempt'],
                measurementProfile=spec['profile'],artifacts={n:digest(admitted['files']['artifacts/'+n]) for n in names},
                remoteReceivers={n:{'originalRoot':p} for n,p in admitted['roots'][name].items()},
                remotePython=dict(nodes=storage['python']),remoteJava=dict(nodes=storage['java'],descriptorSha256=digest(encoded(storage['javaDescriptor']))))
            directory=self.root/'histories'/name;directory.mkdir(parents=True)
            raw=('synthetic history '+name).encode();(directory/'history.tar.gz').write_bytes(raw)
            result=dict(status='PASS',negatives=e.suite.load()['formalNegativeRules'][name],modeledWorkload=True)
            self.retained[name]=dict(status='PASS',history=name,family=spec['family'],mode=spec['mode'],binding=binding,result=result,
                archiveSha256=digest(raw),originalReads=1801,originalUpdates=180,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
            auth.artifacts.save(directory/'result.json',self.retained[name])
            self.actual[name]=dict(result=result,reads=1801,updates=180,domain=dict(groupId=binding['remoteTopology']['groupId'],
                historyId=str(auth.uuid.UUID(int=number))),manifestSha256=digest(name.encode()),archiveSha256=digest(raw))
            rows.append(dict(history=name,archive=name+'/portable/history.tar.gz',archiveSha256=digest(raw),bindingSha256=digest(encoded(binding)),reads=1801,updates=180))
        self.member=dict(schema='gse-v52-native-member-execution-v1',status='MEMBER_EXECUTED_NOT_QUALIFIED',selection=req['selection'],
            source=self.original.source,resourceClaimSha256=digest(encoded(self.value['claim'])),histories=rows,
            fullRemoteQualification=False,paidCloud=True,elapsedSeconds=1000)
        auth.artifacts.save(self.root/'member.json',self.member)
        self.manifest=e.parts.scan({n:self.root/n for n in e.names(req)},req)
        lease=auth.resource_claim(req,self.value['claim'])
        self.clean=dict(status='PASS',errors=[],leftovers=[],checks=[dict(name=r['spec']['name'],expectedId=r['id'],absent=True,observed=None) for r in lease['resources']])
        self.refresh_completion()
    def refresh_completion(self):
        req=self.original.request;self.completed=dict(schema='gse-v52-owned-completion-v1',execution=req['execution'],requestSha256=auth.a.validate_request(req,domain='native'),
            status='PASS',evidenceSha256=digest(encoded(self.manifest)),cleanupSha256=digest(encoded(self.clean)))
        baseline=auth.a.empty_ledger(domain='native');cost=self.value['plan']['reservation']['costMicrousd']
        self.ledger=auth.a.finish(auth.a.reserve(baseline,req,previous_cost=0,cost=cost),req,self.completed)
    def replay_member(self):
        return e.replay(self.root,self.original.request,self.manifest,self.completed,self.clean,self.ledger,
                        self.original.source,self.original.cfg,self.parent/'replay')
    def fake_replay(self,archive,name,binding,output):return deepcopy(self.actual[name])

    def test_complete_member_orchestration_replays_every_history_without_running_work(self):
        self.member_case()
        with patch.object(e,'replay_history',side_effect=self.fake_replay) as replay,patch.object(e.history,'run',side_effect=AssertionError('workload rerun')):
            value=self.replay_member()
        selected=self.original.request['selection']['member']['histories']
        self.assertEqual(selected,[call.args[1] for call in replay.call_args_list])
        self.assertEqual('MEMBER_REPLAYED_NOT_QUALIFIED',value['status'])
        self.assertFalse(value['paidCloud']);self.assertFalse(value['fullRemoteQualification'])
        self.assertEqual(4_000_000,value['accounting']['totalReservedCostMicrousd'])
        saved=auth.artifacts.read(self.parent/'replay/receipt.json');self.assertNotIn('result',next(iter(saved['histories'].values())))

    def test_changed_file_or_extra_secret_never_reaches_physical_replay(self):
        self.member_case();(self.root/'unexpected-private-key').write_bytes(b'not public evidence')
        with patch.object(e,'replay_history') as replay,self.assertRaisesRegex(ValueError,'unexpected member evidence'):
            self.replay_member()
        replay.assert_not_called();(self.root/'unexpected-private-key').unlink()
        (self.root/'inputs.tar.gz').write_bytes(b'changed original')
        with patch.object(e,'replay_history') as replay,self.assertRaisesRegex(ValueError,'file bytes changed'):self.replay_member()
        replay.assert_not_called()

    def test_changed_physical_replay_cannot_accept_the_retained_pass(self):
        self.member_case();name=next(iter(self.actual));self.actual[name]['result']={'status':'PASS','different':True}
        with patch.object(e,'replay_history',side_effect=self.fake_replay) as replay,self.assertRaisesRegex(ValueError,'replay differs'):
            self.replay_member()
        self.assertEqual(1,replay.call_count);self.assertEqual('FAIL',auth.artifacts.read(self.parent/'replay/receipt.json')['status'])

    def test_changed_original_invocation_is_rejected_even_with_matching_new_manifest(self):
        self.member_case();name=next(iter(self.actual));self.retained[name]['binding']['run']='999'
        (self.root/'histories'/name/'result.json').write_bytes(encoded(self.retained[name]))
        self.manifest=e.parts.scan({n:self.root/n for n in e.names(self.original.request)},self.original.request);self.refresh_completion()
        with patch.object(e,'replay_history') as replay,self.assertRaisesRegex(ValueError,'original invocation'):self.replay_member()
        replay.assert_not_called()

    def test_wrong_cleanup_identity_or_changed_reserved_cost_cannot_be_qualified(self):
        self.member_case();self.clean['checks'][0]['expectedId']='123456789';self.refresh_completion()
        with self.assertRaisesRegex(ValueError,'exact-ID'):e.completion(self.original.request,self.manifest,self.completed,self.clean,self.ledger,self.value['claim'],self.value['plan'])
        self.clean['checks'][0]['expectedId']=self.value['claim']['firewalls'][0]['id'];self.refresh_completion()
        self.ledger['entries'][0]['reservedCostMicrousd']+=1
        with self.assertRaisesRegex(ValueError,'reservation/terminal'):e.completion(self.original.request,self.manifest,self.completed,self.clean,self.ledger,self.value['claim'],self.value['plan'])

    def test_partial_retained_history_rows_cannot_form_a_complete_member(self):
        self.member_case();self.member['histories'].pop();(self.root/'member.json').write_bytes(encoded(self.member))
        self.manifest=e.parts.scan({n:self.root/n for n in e.names(self.original.request)},self.original.request);self.refresh_completion()
        with patch.object(e,'replay_history',side_effect=self.fake_replay),self.assertRaisesRegex(ValueError,'complete member history rows'):self.replay_member()


if __name__=='__main__':unittest.main()
