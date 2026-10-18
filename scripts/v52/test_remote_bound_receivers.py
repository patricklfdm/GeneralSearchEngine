"""Bound route plumbing with synthetic hosts; these tests perform no cloud I/O."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_bound_receivers as bound,remote_host_domains as domains
from . import remote_python_package as package,remote_python_receiver as python
from . import remote_voter as voter,remote_voter_guest as guest,remote_voter_scope as scope
from . import remote_delivery_package as delivery,remote_delivery as delivery_client
from . import remote_voter_ssh_evidence as routes
from .test_remote_host_domains import fixture
from .test_remote_delivery import Fixture as DeliveryFixture


def transport(binding):
    binding['remoteVoterTransport']=dict(schema=routes.SCHEMA,execution=routes.BOUND_EXECUTION,nodes={node:dict(
        host='127.0.0.1',port=30000+i,user='operator',alias='gse-v52-'+str(i)*32,
        hostPinSha256=row['sshHostPinSha256']) for i,(node,row) in enumerate(binding[domains.FIELD]['nodes'].items(),1)})
    return binding


class BoundScopeTest(unittest.TestCase):
    def test_scopes_are_closed_and_local_and_bound_markers_cannot_mix(self):
        private=fixture()
        for local,expected in domains.EXECUTIONS.items():
            self.assertEqual(local,domains.execution({},local));self.assertEqual(expected,domains.execution(private,local))
            self.assertFalse(domains.matches(dict(private,test=local),'test',local))
        with self.assertRaisesRegex(ValueError,'unknown host execution scope'):domains.execution(private,'arbitrary')

    def test_private_topology_needs_every_execution_component_and_original_routes(self):
        value=transport(fixture());value.update(remoteVoterControl=domains.EXECUTIONS['local-persistent-voters-v1'],
            remoteVoterLifecycle=domains.EXECUTIONS[guest.EXECUTION],remotePython={},remoteDelivery={})
        domains.chain(value)
        for field in ('remoteVoterControl','remoteVoterLifecycle','remotePython','remoteDelivery'):
            changed=deepcopy(value);changed.pop(field)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'chain incomplete'):domains.chain(changed)
        value['remoteVoterLifecycle']=guest.EXECUTION
        with self.assertRaisesRegex(ValueError,'scope changed'):domains.chain(value)

    def test_formal_and_recovery_admit_only_the_original_full_profiles(self):
        from . import cloud_suite
        for name,row in cloud_suite.load()['histories'].items():
            if row['family']=='UNTIMED':continue
            binding=fixture();profile=row['profile'];family=row['family']
            binding.update(mode=profile['mode'],measurementProfile=deepcopy(profile),programSha256=scope.partition.model.PLAN_SHA,
                readParameters=profile['parameters'] if family in ('M02','M03') else scope.partition.options.parameters())
            if family=='M04':
                binding['faultParameters']=profile['faultParameters']
                key,local=('remoteRestart',scope.RESTART_EXECUTION) if name==scope.RESTART_CASE else ('remotePartition',scope.partition.EXECUTION)
                binding[key]=domains.execution(binding,local)
            else:
                binding['remoteFormal']=domains.execution(binding,scope.FORMAL_EXECUTION)
                self.assertTrue(scope.formal(binding))
                binding['remoteFormal']=scope.FORMAL_EXECUTION
                with self.assertRaisesRegex(ValueError,'formal service binding'):scope.formal(binding)
                binding['remoteFormal']=domains.execution(binding,scope.FORMAL_EXECUTION)
            self.assertEqual(profile,scope.history(binding))
            if name==scope.RESTART_CASE:
                self.assertEqual(2,scope.generation(dict(binding=binding,generation=2)))
                binding['remoteRestart']=scope.RESTART_EXECUTION
                with self.assertRaisesRegex(ValueError,'undeclared generation'):scope.generation(dict(binding=binding,generation=2))

    def test_local_launcher_cannot_interpret_bound_paths_as_local_directories(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(voter.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'local voter cannot launch'):voter.Client(Path(directory)/'absent','node-1',fixture(),[])
            self.assertEqual([],list(Path(directory).iterdir()));spawn.assert_not_called()

    def test_changed_observed_host_rejects_before_guest_creates_a_control_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pin=voter.host.observe(root);binding=transport(fixture())
            binding.update(remoteVoterControl=domains.EXECUTIONS['local-persistent-voters-v1'],
                remoteVoterLifecycle=domains.EXECUTIONS[guest.EXECUTION],remotePython={},remoteDelivery={},
                remoteReceivers={'node-1':dict(originalRoot=str(root))})
            value=dict(node='node-1',binding=binding,session='a'*32,host=pin)
            with self.assertRaisesRegex(ValueError,'bound guest host changed'):guest.preparation(root,value)
            self.assertEqual([],list(root.iterdir()))


class BoundPackageTest(DeliveryFixture):
    def private(self):
        self.binding.update(fixture());self.binding['java']=self.source['java']
        archive,meta=delivery.create(self.producer,self.root/'private-capsule',self.binding)
        value=deepcopy(self.value);value.update(package=meta,execution=delivery.execution(meta))
        value['host'].update(bootId=meta['hostDomains']['nodes']['node-1']['bootId'],uid=1000)
        return archive,meta,value

    def test_private_capsule_binds_the_three_hosts_and_same_immutable_inputs(self):
        archive,meta,value=self.private()
        self.assertEqual(meta,delivery.verify_archive(archive,meta));self.assertEqual(value,delivery.descriptor(value))
        self.assertEqual(self.binding[domains.FIELD],meta['hostDomains'])
        self.assertEqual(self.meta['artifacts'],meta['artifacts']);self.assertEqual(self.meta['classes'],meta['classes'])
        self.assertEqual('bound-host-receiver-delivery-only',value['execution'])

    def test_unknown_local_private_and_foreign_host_combinations_reject(self):
        _,meta,value=self.private()
        for change,reason in ((lambda v:v['package'].pop('hostDomains'),'missing independent host domains'),
            (lambda v:v.update(execution=delivery.EXECUTION),'descriptor scope'),
            (lambda v:v['host'].update(uid=1001),'bound guest host changed'),
            (lambda v:v['package']['hostDomains']['source'].update(source='e'*40),'source binding')):
            wrong=deepcopy(value);change(wrong)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):delivery.descriptor(wrong)
        local=deepcopy(self.meta);local['hostDomains']=meta['hostDomains']
        with self.assertRaisesRegex(ValueError,'cannot promote local'):delivery.validate(local)

    def test_bound_delivery_cannot_fall_back_to_controller_python_checkout(self):
        _,meta,_=self.private()
        with patch.object(delivery_client,'Endpoint') as endpoint:
            with self.assertRaisesRegex(ValueError,'requires installed Python'):delivery_client.Delivery({},'/guest','node-1',meta)
            endpoint.assert_not_called()


class BoundPlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=dict(source='a'*40,checkoutSha256='b'*64,java={'java.runtime.version':'unit','java.vendor':'unit'})
        cls.payload,cls.descriptor,_=package.compose(Path(__file__).resolve().parents[2],cls.source)

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.binding=fixture();self.binding.update(self.source);self.targets={};self.installs={};self.roots={}
        for i,node in enumerate(domains.topology.NODES,1):
            alias='gse-v52-'+str(i)*32;known=self.root/(node+'-known');known.write_text(alias+' ssh-ed25519 AAA'+str(i)+'\n');known.chmod(0o600)
            key=self.root/(node+'-key');key.write_text('fixture key');key.chmod(0o600)
            self.targets[node]=dict(host='127.0.0.1',port=30000+i,user='operator',alias=alias,key=str(key),knownHosts=str(known))
            self.binding[domains.FIELD]['nodes'][node]['sshHostPinSha256']=bound.digest(known.read_bytes())
            self.roots[node]='/guest/history/'+node
            self.installs[node]=dict(schema=python.RECEIPT,descriptorSha256=bound.digest(bound.encoded(self.descriptor)),
                filesSha256=bound.digest(bound.encoded(self.descriptor['files'])),root='/guest/python-'+self.descriptor['sha256'],
                host=dict(bootId=self.binding[domains.FIELD]['nodes'][node]['bootId'],uid=1000,parentDevice=1,parentInode=2))
        transport(self.binding)

    def placement(self):return bound.Placement(self.binding,self.targets,self.roots,self.installs,self.descriptor,self.payload)

    def test_all_exact_histories_use_existing_controllers_with_guest_roots_and_no_local_ports(self):
        for i,(name,spec) in enumerate(bound.installed.h.suite.load()['histories'].items()):
            placement=self.placement()
            own=placement.factory(name)(self.root/str(i),name,self.source);own.binding={}
            with patch.object(bound.installed.h.socket,'socket',side_effect=AssertionError('controller port reservation')):
                self.assertEqual(self.binding['remoteTopology'],own.topology_plan())
            self.assertEqual([],own.sockets);self.assertEqual(Path(self.roots['node-2']),own.receiver_root('node-2'))
            self.assertIsInstance(own,bound.installed.receiver_type(name))
            self.assertEqual(spec,own.spec)
            self.assertFalse(own.qualify_transport);self.assertFalse(own.allow_control_download)
            self.assertEqual(self.installs['node-2']['root'],own.python_context('node-2')['root'])

    def test_source_history_pin_installation_and_path_substitution_reject(self):
        for field,mutate,reason in (
            ('targets',lambda v:v['node-1'].update(port=4444),'pinned target changed'),
            ('roots',lambda v:v.update({'node-2':'/guest/other'}),'receiver root'),
            ('installs',lambda v:v['node-1']['host'].update(uid=1001),'bound guest host changed'),
            ('binding',lambda v:v.update(source='c'*40),'source binding')):
            saved=deepcopy(getattr(self,field));mutate(getattr(self,field))
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):self.placement()
            setattr(self,field,saved)
        factory=self.placement().factory('m03-p4')
        with self.assertRaisesRegex(ValueError,'source/history changed'):factory(self.root/'wrong','m03-p65',self.source)
        with self.assertRaisesRegex(ValueError,'source/history changed'):factory(self.root/'wrong','m03-p4',dict(self.source,source='f'*40))
        with self.assertRaisesRegex(ValueError,'source/history changed'):factory(self.root/'wrong','m03-p4',{})

    def test_mutating_caller_inputs_does_not_retarget_an_existing_placement(self):
        placement=self.placement();self.roots['node-1']='/different/node-1';self.binding[domains.FIELD]['leaseSha256']='e'*64
        self.targets['node-1']['port']=4444;self.installs['node-1']['root']='/other'
        own=placement.factory('m03-p4')(self.root/'one','m03-p4',self.source);own.binding={};own.topology_plan()
        self.assertEqual('/guest/history/node-1',str(own.receiver_root('node-1')))
        self.assertEqual('d'*64,own.binding[domains.FIELD]['leaseSha256']);self.assertEqual(30001,own.targets['node-1']['port'])

    def test_original_guest_paths_cannot_be_consumed_by_a_second_history_or_retry(self):
        placement=self.placement();factory=placement.factory('m03-p4')
        with patch.object(bound.installed.FormalReceivers,'__init__',side_effect=OSError('original preparation failed')):
            with self.assertRaisesRegex(OSError,'original preparation failed'):factory(self.root/'first','m03-p4',self.source)
        for name in ('m03-p4','m03-p65'):
            with self.assertRaisesRegex(ValueError,'already consumed'):
                placement.factory(name)(self.root/name,name,self.source)
            self.assertFalse((self.root/name).exists())

    def test_key_file_substitution_is_rechecked_before_any_receiver_preparation(self):
        placement=self.placement();own=placement.factory('m03-p4')(self.root/'one','m03-p4',self.source);own.binding={}
        path=Path(self.targets['node-1']['knownHosts']);path.write_text(path.read_text().replace('AAA1','BBBB'))
        with self.assertRaisesRegex(ValueError,'pinned target changed'):own.topology_plan()
        self.assertEqual({},own.binding);self.assertEqual({},own.roots)

    def test_delivery_checks_captured_endpoint_pin_before_the_first_exchange(self):
        from unittest.mock import Mock
        endpoint=Mock(pins={'knownHosts':b'substituted'})
        meta=dict(source=self.source,topology=self.binding['remoteTopology'],hostDomains=self.binding[domains.FIELD])
        with patch.object(delivery_client,'Endpoint',return_value=endpoint):
            with self.assertRaisesRegex(ValueError,'bound delivery SSH pin changed'):
                delivery_client.Delivery({},'/guest','node-1',meta,python_context={'selected':'fixture'})
        endpoint.close.assert_called_once();endpoint.exchange.assert_not_called()


if __name__=='__main__':unittest.main()
