import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from . import guest_setup as s, cloud_gcp as g, cloud_http_fake as f, cloud_authority as a, performance_model as m
from .cloud_http import Api

KEY='ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(range(32))).decode()


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_fresh_key_permissions_and_no_reuse(self):
        value=s.generate(self.root/'private','a'*32);s.access(value)
        self.assertEqual((self.root/'private/identity').stat().st_mode&0o077,0)
        self.assertNotIn('PRIVATE',str(value))
        with self.assertRaises(FileExistsError):s.generate(self.root/'private','a'*32)
    def test_key_encoding_user_and_attempt_injection_rejected(self):
        good=dict(attempt='a'*32,user='gse-'+'a'*24,publicKey=KEY);s.access(good)
        for key,value in [('user','root'),('attempt','../bad'),('publicKey','ssh-ed25519 AQID'),('publicKey',KEY+'\ninjected')]:
            with self.subTest(key=key),self.assertRaises(ValueError):s.access(dict(good,**{key:value}))
    def test_host_key_pinning_is_exact_and_non_overwriting(self):
        response=dict(queryPath='hostkeys/',queryValue=dict(items=[dict(namespace='hostkeys',key='ssh-ed25519',value=KEY.split()[1])]))
        self.assertEqual(s.host_key(response),KEY);s.pin(self.root/'known','123',KEY)
        self.assertEqual((self.root/'known').read_text(),'gse-v51-123 '+KEY+'\n')
        with self.assertRaises(FileExistsError):s.pin(self.root/'known','456',KEY)
        response['queryValue']['items']*=2
        with self.assertRaises(ValueError):s.host_key(response)
    def provider(self):
        req,_,_,clock,http,store,old=f.fixture();cfg=deepcopy(old.config)
        access=dict(attempt=req['attempt'],user='gse-'+req['attempt'][:24],publicKey=KEY)
        req.update(schema='gse-v51-cloud-request-v2',guestAccessSha256=m.sha(m.canonical(access)))
        provider=g.Compute(cfg,req,old.api,guest_access=access)
        spec=next(r for r in a.resources(req) if r['kind']=='instance');value=provider.body(spec);value['id']='123'
        return provider,spec,value,http
    def test_access_bound_to_request_and_inspected_metadata(self):
        provider,spec,value,_=self.provider();provider.inspect(spec,value)
        value['metadata']['items'][-1]['value']='foreign:'+KEY
        with self.assertRaisesRegex(ValueError,'metadata'):provider.inspect(spec,value)
        access=dict(provider.guest_access,attempt='f'*32,user='gse-'+'f'*24)
        with self.assertRaisesRegex(ValueError,'attempt'):g.Compute(provider.config,provider.req,provider.api,guest_access=access)
    def test_attempt_keys_rotate_without_changing_sequence_configuration(self):
        provider,_,_,_=self.provider();first=provider.req;ledger=a.empty_ledger()
        for ordinal,member in enumerate(a.ORDERS[first['order']]):
            attempt=f'{ordinal+1:032x}'
            access=dict(attempt=attempt,user='gse-'+attempt[:24],publicKey=KEY)
            req=a.request(first['source'],first['bundleSha256'],first['configurationSha256'],first['sequence'],attempt,member,
                now=first['createdAt']+ordinal,guest_access_sha256=m.sha(m.canonical(access)))
            g.Compute(provider.config,req,provider.api,guest_access=access)
            ledger['entries'].append(dict(kind='RESERVED',requestSha256=a.validate_request(req),request=req,maximumCostMicrousd=1))
            ledger['entries'].append(dict(kind='FINISHED',requestSha256=a.validate_request(req),status='PASS',completionSha256='a'*64))
        total,attempts=a.inspect_ledger(ledger);self.assertEqual((total,len(attempts)),(5,5))
        changed=deepcopy(ledger);changed['entries'][2]['request']['configurationSha256']='0'*64
        changed['entries'][2]['requestSha256']=a.validate_request(changed['entries'][2]['request'])
        with self.assertRaisesRegex(ValueError,'sequence changed'):a.inspect_ledger(changed)
    def test_unbound_missing_or_changed_access_rejected(self):
        provider,_,_,_=self.provider();req=deepcopy(provider.req)
        with self.assertRaises(ValueError):g.Compute(provider.config,req,provider.api)
        with self.assertRaises(ValueError):g.Compute(provider.config,dict(req,guestAccessSha256='0'*64),provider.api,guest_access=provider.guest_access)
        req.pop('guestAccessSha256');req['schema']='gse-v51-cloud-request-v1'
        with self.assertRaisesRegex(ValueError,'bound request'):g.Compute(provider.config,req,provider.api,guest_access=provider.guest_access)
    def test_authenticated_host_query_bracketed_by_exact_id(self):
        provider,spec,value,http=self.provider();calls=[]
        def respond(method,path,query,body):
            calls.append(path.path)
            if path.path.endswith('/getGuestAttributes'):
                return http.reply(dict(queryPath='hostkeys/',queryValue=dict(items=[dict(namespace='hostkeys',key='ssh-ed25519',value=KEY.split()[1])])))
            return http.reply(value)
        http.hook=respond
        self.assertEqual(provider.guest_host_key(spec,'123'),dict(instanceId='123',publicKey=KEY))
        self.assertTrue(calls[0].endswith('/123') and calls[-1].endswith('/123'));self.assertEqual(len(calls),3)
        calls.clear()
        def replaced(method,path,query,body):
            result=respond(method,path,query,body)
            if len(calls)==3:return http.reply(dict(value,id='124'))
            return result
        http.hook=replaced
        with self.assertRaisesRegex(ValueError,'changed'):provider.guest_host_key(spec,'123')
    def test_blank_disk_plan_rejects_boot_foreign_used_partitioned_readonly_or_wrong_size(self):
        provider=dict(instanceId='123',diskId='456',node=1,sizeGiB=100,attempt='a'*32);user='gse-'+'a'*24
        observed=dict(instanceId='123',device='/dev/disk/by-id/google-gse-data-1',resolved='/dev/sdb',type='disk',sizeBytes=100*(1<<30),readOnly=False,mounted=False,signatures=[],children=[],bootDevice='/dev/sda',targetEmpty=True)
        plan=s.volume_plan(provider,observed,user);self.assertFalse(plan['paidCloud']);self.assertNotIn('-F',plan['commands'][0])
        for key,value in [('instanceId','124'),('device','/dev/sda'),('resolved','/dev/sda'),('sizeBytes',1),('mounted',True),('readOnly',True),('signatures',['ext4']),('children',['sdb1']),('targetEmpty',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):s.volume_plan(provider,dict(observed,**{key:value}),user)

if __name__=='__main__':unittest.main()
