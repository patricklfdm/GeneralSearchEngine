"""Synthetic recorder tests, with no native execution credit."""
import copy
import tempfile
from pathlib import Path
import unittest
from . import storage_transfer_evidence as r
from .test_resource_transitions import charge,trace,row


def fixture(cyclic=False):
    a=charge('APPLICATION','a',837);b=charge('APPLICATION','b',837)
    c=dict(a,owner='b' if cyclic else 'c');d=dict(b,owner='a' if cyclic else 'd')
    value=trace([row('START'),row('RESERVE',added=[a],staging=837,counts={'APPLICATION':1}),
                 row('RESERVE',added=[b],staging=1674,counts={'APPLICATION':2}),
                 row('TRANSFER',[] if cyclic else [a,b],[] if cyclic else [c,d],staging=1674,counts={'APPLICATION':2}),
                 row('RELEASE',[c],staging=837,counts={'APPLICATION':1}),row('RELEASE',[d])])
    captured=dict(schema=r.SCHEMA,transitions=len(value['changes']),truncated=False,failed=False,
                  rows=[dict(resourceSequence=3,moves=[dict(before=a,after=c),dict(before=b,after=d)])])
    return value,captured


class StorageTransferEvidenceTest(unittest.TestCase):
    def test_original_mapping_survives_sorted_equal_charge_sets_and_cyclic_delta(self):
        for cyclic in (False,True):
            data=fixture(cyclic);before=copy.deepcopy(data)
            self.assertEqual(data[1]['rows'],r.replay(*data));self.assertEqual(data,before)
            if cyclic:self.assertEqual([],data[0]['changes'][3]['removed'])

    def test_empty_original_transfer_set_is_valid_but_unobserved_switch_is_not(self):
        data=fixture();data[1]['rows']=[]
        with self.assertRaisesRegex(ValueError,'complete switch coverage'):r.replay(*data)
        closed=trace([row('START')]);value=dict(data[1],transitions=1)
        self.assertEqual([],r.replay(closed,value))

    def test_delta_alone_intentionally_does_not_prove_equal_image_pairing(self):
        value,captured=fixture();moves=captured['rows'][0]['moves']
        moves[0]['after'],moves[1]['after']=moves[1]['after'],moves[0]['after']
        # Only independent file/network derivation can reject this alternative.
        self.assertEqual(captured['rows'],r.replay(value,captured))

    def test_duplicate_claimed_changed_category_and_occupied_successors_fail(self):
        for kind in ('duplicate','claim','unit','unrelated','boolean'):
            data=fixture();moves=data[1]['rows'][0]['moves']
            if kind=='duplicate':moves.append(copy.deepcopy(moves[0]))
            elif kind=='claim':moves[0]['before']['claimSource']='foreign'
            elif kind=='unit':moves[0]['after']['unit']='GENERATION'
            elif kind=='unrelated':moves[0]['after']['owner']='z'
            else:moves[0]['before']['bytes']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):r.replay(*data)

    def test_read_rejects_duplicate_json_keys_noncanonical_and_missing_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.json';value=fixture()[1]
            raw=r.t.collection.snapshot.f.canonical(value);path.write_bytes(raw);self.assertEqual((raw,value),r.read(path))
            for bad in (b'{"rows":[],"rows":[]}',raw+b'\n',b'{}'):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):r.read(path)

    def test_loader_requires_original_hashes_identity_and_exact_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/r.DIRECTORY;directory.mkdir();value=fixture()[1]
            raw=r.t.collection.snapshot.f.canonical(value);(directory/'node-6.json').write_bytes(raw)
            owner=dict(identity={'node':'node-6'},path='node-6.json',sha256='a'*64,registeredAt=0)
            index=dict(root='b'*64,eventsSha256='c'*64,owners=[owner])
            ref=dict(identity=owner['identity'],path=owner['path'],sha256=r.t.collection.digest(raw),resourceSha256=owner['sha256'])
            captured=dict(schema='gse-v53-storage-transfer-capture-v1',root=index['root'],eventsSha256=index['eventsSha256'],owners=[ref])
            def save(x):(directory/'index.json').write_bytes(r.t.collection.snapshot.f.canonical(x))
            save(captured);self.assertEqual({'node-6':value},r.load(temp,index))
            for field in ('root','eventsSha256','identity','resourceSha256','path','sha256'):
                changed=copy.deepcopy(captured)
                if field in ('root','eventsSha256'):changed[field]='d'*64
                else:changed['owners'][0][field]='wrong'
                save(changed)
                with self.subTest(field=field),self.assertRaises(ValueError):r.load(temp,index)
            save(captured);(directory/'unrecorded.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'capture inventory'):r.load(temp,index)
            (directory/'unrecorded.json').unlink();(directory/'node-6.json').unlink()
            (directory/'node-6.json').symlink_to(directory/'index.json')
            with self.assertRaises(ValueError):r.load(temp,index)


if __name__=='__main__':unittest.main()
