import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from . import cloud_access as access, cloud_authority as a, cloud_provider as p, cloud_control as c, cloud_identity as identity
from .cloud_provider_offline import Server
from .test_cloud_authority import fixture, completion
from .test_cloud_provider import configuration
from .evidence import digest, encoded


def public_key(byte=1):
    return 'ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes([byte])*32).decode()


def bound_request(attempt='b'*32, member='experiment'):
    req=fixture(member,attempt);req['configurationSha256']=p.config(configuration())
    return a.with_access(req,access.descriptor(attempt,public_key()))


class AccessTest(unittest.TestCase):
    def test_access_extends_request_without_changing_shared_cohort_identity(self):
        req=fixture();value=access.descriptor(req['selection']['attempt'],public_key());bound=a.with_access(req,value)
        self.assertEqual(a.identity(req),a.identity(bound))
        self.assertNotEqual(a.validate_request(req,domain='offline'),a.validate_request(bound,domain='offline'))
        self.assertEqual('gse-v52-owned-request-v1',req['schema']);self.assertNotIn('guestAccess',req)
        value['publicKey']=public_key(2);self.assertEqual(public_key(),bound['guestAccess']['publicKey'])
        with self.assertRaisesRegex(ValueError,'already bound'):a.with_access(bound,value)

    def test_native_access_is_only_data_and_cannot_enter_offline_provider(self):
        req=fixture(domain='native');bound=a.with_access(req,access.descriptor(req['selection']['attempt'],public_key()))
        a.validate_request(bound,domain='native')
        with self.assertRaisesRegex(ValueError,'domain'):p.context(configuration(),bound)

    def test_access_is_per_attempt_in_same_sequence_not_shared_public_key(self):
        ledger=a.empty_ledger(domain='offline')
        for n,name in enumerate(a.suite.MEMBERS):
            req=bound_request(f'{n+1:032x}',name);req['guestAccess']['publicKey']=public_key(n+1)
            ledger=a.reserve(ledger,req,previous_cost=n,cost=1);ledger=a.finish(ledger,req,completion(req))
        self.assertEqual(list(a.suite.MEMBERS),a.inspect_ledger(ledger,domain='offline')['sequences']['c'*32]['passed'])

    def test_unknown_access_fields_wrong_attempt_user_and_key_reject(self):
        value=access.descriptor('b'*32,public_key())
        for mutate in (lambda v:v.update(extra=True),lambda v:v.update(schema='gse-v51-guest-access-v1'),
                       lambda v:v.update(attempt='c'*32),lambda v:v.update(user='root'),
                       lambda v:v.update(publicKey=public_key()+' comment'),lambda v:v.update(publicKey='ssh-ed25519 AAAA')):
            changed=deepcopy(value);mutate(changed)
            with self.assertRaises(ValueError):a.with_access(fixture(),changed)
        req=bound_request();req.pop('guestAccess')
        with self.assertRaisesRegex(ValueError,'fields'):a.validate_request(req,domain='offline')

    def test_key_generation_pin_and_private_public_match_without_leak(self):
        with tempfile.TemporaryDirectory(prefix='v52-access-') as temp:
            root=Path(temp);value=access.generate(root/'keys','b'*32)
            access.validate(value);access.check_private_key(root/'keys/identity',value)
            self.assertEqual(value,json.loads((root/'keys/v52-access.json').read_text()))
            self.assertNotIn('PRIVATE',(root/'keys/v52-access.json').read_text())
            name=access.alias('a'*64,'node-1','123');record=access.pin(root/'host-key',name,public_key(2))
            self.assertEqual((name+' '+public_key(2)+'\n').encode(),(root/'host-key').read_bytes())
            self.assertEqual(0,(root/'host-key').stat().st_mode&0o077)
            self.assertEqual(digest((root/'host-key').read_bytes()),record['sha256'])
            with self.assertRaises(FileExistsError):access.pin(root/'host-key',name,public_key(3))
            wrong=deepcopy(value);wrong['publicKey']=public_key(3)
            with self.assertRaises(ValueError):access.check_private_key(root/'keys/identity',wrong)
            (root/'keys/identity').chmod(0o644)
            with self.assertRaises(ValueError):access.check_private_key(root/'keys/identity',value)

    def test_host_pin_alias_changes_with_original_resource_identity(self):
        values=[access.alias('a'*64,'node-1','1'),access.alias('b'*64,'node-1','1'),
                access.alias('a'*64,'node-2','1'),access.alias('a'*64,'node-1','2')]
        self.assertEqual(4,len(set(values)));self.assertTrue(all(len(x)==40 for x in values))

    def test_foreign_or_malformed_host_key_rows_are_fatal_not_pending(self):
        for row in (dict(namespace='other',key='ssh-ed25519',value=public_key().split()[1]),
                    dict(namespace='hostkeys',key=12,value='x'),dict(namespace='hostkeys',key='ssh-rsa')):
            with self.assertRaisesRegex(ValueError,'entry scope/shape'):
                access.host_key(dict(queryPath='hostkeys/',queryValue=dict(items=[row])))


class ObservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req=bound_request();cfg=configuration();server=Server(cfg);api=p.OfflineApi(server);store=p.Store(cfg,api)
        provider=p.Provider(store,cls.req,wall=lambda:1000,sleep=server.sleep)
        owner=c.OfflineOwner(store,provider,cls.req,wall=lambda:1000);owner.prepare(previous_cost=0,cost=1)
        cls.claim=owner.resource_claim();cls.original=(deepcopy(server.objects),deepcopy(server.resources),deepcopy(server.operations),server.serial)

    def setUp(self):
        self.server=Server(configuration());self.server.objects,self.server.resources,self.server.operations,self.server.serial=deepcopy(self.original)
        self.api=p.OfflineApi(self.server);self.store=p.Store(configuration(),self.api)
        self.now=1000;self.provider=p.Provider(self.store,self.req,wall=lambda:self.now,sleep=self.server.sleep)
        self.expected=deepcopy(self.claim)
        for node in ('node-1','node-2','node-3'):
            vm=next(r for r in self.expected['nodes'][node]['identity']['resources'] if r['spec']['kind']=='instance')
            self.server.host_keys[vm['spec']['name']]=dict(queryPath='hostkeys/',queryValue=dict(items=[
                dict(namespace='hostkeys',key='ssh-ed25519',value=public_key(int(node[-1])+3).split()[1])]))
        self.vmrow=next(r for r in self.expected['nodes']['node-1']['identity']['resources'] if r['spec']['kind']=='instance')
        self.vmkey=next(k for k in self.server.resources if k[2]==self.vmrow['spec']['name'])
        self.vm=self.server.resources[self.vmkey]

    def observe(self,node='node-1',deadline=None):
        return identity.observe(self.provider,self.expected,node,deadline=self.api.clock()+30 if deadline is None else deadline)

    def test_every_node_observation_brackets_key_with_six_exact_resource_reads(self):
        for node in ('node-1','node-2','node-3'):
            start=len(self.server.events);result=self.observe(node)
            self.assertEqual(node,result['node']);self.assertFalse(result['guestObserved']);self.assertFalse(result['paidCloud'])
            self.assertEqual(digest(encoded(self.expected)),result['resourceClaimSha256'])
            self.assertEqual(self.expected['nodes'][node]['resourceIdentitySha256'],result['resourceIdentitySha256'])
            self.assertEqual(digest(encoded(self.req['guestAccess'])),result['guestAccessSha256'])
            self.assertEqual(digest((result['alias']+' '+result['hostKey']+'\n').encode()),result['sshHostPinSha256'])
            events=[e for e in self.server.events[start:] if 'compute.googleapis.com' in e['url']]
            self.assertEqual(7,len(events));self.assertIn('/getGuestAttributes?queryPath=hostkeys%2F',events[3]['url'])
            self.assertTrue(all(e['method']=='GET' for e in events))
            self.assertEqual([e['url'] for e in events[:3]],[e['url'] for e in events[4:]])
            self.assertTrue(all(e['url'].rsplit('/',1)[1].isdigit() for e in events[:3]))

    def test_instance_creation_metadata_is_bound_to_request_public_key(self):
        self.assertEqual(access.metadata(self.req['guestAccess']),self.vm['metadata']['items'])
        self.assertFalse(self.vm['networkInterfaces'][0]['accessConfigs'])
        changed=deepcopy(self.vm);changed['metadata']['items'][-1]['value']='root:'+public_key()
        with self.assertRaisesRegex(ValueError,'metadata'):self.provider.inspect(self.vmrow['spec'],changed)

    def test_provider_identity_is_stable_across_lease_renewal(self):
        before=self.observe();version,lease=self.store.get(a.LEASE)
        self.now=1050;control=a.renew(lease,1050);c.put(self.store,a.LEASE,control,version)
        self.assertEqual(before,self.observe())

    def test_expired_cleaning_missing_and_replaced_lease_reject_before_compute(self):
        version,original=self.store.get(a.LEASE)
        for phase in ('CLEANING','ACQUIRING'):
            changed=deepcopy(original);changed['phase']=phase
            # ACQUIRING with attempted resources also fails the authority parser.
            self.server.objects[a.LEASE]=(version,encoded(changed),'application/json')
            with self.assertRaises(ValueError):self.observe()
        self.server.objects[a.LEASE]=(version,encoded(original),'application/json');self.now=1060
        with self.assertRaisesRegex(ValueError,'inactive'):self.observe()
        self.server.objects.pop(a.LEASE)
        with self.assertRaisesRegex(ValueError,'absent'):self.observe()
        self.assertFalse(any('compute.googleapis.com' in e['url'] for e in self.server.events))

    def test_changed_claim_or_pending_charge_reject(self):
        self.expected['nodes']['node-1']['resourceIdentitySha256']='0'*64
        with self.assertRaisesRegex(ValueError,'allocation changed'):self.observe()
        self.expected=deepcopy(self.claim);version,ledger=self.store.get(a.LEDGER)
        c.put(self.store,a.LEDGER,a.finish(ledger,self.req,completion(self.req,'FAIL')),version)
        with self.assertRaisesRegex(ValueError,'charge changed'):self.observe()

    def test_numeric_resource_replacement_rejects(self):
        self.vm['id']='999'
        with self.assertRaises(p.ApiError) as error:self.observe()
        self.assertEqual(404,error.exception.status)
        self.assertFalse(any('/getGuestAttributes' in e['url'] for e in self.server.events))

    def test_same_numeric_path_returning_wrong_id_rejects(self):
        def fault(stage,event):
            if stage=='before' and event['url'].endswith('/instances/'+self.vm['id']):return 200,encoded(dict(self.vm,id='999'))
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'resource ID changed'):self.observe()

    def test_bidirectional_disk_attachments_ready_status_and_private_address(self):
        disk_key=next(k for k in self.server.resources if k[1]=='disks' and k[2].endswith('n1-data'))
        disk=self.server.resources[disk_key]
        for field,value in (('users',[]),('users',['https://compute.googleapis.com/compute/v1/projects/foreign/zones/x/instances/y']),('status','CREATING')):
            original=disk[field];disk[field]=value
            with self.assertRaisesRegex(ValueError,'attachment/status'):self.observe()
            disk[field]=original
        for address in ('8.8.8.8','127.0.0.1','169.254.169.254','::1','10.1.2.3 '):
            self.vm['networkInterfaces'][0]['networkIP']=address
            with self.assertRaises(ValueError):self.observe()
        self.vm['networkInterfaces'][0]['networkIP']='10.1.2.3';self.vm['status']='TERMINATED'
        with self.assertRaisesRegex(ValueError,'RUNNING'):self.observe()

    def test_resource_change_during_host_key_query_is_fatal(self):
        def fault(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:self.vm['networkInterfaces'][0]['networkIP']='10.2.3.4'
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'observation changed'):self.observe()

    def test_attachment_change_during_host_key_query_is_fatal(self):
        def fault(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:
                disk=next(v for k,v in self.server.resources.items() if k[1]=='disks' and k[2].endswith('n1-boot'));disk['users']=[]
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'attachment/status'):self.observe()

    def test_missing_key_is_pending_only_after_second_complete_sample(self):
        self.server.host_keys.clear()
        with self.assertRaises(access.HostKeyPending):self.observe()
        self.assertEqual(7,len([e for e in self.server.events if 'compute.googleapis.com' in e['url']]))
        self.server.events.clear();self.server.host_keys[self.vm['name']]=dict(queryPath='hostkeys/',queryValue=dict(items=[]))
        with self.assertRaises(access.HostKeyPending):self.observe()
        self.assertEqual(7,len([e for e in self.server.events if 'compute.googleapis.com' in e['url']]))

    def test_missing_key_plus_resource_disappearance_is_not_retryable_pending(self):
        self.server.host_keys.clear()
        def fault(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:self.server.resources.pop(self.vmkey)
        self.server.fault=fault
        with self.assertRaises(p.ApiError):self.observe()

    def test_denied_or_malformed_key_is_not_readiness_retry(self):
        self.server.fault=lambda stage,event:(403,b'private-detail') if stage=='before' and '/getGuestAttributes' in event['url'] else None
        with self.assertRaises(p.ApiError) as error:self.observe()
        self.assertEqual(403,error.exception.status);self.assertNotIn('private-detail',str(error.exception))
        self.server.fault=lambda *args:None
        value=self.server.host_keys[self.vm['name']];value['queryValue']['items']*=2
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.observe()
        value['queryValue']['items']=[];value['queryPath']='foreign/'
        with self.assertRaisesRegex(ValueError,'query scope'):self.observe()
        value['queryPath']='hostkeys/';value['queryValue']['items']=[dict(namespace='hostkeys',key='ssh-ed25519',value='AAAA')]
        with self.assertRaisesRegex(ValueError,'Ed25519'):self.observe()

    def test_lease_expiry_or_fencing_during_query_rejects(self):
        def fault(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:self.now=1060
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'inactive'):self.observe()
        self.now=1000
        def fence(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:
                version,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';c.put(self.store,a.LEASE,lease,version)
        self.server.fault=fence
        with self.assertRaisesRegex(ValueError,'inactive'):self.observe()

    def test_original_deadline_bounds_reads_without_restart(self):
        def fault(stage,event):
            if stage=='after' and '/getGuestAttributes' in event['url']:self.server.seconds+=31
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'late response'):self.observe()
        self.assertEqual(1,len([e for e in self.server.events if '/getGuestAttributes' in e['url']]))
        for deadline in (True,float('inf'),self.api.clock(),self.api.clock()+301):
            with self.assertRaises(ValueError):self.observe(deadline=deadline)

    def test_v1_keyless_request_cannot_observe_guest(self):
        req=fixture();req['configurationSha256']=p.config(configuration())
        provider=p.Provider(self.store,req,wall=lambda:1000)
        with self.assertRaisesRegex(ValueError,'bound guest access'):identity.observe(provider,self.expected,'node-1',deadline=self.api.clock()+30)
        self.assertEqual([],self.server.events)

    def test_group_observations_build_exact_private_topology(self):
        result=identity.observe_group(self.provider,self.expected,'12345678-1234-1234-1234-123456789abc',deadline=self.api.clock()+100)
        self.assertEqual(3,len(result['topology']['members']));self.assertFalse(result['guestObserved'])
        self.assertEqual('owned-private-hosts',result['topology']['placement'])
        self.assertEqual([19752]*3,[v['port'] for v in result['topology']['members']])
        for row in result['topology']['members']:
            self.assertEqual(result['nodes'][row['node']]['facts']['privateAddress'],row['host'])

    def test_group_duplicate_addresses_and_public_keys_reject(self):
        vms=[v for k,v in self.server.resources.items() if k[1]=='instances']
        original=vms[1]['networkInterfaces'][0]['networkIP']
        vms[1]['networkInterfaces'][0]['networkIP']=vms[0]['networkInterfaces'][0]['networkIP']
        with self.assertRaisesRegex(ValueError,'independent provider guests'):
            identity.observe_group(self.provider,self.expected,'12345678-1234-1234-1234-123456789abc',deadline=self.api.clock()+100)
        vms[1]['networkInterfaces'][0]['networkIP']=original
        self.server.host_keys[vms[1]['name']]=deepcopy(self.server.host_keys[vms[0]['name']])
        with self.assertRaisesRegex(ValueError,'independent provider guests'):
            identity.observe_group(self.provider,self.expected,'12345678-1234-1234-1234-123456789abc',deadline=self.api.clock()+100)

    def test_host_key_response_bounds_and_noncanonical_encoding(self):
        for response in ([],dict(queryPath='hostkeys/',queryValue=[]),
            dict(queryPath='hostkeys/',queryValue=dict(items=[None])),
            dict(queryPath='hostkeys/',queryValue=dict(items=[{}]*11))):
            with self.assertRaises(ValueError):access.host_key(response)
        with self.assertRaises(ValueError):access.ed25519(public_key()+'=')


if __name__=='__main__':unittest.main()
