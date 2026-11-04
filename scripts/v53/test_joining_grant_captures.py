"""Collection boundaries; mocked event fixtures do not qualify native history."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joining_grant_captures as g


def identity(node):
    return dict(node=node, storage='00000000-0000-0000-0000-'+str(int(node[-1])).zfill(12), host='127.0.0.1', port=19000+int(node[-1]))


def observed(node='node-1', counter=2):
    return dict(root='a'*64, node=node, identity=identity(node), scope='network-owner',
                ballot=dict(counter=counter, proposer='node-1', incarnation=identity('node-1')['storage']),
                basisId=node+'-'+str(counter), basisSha256=str(counter)*64, bytes=1)


def events(nodes):
    result=[]
    for i, node in enumerate(nodes, 1):
        result += [dict(node=node, event='GRANT_BEFORE_RETURN'),
                   dict(node=node, scope='network-owner', event=g.EVENT, capture=f'grant-captures/capture-{i:04d}')]
    return result


class JoiningGrantCapturesTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        (self.root/g.DIRECTORY).mkdir()

    def copies(self, count):
        for i in range(1,count+1): (self.root/g.DIRECTORY/f'capture-{i:04d}').mkdir()

    def test_interleaved_owners_pair_by_writer_scope_not_adjacency(self):
        self.copies(2); rows=events(['node-1','node-2']); rows=[rows[0],rows[2],rows[1],rows[3]]
        with patch.object(g, 'read', side_effect=[observed(),observed('node-2')]): result=g.collect(self.root,rows)
        self.assertEqual([0,1],[r['returnEvent'] for r in result]); self.assertEqual([2,3],[r['capturedEvent'] for r in result])

    def test_missing_return_pending_copy_duplicate_marker_and_path_are_refused(self):
        self.copies(1); original=events(['node-1'])
        variants=[(original[1:], 'orphan/capacity'), (original[:1], 'incomplete event copies'),
                  (original+[original[1]], 'orphan/capacity'),
                  ([original[0],dict(original[1],capture='../outside')], 'ordered unique path'),
                  ([original[0],original[0]], 'missing prior copy'),
                  ([original[0],dict(original[1],scope='other')], 'orphan/capacity')]
        for rows,reason in variants:
            with self.subTest(reason=reason),patch.object(g,'read',return_value=observed()),self.assertRaisesRegex(ValueError,reason):
                g.collect(self.root,rows)

    def test_same_original_reobservation_allowed_but_reused_identity_conflict_refused(self):
        self.copies(2); rows=events(['node-1','node-1'])
        with patch.object(g,'read',side_effect=[observed(),observed()]): self.assertEqual(2,len(g.collect(self.root,rows)))
        other=observed(); other['basisSha256']='f'*64
        with patch.object(g,'read',side_effect=[observed(),other]),self.assertRaisesRegex(ValueError,'reused source identity'):
            g.collect(self.root,rows)

    def test_copies_cannot_mix_roots_or_permanent_identities(self):
        self.copies(2); rows=events(['node-1','node-1'])
        for field,value,reason in [('root','b'*64,'mixed roots'),('identity',dict(identity('node-1'),port=19009),'owner changed')]:
            other=observed(counter=3); other[field]=value
            with self.subTest(field=field),patch.object(g,'read',side_effect=[observed(),other]),self.assertRaisesRegex(ValueError,reason):
                g.collect(self.root,rows)

    def test_extra_directory_empty_collection_and_aggregate_budget_refuse(self):
        with self.assertRaisesRegex(ValueError,'incomplete event copies'):g.collect(self.root,[])
        self.copies(2)
        with patch.object(g,'read',return_value=observed()),self.assertRaisesRegex(ValueError,'unobserved copies'):
            g.collect(self.root,events(['node-1']))
        with patch.object(g,'read',return_value=observed()),patch.object(g,'MAXIMUM_BYTES',1),self.assertRaisesRegex(ValueError,'aggregate capacity'):
            g.collect(self.root,events(['node-1','node-1']))

    def test_inventory_retains_empty_directories_rejects_links_and_extent(self):
        root=self.root/'replica';root.mkdir();(root/'empty').mkdir();(root/'file').write_bytes(b'abc')
        files,inventory,total=g.inventory(root)
        self.assertEqual({'empty':None,'file':b'abc'},files);self.assertEqual(3,total)
        self.assertEqual(dict(size=3,sha256=g.sha(b'abc')),inventory['file'])
        with patch.object(g,'MAXIMUM_BYTES',2),self.assertRaisesRegex(ValueError,'byte capacity'):g.inventory(root)
        (root/'link').symlink_to(root/'file')
        with self.assertRaisesRegex(ValueError,'linked/member capacity'):g.inventory(root)
        (root/'link').unlink()
        import os
        os.link(root/'file',root/'hardlink')
        with self.assertRaises(ValueError):g.inventory(root)

    def test_metadata_rejects_duplicate_keys_and_noncanonical_encoding(self):
        path=self.root/'capture.json';path.write_bytes(b'{"node":"a","node":"b"}')
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):g.json_file(path)
        path.write_bytes(b'{ }')
        with self.assertRaisesRegex(ValueError,'canonical metadata'):g.json_file(path)

    def before(self,node):
        owner=identity(node);root='a'*64
        return {'node.gsr':g.f.encode('records','NODE',dict(root=root,identity=owner)),
                'allocator.gsr':g.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=6)),
                'grants.gsr':g.f.encode('records','PROMISE',dict(root=root,view='b'*64,
                    ballot=observed(counter=6)['ballot'],basisId=None))}

    def test_boolean_sizes_cannot_masquerade_as_integer_inventory_extents(self):
        path=self.root/'capture';path.mkdir();replica=path/'replica';replica.mkdir();(replica/'file').write_bytes(b'x')
        metadata=dict(schema=g.SCHEMA,node='node-1',scope='test-owner',ballot={},basisId='unused',
                      basisSha256='a'*64,packetSha256='b'*64,
                      files=[dict(name='file',identity=dict(size=True,sha256=g.sha(b'x')))])
        raw=g.f.canonical(metadata);(path/'capture.json').write_bytes(raw)
        event=dict(node='node-1',scope='test-owner',event=g.EVENT,capture='grant-captures/capture-0001',
                   sha256=g.sha(raw),basis='a'*64)
        with self.assertRaisesRegex(ValueError,'^grant capture copied inventory$'):g.read(path,event)

    def test_intermediate_requires_both_original_voters_and_distinct_activation(self):
        rows=[observed(node,counter) for node in ('node-1','node-2') for counter in (7,8)]
        def load(path):return self.before(path.name),{},0
        with patch.object(g,'inventory',side_effect=load):self.assertEqual(7,g.require_intermediate(self.root,rows))
        for changed in (rows[1:],rows+[rows[0]],[dict(v,ballot=dict(v['ballot'],counter=8)) for v in rows],
                        [dict(v,root='b'*64) for v in rows],[dict(v,scope='other') for v in rows]):
            with patch.object(g,'inventory',side_effect=load),self.assertRaisesRegex(ValueError,'intermediate preparation missing/duplicate'):
                g.require_intermediate(self.root,changed)

    def test_complete_collection_is_still_partial(self):
        with patch.object(g,'collect',return_value=[observed()]),patch.object(g,'require_intermediate',return_value=7) as middle:
            result=g.validate(self.root,[],whole_history=True)
        self.assertEqual('PARTIAL',result['status']); self.assertEqual(7,result['intermediateBallot']); middle.assert_called_once()
        for flag in ('nativeHistoryQualified','intermediatePreparationPhysicalQualified','forceAndNetworkQualified','phase3Complete'):
            self.assertIs(result[flag],False)

    def test_cold_owner_requires_explicit_event_boundary(self):
        rows=[dict(observed(node,counter),capturedEvent=counter) for node in ('node-1','node-2') for counter in (7,8)]
        rows=[dict(v,scope='cold-owner') if v['node']=='node-2' and v['capturedEvent']>=8 else v for v in rows]
        def load(path):return self.before(path.name),{},0
        with patch.object(g,'inventory',side_effect=load):
            with self.assertRaisesRegex(ValueError,'intermediate preparation missing/duplicate'):g.require_intermediate(self.root,rows)
            self.assertEqual(7,g.require_intermediate(self.root,rows,old_owner_lifetimes={'node-2':(8,'cold-owner')}))
            for boundary,scope in ((7,'cold-owner'),(9,'cold-owner'),(8,'foreign-owner')):
                with self.assertRaisesRegex(ValueError,'original cold lifetime'):
                    g.require_intermediate(self.root,rows,old_owner_lifetimes={'node-2':(boundary,scope)})

    def test_owner_lifetime_declarations_fail_closed(self):
        for value in ({'foreign':(1,'cold')},{'node-2':(True,'cold')},{'node-2':(-1,'cold')},{'node-2':(1,'')},[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'declared owner lifetimes'):
                g.require_intermediate(self.root,[],old_owner_lifetimes=value)

    def test_negative_driver_requires_valid_original_and_exact_rejection(self):
        with patch.object(g,'validate',side_effect=ValueError('original')),patch.object(g,'mutate') as mutation:
            with self.assertRaisesRegex(ValueError,'^original$'):g.qualify(self.root,[])
            mutation.assert_not_called()
        for effect,reason in [([{},ValueError('unrelated')],'unrelated grant capture negative'),([{},{}],'mutation accepted')]:
            with patch.object(g,'validate',side_effect=effect),patch.object(g,'mutate'),self.assertRaisesRegex(ValueError,reason):
                g.qualify(self.root,[])


if __name__=='__main__':unittest.main()
