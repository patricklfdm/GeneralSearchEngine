"""Partition/provenance/budget negatives. Synthetic fixtures are not qualification."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_rich_evidence as evidence, remote_rich_shards as shards
from . import remote_schedule, remote_collection as collection, performance_model as m
from .remote_rich_plan import CELLS, MODES, SHARDS


class PartitionTest(unittest.TestCase):
    def test_exact_whole_cell_partition_preserves_all_frozen_windows(self):
        self.assertEqual(CELLS,tuple(c for rows in SHARDS.values() for c in rows))
        self.assertEqual(len(CELLS),len(set(CELLS)))
        durations={name:sum(w['durationNanos']//10**9 for cell,_ in rows
                            for w in remote_schedule.windows(cell)) for name,rows in SHARDS.items()}
        self.assertEqual(dict(zip(SHARDS,(520,260,300))),durations)
        self.assertEqual(1080,sum(durations.values()))
        for cell,_ in CELLS:
            windows=remote_schedule.windows(cell)
            if cell=='healthy':
                self.assertEqual(['warmup','baseline-a','instrumented-a','instrumented-b','baseline-b'],[v['window'] for v in windows])

    def test_partial_receipt_cannot_satisfy_original_full_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rows=[]
            for cell,mode in SHARDS['published-controls']:
                (root/(cell+'-'+mode)).mkdir();rows.append(dict(cell=cell,mode=mode))
            evidence.coverage(root,dict(cells=rows),SHARDS['published-controls'])
            with self.assertRaisesRegex(ValueError,'incomplete'):evidence.coverage(root,dict(cells=rows),CELLS)
            for changed in (rows+rows[:1],rows[::-1],rows[:1]):
                with self.assertRaisesRegex(ValueError,'incomplete'):
                    evidence.coverage(root,dict(cells=changed),SHARDS['published-controls'])
            (root/('sustained-'+MODES[2])).mkdir()
            with self.assertRaisesRegex(ValueError,'unexpected'):
                evidence.coverage(root,dict(cells=rows),SHARDS['published-controls'])

    def test_partial_validation_cannot_claim_complete_or_cloud_pass(self):
        execution=dict(preset='canonical',cells=[])
        with patch.object(evidence,'header',return_value=(execution,None)),patch.object(evidence,'validate_rows',return_value=[]):
            result=evidence.validate_partial(Path('/unused'),'automatic-healthy')
            self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['fullRemoteQualification'])
            self.assertFalse(result['paidCloud'])
            execution['preset']='experiment'
            with self.assertRaisesRegex(ValueError,'canonical'):evidence.validate_partial(Path('/unused'),'automatic-healthy')
        with self.assertRaisesRegex(ValueError,'unknown'):evidence.validate_partial(Path('/unused'),'arbitrary')


class AggregateIdentityTest(unittest.TestCase):
    def setUp(self):
        self.roots={name:Path(name) for name in SHARDS}
        self.identity=dict(source='a'*40,sourceInventorySha256='b'*64,plans={'plan':'c'*64},seed={'backup':'d'*64},
                           adapters={'candidate':dict(artifacts={'jar':'e'*64},classes={'c':'f'*64},sources={'s':'a'*64})})
        def header(root,expected):
            return dict(preset='canonical',cells=[dict(cell=c,mode=mode) for c,mode in expected]),None
        self.header=patch.object(evidence,'header',side_effect=header);self.header.start();self.addCleanup(self.header.stop)
        self.common=patch.object(evidence,'common_identity',return_value=self.identity);self.common.start();self.addCleanup(self.common.stop)
        self.budgets=[]

    def rows(self,root,execution,location,budget):
        self.budgets.append(budget)
        from .remote_trace import Decoder
        Decoder(budget).row({'test':True},4)
        return [dict(status='PASS',**row) for row in execution['cells']]

    def test_complete_set_replays_original_order_with_one_trace_budget(self):
        with patch.object(evidence,'validate_rows',side_effect=self.rows):
            result=evidence.validate_group(dict(reversed(list(self.roots.items()))))
        self.assertEqual(CELLS,tuple((r['cell'],r['mode']) for r in result['cells']))
        self.assertEqual('PASS',result['status']);self.assertFalse(result['fullRemoteQualification'])
        self.assertEqual(1,len({id(v) for v in self.budgets}))

    def test_aggregate_does_not_reset_expanded_trace_budget_per_shard(self):
        with patch.object(evidence.contract,'load',return_value={'evidence':{'traceBytes':10}}),patch.object(evidence,'validate_rows',side_effect=self.rows):
            with self.assertRaisesRegex(ValueError,'expansion budget'):evidence.validate_group(self.roots)

    def test_missing_extra_or_renamed_shards_fail_before_replay(self):
        for roots in ({},dict(list(self.roots.items())[:2]),{**self.roots,'extra':Path('extra')}):
            with patch.object(evidence,'validate_rows') as replay:
                with self.assertRaisesRegex(ValueError,'missing or extra'):evidence.validate_group(roots)
                replay.assert_not_called()

    def test_mixed_source_plans_seed_jars_classes_and_adapter_sources_fail(self):
        edits=[lambda v:v.update(source='z'*40),lambda v:v.update(sourceInventorySha256='z'*64),
               lambda v:v['plans'].update(plan='z'*64),lambda v:v['seed'].update(backup='z'*64),
               lambda v:v['adapters']['candidate']['artifacts'].update(jar='z'*64),
               lambda v:v['adapters']['candidate']['classes'].update(c='z'*64),
               lambda v:v['adapters']['candidate']['sources'].update(s='z'*64)]
        for edit in edits:
            changed=copy.deepcopy(self.identity);edit(changed)
            with patch.object(evidence,'common_identity',side_effect=[self.identity,changed,self.identity]),patch.object(evidence,'validate_rows') as replay:
                with self.assertRaisesRegex(ValueError,'mixed rich shard'):evidence.validate_group(self.roots)
                replay.assert_not_called()

    def test_one_failed_physical_replay_cannot_produce_aggregate_pass(self):
        with patch.object(evidence,'validate_rows',side_effect=ValueError('original physical oracle rejected')):
            with self.assertRaisesRegex(ValueError,'physical oracle'):evidence.validate_group(self.roots)


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'handoff';self.folder.mkdir()
        self.source='a'*40;self.manifest='b'*64
        self.receipt=dict(schema=shards.SCHEMA,status='PARTIAL',kind='shard',shard='automatic-healthy',source=self.source,
                          buildManifestSha256=self.manifest,paidCloud=False,fullRemoteQualification=False,
                          seedBindingSha256='c'*64,bindingSha256='d'*64,identity={'seed':'same'},collection={})
        self.save()

    def save(self):shards.save(self.folder/'receipt.json',self.receipt)

    def test_missing_failed_cancelled_full_pass_wrong_scope_and_stale_receipts_fail(self):
        original=copy.deepcopy(self.receipt)
        edits=[('status','FAIL'),('status','CANCELLED'),('status','PASS'),('kind','aggregate'),
               ('shard','published-controls'),('source','f'*40),('buildManifestSha256','f'*64),
               ('paidCloud',True),('fullRemoteQualification',True)]
        for field,value in edits:
            self.receipt=copy.deepcopy(original);self.receipt[field]=value;self.save()
            with patch.object(collection,'unpack') as unpack:
                with self.assertRaisesRegex(ValueError,'handoff'):
                    shards.unpack_input(self.folder,self.root/'out','shard','automatic-healthy',self.source,self.manifest)
                unpack.assert_not_called()
        (self.folder/'receipt.json').unlink()
        with self.assertRaisesRegex(ValueError,'metadata'):shards.unpack_input(self.folder,self.root/'out','shard','automatic-healthy',self.source,self.manifest)

    def test_real_portable_parts_require_matching_binding_and_preserved_identity(self):
        raw=self.root/'raw';raw.mkdir();shards.save(raw/'execution.json',{'state':'synthetic'})
        shards.save(raw/'provenance.json',{'test':True})
        digest=shards.binding(raw);collection.pack(raw,self.folder/'parts',digest)
        target=self.root/'inspect';info=collection.unpack(self.folder/'parts',target,digest)
        self.receipt.update(bindingSha256=digest,collection=info);self.save()
        returned=({},dict(seedBindingSha256='c'*64),{'seed':'same'})
        with patch.object(shards,'inspect',return_value=returned):
            receipt,_=shards.unpack_input(self.folder,self.root/'again','shard','automatic-healthy',self.source,self.manifest)
            self.assertEqual(digest,receipt['bindingSha256'])
        with patch.object(shards,'inspect',return_value=({},dict(seedBindingSha256='e'*64),{'seed':'same'})):
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                shards.unpack_input(self.folder,self.root/'changed','shard','automatic-healthy',self.source,self.manifest)
        part=next((self.folder/'parts').glob('part-*.bin'));data=part.read_bytes();part.write_bytes(data[:-1])
        with self.assertRaises(ValueError):
            shards.unpack_input(self.folder,self.root/'broken','shard','automatic-healthy',self.source,self.manifest)

    def test_aggregate_rejects_incomplete_directories_and_keeps_failure_receipt(self):
        with patch.object(shards,'build_identity'):
            manifest=self.root/'manifest.json';manifest.write_text('{}')
            output=self.root/'aggregate'
            with redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'missing/duplicate/extra'):
                shards.aggregate(output,manifest,self.source,self.folder)
            receipt=json.loads((output/'receipt.json').read_text())
            self.assertEqual('FAIL',receipt['status']);self.assertIn('failure',receipt)


class CombinedBudgetTest(unittest.TestCase):
    def test_each_collection_cannot_take_a_fresh_global_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);inputs=root/'inputs';roots={}
            for name in SHARDS:
                roots[name]=root/name;roots[name].mkdir()
                shards.save(roots[name]/collection.INDEX,{'trace.jsonl':dict(bytes=4,sha256='a'*64)})
                shards.save(inputs/name/'parts/parts.json',dict(compressedBytes=4,parts=[{}]))
            limits=dict(files=100,expandedBytes=10000,traceBytes=100,compressedBytes=100,parts=100)
            with patch.object(collection,'LIMITS',limits):self.assertEqual(12,shards.combined_limits(roots,inputs)['traceBytes'])
            for field,value in [('files',5),('expandedBytes',100),('traceBytes',10),('compressedBytes',10),('parts',2)]:
                with self.subTest(field=field),patch.object(collection,'LIMITS',{**limits,field:value}):
                    with self.assertRaisesRegex(ValueError,'combined rich evidence budget'):shards.combined_limits(roots,inputs)


if __name__=='__main__':unittest.main()
