from copy import deepcopy
import hashlib
import json
import struct
import subprocess
import sys
import unittest

from . import format_fixture as f


class FormatTest(unittest.TestCase):
    def fixture(self):return json.loads((f.ROOT/'docs/v5x/v5.3/byte-fixtures.json').read_text())

    def test_exact_retained_independent_golden_bytes_for_every_record_and_wire_kind(self):
        saved=self.fixture();self.assertEqual(saved,f.generate())
        for row in saved['fixtures']:
            with self.subTest(family=row['family'],name=row['name']):
                data=bytes.fromhex(row['hex']);self.assertEqual(data,f.encode(row['family'],row['name'],row['value']))
                self.assertEqual(row['value'],f.decode(data,row['family'],row['name']))

    def test_each_frame_rejects_version_type_flags_length_checksum_truncation_and_root_drift(self):
        for row in self.fixture()['fixtures']:
            data=bytes.fromhex(row['hex']);family,name=row['family'],row['name']
            f.decode(data,family,name)
            for offset in (0,5,7,9,11,15,16,48):
                changed=bytearray(data);changed[offset]^=1
                with self.subTest(name=name,offset=offset),self.assertRaises(ValueError):f.decode(bytes(changed),family,name)
            for changed in (data[:-1],data+b'\0'):
                with self.assertRaises(ValueError):f.decode(changed,family,name)
            if 'root' in row['value']:
                with self.assertRaisesRegex(ValueError,'foreign root'):f.decode(data,family,name,'f'*64)

    def test_recomputed_checksum_cannot_hide_duplicate_unknown_or_noncanonical_json(self):
        row=next(v for v in self.fixture()['fixtures'] if v['name']=='NODE');value=row['value'];raw=bytes.fromhex(row['hex'])
        bodies=[f.canonical(value)[:-1]+b',"root":"'+value['root'].encode()+b'"}',
                f.canonical(dict(value,extra=True)),json.dumps(value,indent=2).encode()]
        for body in bodies:
            prefix=raw[:12]+len(body).to_bytes(4,'big');frame=prefix+hashlib.sha256(prefix+body).digest()+body
            with self.assertRaises(ValueError):f.decode(frame,'records','NODE')

    def test_command_payloads_and_unchanged_read_token_layout(self):
        saved=self.fixture();c=f.catalog()
        self.assertEqual(set(c['commands'])-{'DATA'},{v['name'] for v in saved['commandPayloads']})
        for row in saved['commandPayloads']:
            raw=bytes.fromhex(row['hex']);self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest())
            if row['name']=='BARRIER':self.assertEqual(b'',raw)
            else:
                f.check_type(row['value'],{'object':c['commands'][row['name']]},c['types'])
                self.assertEqual(raw,f.canonical(row['value']))
        token=bytes.fromhex(saved['unchangedReadTokenV1']['hex'])
        self.assertEqual(112,len(token));self.assertEqual(b'GSRT\1\0\0\0',token[:8])
        self.assertEqual(17,int.from_bytes(token[72:80],'big'));self.assertEqual(bytes.fromhex('03'*32),token[40:72])
        self.assertEqual(hashlib.sha256(b'gse-replica-read-token/1\0'+token[:80]).digest(),token[80:])

    def test_scalars_and_oversize_arrays_fail_without_assertions(self):
        c=f.catalog()
        for value,spec in ((True,'positive'),(-1,'counter'),(2**63,'positive'),('0'*36,'uuid'),('../x','relative'),
                           ('A'*64,'hash'),('Node','node'),('Zg','blob'),('::bad host','host')):
            with self.subTest(value=value),self.assertRaises(ValueError):f.check_type(value,spec,c['types'])
        with self.assertRaises(ValueError):f.check_type([1]*7,{'array':'positive','min':2,'max':6},c['types'])
        for host in ('::1','2001:db8::1','127.0.0.1','node-1.example'):f.check_type(host,'host',c['types'])
        for host in ('2001:0db8::1','127.00.0.1','Example.COM','node..example'):
            with self.assertRaises(ValueError):f.check_type(host,'host',c['types'])
        result=subprocess.run([sys.executable,'-O','-c',"from scripts.v53.format_fixture import check_type; check_type(True,'positive',{})"],capture_output=True)
        self.assertNotEqual(0,result.returncode)

    def test_resource_envelope_covers_edges_ranges_catalog_and_all_retained_sources(self):
        r=f.catalog()['resources'];changes=r['membershipChangesMax']
        self.assertEqual(3*changes+1,r['capsuleItemsMax'])
        capsule=2*changes*r['membershipEdgeBytesMax']+(changes+1)*r['stableRangeBytesMax']+r['catalogBytesMax']+r['capsuleEnvelopeBytesMax']
        self.assertLessEqual(capsule,r['capsuleBytesMax'])
        peak=(r['generationsMax']+r['selectedSourcesMax']+r['learnersMax'])*r['capsuleBytesMax']
        peak+=r['metadataJournalBytesMax']+r['catalogBytesMax']+r['metadataMiscBytesMax']
        self.assertLessEqual(peak,r['metadataBytesMax'])
        self.assertLess(r['operationNumberMax'],2**63-1)

    def test_parser_budget_precedes_recursive_json_decode(self):
        for body in (b'['*17+b'0'+b']'*17,b'['+b'0,'*65536+b'0]'):
            prefix=struct.pack('>4sHHHHI',b'GSER',1,3,f.catalog()['records']['CAPSULE']['id'],0,len(body))
            frame=prefix+hashlib.sha256(prefix+body).digest()+body
            with self.assertRaisesRegex(ValueError,'parser depth/node'):f.decode(frame,'records','CAPSULE')

    def test_catalog_does_not_grow_with_normal_data_after_membership_budget_exhaustion(self):
        from . import operation_model as m
        from . import operation_oracle as o
        from .test_operation_model import store,req,complete
        s=store(limits=m.Limits(changes=1));s.submit(req(s));complete(s);s.commit('RETIRE',through=1)
        self.assertEqual(s.state,o.check(s.evidence())['state'])
        with self.assertRaises(ValueError):s.submit(req(s,'REMOVE'))
        state=deepcopy(s.state)
        # Pure reducer longevity: not a 10,000-slot consensus experiment.
        from dataclasses import asdict
        before=set(state);largest=0
        for i in range(10000):
            command=dict(kind='DATA',value=str(i));state=o.next_state(state,command,asdict(s.limits),set())
            self.assertEqual(before,set(state));largest=max(largest,len(f.canonical(state)))
        self.assertLess(largest,2048);self.assertEqual(2,state['nextOperation']);self.assertEqual(4,len(state['identities']))


if __name__=='__main__':unittest.main()
