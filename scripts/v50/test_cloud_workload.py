"""Cloud workload contract, bounded stream negatives and resealed real-evidence negatives."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
from unittest.mock import patch
import tempfile
import unittest
import zipfile
from .admission_format import check
from .cloud_workload_plan import PLAN, read_plan, arithmetic
from .cloud_workload_model import Model, operation, payload
from .cloud_workload_io import parse_json, relative, pack, unpack, inventory, rows, validate_source_archive
from .performance_model import OP_IDS, digest, canonical
from .offline_harness import save


class CloudWorkloadTests(unittest.TestCase):
    def test_frozen_corpus_and_full_sequence_arithmetic(self):
        result=arithmetic(read_plan())
        self.assertEqual((result['corpusDocuments'],result['maximumBulkPayloadBytes'],result['reservedEntries']),(4096,1169,21524))
    def test_changed_plan_is_not_a_new_admitted_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';plan=read_plan();plan['localQualification']['execution']='gcp-canonical';p.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'unreviewed'):read_plan(p)
    def test_local_pacing_is_separate_from_fixed_cloud_rates(self):
        p=read_plan();local=p['localQualification']
        self.assertEqual(local['preset'],'v5.0-cloud-workload-local-qualification-v2')
        self.assertEqual((local['pacing'],local['maximumWindowSeconds']),('completion-paced',20))
        self.assertEqual((p['workload']['healthyIntervalNanos'],p['workload']['sustainedIntervalNanos']),(100000000,50000000))
    def test_healthy_cycle_preserves_corpus_order_and_bulk_atomicity(self):
        m=Model()
        for i in range(10):
            op=operation(0,i)
            if op['operation'] in OP_IDS:m.apply(OP_IDS[op['operation']],payload(op['operation'],op['keys'],op['revision']))
        self.assertEqual((m.sequence,len(m.docs),list(m.docs)),(264,4096,list(range(1,4097))))
        self.assertEqual(m.docs[1][-1],'java search memory revision 1')
        self.assertEqual([json.loads(value)['field'] for value in m.indexes],['body','category','price','title'])
    def test_sustained_lanes_have_independent_keys_and_revisions(self):
        ops=[operation(5+i//10,i,True) for i in range(32)]
        self.assertEqual(sum(r['operation']=='UPDATE' for r in ops),24)
        for lane in range(4):
            mutations=[r for r in ops if r['lane']==lane and r['operation']=='UPDATE']
            self.assertTrue(all(r['keys']==[lane+1] for r in mutations))
            self.assertEqual([r['revision'] for r in mutations],[1,2,3,5,6,7])
    def test_json_duplicate_nonfinite_and_deep_values(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'['*25+b'0'+b']'*25):
            with self.subTest(raw=raw),self.assertRaises(ValueError):parse_json(raw)
    def test_path_traversal_and_aliases(self):
        for name in ('../x','/tmp/x','a/../x','a//b','./x','a\\x','a/./x',''):
            with self.subTest(name=name),self.assertRaises(ValueError):relative(name)
    def test_stream_truncation_and_part_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'part-0000.jsonl').write_text('{"x":1}')
            with self.assertRaisesRegex(ValueError,'truncated'):list(rows(p))
            (p/'part-0000.jsonl').unlink();(p/'part-0001.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'part'):list(rows(p))
    def test_part_manifest_reassembly_and_missing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();(source/'a').write_bytes(b'abc');(source/'empty').write_bytes(b'')
            pack(source,root/'bundle');unpack(root/'bundle',root/'valid');self.assertEqual((root/'valid/a').read_bytes(),b'abc')
            p=root/'bundle/parts.json';m=json.loads(p.read_text());m['files']['a']['bytes']=4;save(p,m)
            with self.assertRaisesRegex(ValueError,'reassembly'):unpack(root/'bundle',root/'bad')
    def test_duplicate_chunk_and_unlisted_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();(source/'a').write_bytes(b'a');(source/'b').write_bytes(b'b')
            pack(source,root/'bundle');p=root/'bundle/parts.json';original=json.loads(p.read_text());m=copy.deepcopy(original)
            m['files']['b']['parts']=m['files']['a']['parts'];save(p,m)
            with self.assertRaisesRegex(ValueError,'duplicate'):unpack(root/'bundle',root/'bad')
            save(p,original);(root/'bundle/unlisted.bin').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'unlisted'):unpack(root/'bundle',root/'bad2')
    def test_symlinks_never_enter_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'link').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError,'nonregular'):inventory(p)
    def test_source_archive_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.zip'
            with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('../escape',b'x')
            with self.assertRaisesRegex(ValueError,'traversal'):validate_source_archive(p,{'../escape':digest(b'x')})

    def test_reordered_parts_fail_complete_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp, patch('scripts.v50.cloud_workload_io.BINARY_LIMIT',4):
            root=Path(tmp);source=root/'source';source.mkdir();(source/'data').write_bytes(b'abcdefgh')
            pack(source,root/'bundle');p=root/'bundle/parts.json';m=json.loads(p.read_text());m['files']['data']['parts'].reverse();save(p,m)
            with self.assertRaisesRegex(ValueError,'ordered reassembly'):unpack(root/'bundle',root/'bad')
    def test_archive_expansion_is_rejected_before_opening_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('data',b'x')
            raw=bytearray(p.read_bytes());offset=raw.index(b'PK\x01\x02');struct.pack_into('<I',raw,offset+24,129<<20);p.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'archive expansion'):validate_source_archive(p,{'data':digest(b'x')})


def negatives(raw,output):
    from .cloud_workload_evidence import validate_raw
    raw=Path(raw);validate_raw(raw);results=[]
    def change_json(root,name,fn):
        p=root/name;value=json.loads(p.read_text());fn(value);save(p,value)
    def change_row(root,directory,predicate,fn):
        for p in sorted((root/directory).glob('part-*.jsonl')):
            values=[json.loads(line) for line in p.read_text().splitlines()]
            for value in values:
                if predicate(value):
                    fn(value);p.write_text(''.join(json.dumps(v,sort_keys=True,separators=(',',':'))+'\n' for v in values));return
        raise ValueError('negative fixture row not found')
    leader='streams/node-1-1/'
    cases={
        'cloud-relabel':lambda r:change_json(r,'set.json',lambda v:v.update(execution='gcp-canonical')),
        'wrong-plan':lambda r:change_json(r,'plan.json',lambda v:v.update(corpusDocuments=64)),
        'missing-cell':lambda r:change_json(r,'cells.json',lambda v:v.pop(5)),
        'failed-cell':lambda r:change_json(r,'cells.json',lambda v:v[2].update(status='FAIL')),
        'forged-cleanup':lambda r:change_json(r,'members/node-1-1.json',lambda v:v.update(cleanup='not-reaped')),
        'serial-voter':lambda r:change_json(r,'members/node-3-1.json',lambda v:v.update(readyNanos=v['finishedNanos']-1)),
        'forged-success':lambda r:change_row(r,leader+'calls',lambda v:v['operation']=='UPDATE',lambda v:v.update(afterSequence=30000)),
        'suppressed-rejection':lambda r:change_row(r,leader+'calls',lambda v:v['operation']=='ADD',lambda v:v.update(outcome='rejected')),
        'wrong-read':lambda r:change_row(r,leader+'calls',lambda v:v['operation']=='QUERY',lambda v:v.update(answerDigest='0'*64)),
        'ambiguous-read-cut':lambda r:change_row(r,leader+'calls',lambda v:v['operation']=='QUERY',lambda v:v.update(afterSequence=v['beforeSequence']+1)),
        'short-window':lambda r:change_row(r,leader+'windows',lambda v:True,lambda v:v.update(endNanos=v['startNanos']+1)),
        'changed-arrival-rate':lambda r:change_row(r,leader+'windows',lambda v:True,lambda v:v.update(intervalNanos=1)),
        'changed-pacing-mode':lambda r:change_row(r,leader+'windows',lambda v:True,lambda v:v.update(pacing='fixed-rate')),
        'forged-nominal-arrival':lambda r:change_row(r,leader+'calls',lambda v:True,lambda v:v.update(nominalScheduledNanos=v['nominalScheduledNanos']+1)),
        'overlong-local-window':lambda r:change_row(r,leader+'windows',lambda v:True,lambda v:v.update(endNanos=v['startNanos']+20_000_000_001)),
        'overlapping-client-lane':lambda r:change_row(r,leader+'calls',lambda v:v['call']==0,lambda v:v.update(endNanos=v['endNanos']+1_000_000_000)),
        'changed-corpus-output':lambda r:change_row(r,leader+'states',lambda v:True,lambda v:v['documents'].__setitem__(0,'forged document')),
        'forged-force':lambda r:change_row(r,leader+'forces',lambda v:True,lambda v:v.update(endNanos=v['startNanos'])),
        'missing-proof-stage':lambda r:change_row(r,leader+'events',lambda v:v['event']=='AFTER_PROOF_QUORUM',lambda v:v.update(event='BEFORE_PROOF_QUORUM')),
        'forged-resource':lambda r:change_row(r,leader+'resources',lambda v:True,lambda v:v['runtime'].update(pendingClients=999)),
        'missing-sample':lambda r:(r/leader/'calls/part-0000.jsonl').unlink(),
        'forged-summary':lambda r:change_json(r,'measurements.json',lambda v:v['candidate'].update(instrumentedToBaselineServiceTimePpm=1)),
        'wrong-control':lambda r:change_json(r,'metadata.json',lambda v:v['jars']['control'].update(sha256='0'*64)),
        'one-survivor-success':lambda r:change_json(r,'cells.json',lambda v:next(c for c in v if c['name']=='leader-replacement')['details']['oneSurvivor'].update(accepted=True)),
        'changed-protected-source':lambda r:change_json(r,'cells.json',lambda v:next(c for c in v if c['name']=='capacity')['details'].update(sourceAfter={})),
        'forged-capacity':lambda r:change_json(r,'cells.json',lambda v:next(c for c in v if c['name']=='capacity')['details']['attempts'][-1].update(reason='STORAGE_FAILURE')),
    }
    if (raw/'offline-bundle.json').exists():
        cases['changed-bundle-class'] = lambda r: next((r/'classes-candidate').rglob('V50CloudWorkloadConsumer.class')).write_bytes(b'forged')
        cases['forged-bundle-inputs'] = lambda r: change_json(r,'offline-bundle.json',lambda v:v.update(inputs={}))
    if json.loads((raw/'metadata.json').read_text()).get('volumeLayout'):
        cases['false-volume-layout'] = lambda r: change_json(r,'metadata.json',lambda v:v.update(volumeLayout=False))
        cases['missing-volume-authority'] = lambda r: (r/'volume-1/node-1/manifest.gsr').unlink()
    for name,mutate in cases.items():
        with tempfile.TemporaryDirectory(prefix='gse-workload-negative-') as tmp:
            candidate=Path(tmp)/'raw';shutil.copytree(raw,candidate);mutate(candidate)
            env=json.loads((candidate/'set.json').read_text());env['files']=inventory(candidate,exclude=('set.json',),logical=True);save(candidate/'set.json',env)
            try:validate_raw(candidate)
            except (ValueError,KeyError,TypeError,FileNotFoundError) as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
            else:raise AssertionError('resealed semantic negative accepted: '+name)
    save(Path(output),results);print(json.dumps(dict(semanticNegatives=len(results),status='PASS')),flush=True)


if __name__=='__main__':
    import sys
    if '--evidence' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        args=p.parse_args();negatives(args.evidence,args.output)
    else:unittest.main()
