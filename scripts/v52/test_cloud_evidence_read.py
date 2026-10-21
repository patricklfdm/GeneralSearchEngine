"""Original-object decoder tests on synthetic HTTP, never GCP qualification."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_evidence_read as r,cloud_prepared as prepared
from .cloud_provider_offline import Server
from .test_cloud_prepared import arguments
from .test_cloud_authority import completion


class ReadTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        args=arguments();self.source=args['proof']['source']
        self.cfg=dict(schema='gse-v52-preflight-config-v1',provider=args['configuration'],projectNumber=args['project_number'],
            layout=args['resource_layout'],policy=args['ownership_policy'])
        self.server=Server(self.cfg['provider']);self.ledger=r.a.empty_ledger(domain='native');self.chosen={};self.requests={};self.files={}
        for i,name in enumerate(r.suite.MEMBERS,1):
            req=prepared.prepare(**arguments(member=name,attempt=f'{i:032x}'))['request'];self.requests[name]=req
            sha=r.a.validate_request(req,domain='native');self.chosen[name]=sha
            source=self.root/name;source.mkdir();paths={}
            for file in ('authority.json','history.tar.gz'):
                path=source/file;path.write_bytes((name+' modeled '+file).encode());paths[file]=path
            self.files[name]=paths;manifest=r.parts.scan(paths,req);clean=dict(status='PASS',checks=[],errors=[],leftovers=[])
            completed=completion(req);completed.update(evidenceSha256=r.digest(r.encoded(manifest)),cleanupSha256=r.digest(r.encoded(clean)))
            prefix=r.control.attempt_key(req)
            self.seed(r.p.context_key(req),r.p.context(self.cfg['provider'],req,domain='native'))
            self.seed(prefix+'completion.json',completed);self.seed(r.control.cleanup_key(req,completed['cleanupSha256']),clean)
            self.seed(r.retention.prefix(req)+'manifest.json',manifest)
            for ordinal,body in r.parts.chunks(paths,manifest):self.seed(r.retention.chunk_key(req,ordinal),body)
            self.ledger=r.a.finish(r.a.reserve(self.ledger,req,previous_cost=(i-1)*4_000_000,cost=4_000_000),req,completed)
        self.seed(r.a.LEDGER,self.ledger)
        self.reader=r.OfflineObjects(self.cfg,self.source,self.server,self.root/'reads');self.addCleanup(self.reader.close)
        self.network=patch.object(r.h.Network,'send',side_effect=AssertionError('network forbidden'));self.network.start();self.addCleanup(self.network.stop)
    def seed(self,key,value):
        self.server.serial+=1;self.server.objects[key]=(self.server.serial,r.encoded(value),'application/json')
    def run_restore(self):return r.restore(self.reader,dict(reversed(list(self.chosen.items()))),self.root/'restored')

    def test_exact_selected_bytes_restored_with_only_pinned_gets_and_no_listing(self):
        result=self.run_restore();self.assertEqual('ORIGINALS_RESTORED_NOT_QUALIFIED',result['receipt']['status'])
        self.assertEqual('offline-v52-evidence-reads',result['receipt']['execution']);self.assertFalse(result['receipt']['fullRemoteQualification'])
        self.assertEqual(self.ledger,result['ledger']);self.assertEqual(5,len(result['inputs']))
        for value in result['inputs']:
            name=value['request']['selection']['member']['name']
            for file,path in self.files[name].items():self.assertEqual(path.read_bytes(),(Path(value['root'])/file).read_bytes())
        self.assertTrue(all(row['method']=='GET' and row['body'] is None for row in self.server.events))
        media=[row['url'] for row in self.server.events if '?alt=media' in row['url']]
        self.assertTrue(media);self.assertTrue(all('&generation=' in u and '&ifGenerationMatch=' in u for u in media))

    def test_unknown_object_foreign_bucket_mutations_and_unobserved_generation_reject_before_io(self):
        key=r.control.attempt_key(self.requests['experiment'])+'completion.json';endpoint=self.reader.endpoint(key)
        before=len(self.server.events)
        for method,url in (('GET',endpoint),('GET',self.reader.base),('POST',self.reader.endpoint(r.a.LEDGER)),
                           ('GET',r.p.query(self.reader.endpoint(r.a.LEDGER),alt='media',generation='1',ifGenerationMatch='1'))):
            with self.assertRaisesRegex(ValueError,'outside selected'):self.reader.api.call(method,url,deadline=self.server.clock()+30)
        self.assertEqual(before,len(self.server.events))

    def test_partial_or_wrong_source_selection_rejects_before_evidence_reads(self):
        self.chosen.pop('experiment')
        with self.assertRaisesRegex(ValueError,'five-member'):self.run_restore()
        self.assertEqual([],self.server.events)
        self.chosen['experiment']=r.a.validate_request(self.requests['experiment'],domain='native');self.reader.source['source']='f'*40
        with self.assertRaisesRegex(ValueError,'source/configuration'):self.run_restore()
        self.assertTrue(all(r.p.url.unquote(e['url']).split('?')[0].endswith(r.a.LEDGER) for e in self.server.events))

    def test_changed_metadata_truncation_oversize_and_generation_reject(self):
        for problem in ('identity','oversize','truncated','generation'):
            def fault(stage,row):
                if stage!='after' or r.a.LEDGER not in r.p.url.unquote(row['url']):return None
                if '?alt=media' in row['url']:
                    if problem=='truncated':return 200,b'{}'
                    if problem=='generation':self.seed(r.a.LEDGER,self.ledger)
                elif problem in ('identity','oversize'):
                    value=self.server.metadata(r.a.LEDGER,self.server.objects[r.a.LEDGER])
                    value.update({'name':'foreign'} if problem=='identity' else {'size':str(r.p.MAX_OBJECT+1)})
                    return 200,r.encoded(value)
            self.server.fault=fault
            with self.subTest(problem=problem),self.assertRaises(ValueError):self.reader.get(r.a.LEDGER)
        self.assertEqual([],self.reader.receipts)

    def test_changed_terminal_or_manifest_hash_cannot_be_a_success(self):
        for key in (r.control.attempt_key(self.requests['canonical-3'])+'completion.json',r.retention.prefix(self.requests['canonical-3'])+'manifest.json'):
            original=self.server.objects[key];value=r.strict(original[1])
            if key.endswith('completion.json'):value['evidenceSha256']='f'*64
            else:value['files'][0]['sha256']='f'*64
            self.seed(key,value)
            with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValueError,'original (terminal|manifest) hash'):
                r.restore(self.reader,dict(reversed(list(self.chosen.items()))),Path(directory)/'restore')
            self.server.objects[key]=original

    def test_missing_original_part_stops_without_retry_or_fallback(self):
        key=r.retention.chunk_key(self.requests['canonical-3'],0);del self.server.objects[key]
        with self.assertRaises(r.h.ApiError):self.run_restore()
        queried=[e for e in self.server.events if r.p.url.unquote(e['url']).endswith(key)]
        self.assertEqual(1,len(queried));receipt=r.artifacts.read(self.root/'restored/receipt.json')
        self.assertEqual('FAIL',receipt['status']);self.assertEqual([],receipt['restoredMembers'])

    def test_transient_original_part_read_recovers_without_changing_generation(self):
        failed=[]
        def fault(stage,row):
            if stage=='before' and 'chunk-' in row['url'] and '?alt=media' in row['url'] and not failed:
                failed.append(row['url']);raise ConnectionError('lost response')
        self.server.fault=fault
        result=self.run_restore()
        self.assertEqual('ORIGINALS_RESTORED_NOT_QUALIFIED',result['receipt']['status']);self.assertEqual(1,len(failed))
        self.assertEqual(2,sum(row['url']==failed[0] for row in self.server.events))
        self.assertTrue(all(row['method']=='GET' for row in self.server.events))

    def test_persistent_read_failure_is_retained_and_not_retried_by_restore(self):
        def fault(stage,row):
            if stage=='before':raise ConnectionError('private')
        self.server.fault=fault
        with self.assertRaises(r.cloud_read_retry.ReadError):self.run_restore()
        receipt=r.artifacts.read(self.root/'restored/receipt.json')
        self.assertEqual(3,len(self.server.events));self.assertEqual([],receipt['restoredMembers'])
        self.assertEqual(3,receipt['failure']['readRetry']['attempts'])

    def test_altered_part_never_finishes_restoration(self):
        key=r.retention.chunk_key(self.requests['canonical-3'],0);value=r.strict(self.server.objects[key][1]);value['data']='A'*len(value['data']);self.seed(key,value)
        with self.assertRaisesRegex(ValueError,'chunk bytes'):self.run_restore()
        self.assertEqual('FAIL',r.artifacts.read(self.root/'restored/receipt.json')['status'])

    def test_later_failed_attempt_is_preserved_but_rewritten_ledger_is_rejected(self):
        req=prepared.prepare(**dict(arguments(member='experiment',attempt='f'*32),sequence='d'*32))['request']
        later=r.a.finish(r.a.reserve(self.ledger,req,previous_cost=20_000_000,cost=1),req,completion(req,'FAIL'))
        original=self.server.objects[r.a.LEDGER];last=r.retention.chunk_key(self.requests['experiment'],1)
        def append(stage,row):
            if stage=='after' and r.p.url.unquote(row['url']).endswith(last):self.seed(r.a.LEDGER,later)
        self.server.fault=append;result=self.run_restore();self.assertEqual(later,result['ledger'])
        self.server.objects[r.a.LEDGER]=original;changed=deepcopy(self.ledger);changed['entries'][0]['reservedCostMicrousd']+=1
        def rewrite(stage,row):
            if stage=='after' and r.p.url.unquote(row['url']).endswith(last):self.seed(r.a.LEDGER,changed)
        self.server.fault=rewrite
        with self.assertRaisesRegex(ValueError,'ledger history changed'):r.restore(self.reader,self.chosen,self.root/'rewrite')


if __name__=='__main__':unittest.main()
