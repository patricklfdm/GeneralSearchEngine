"""Bounds, original-first rejection and complete conditional matrix admission."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import partial_joint_floor_evidence as r


class PartialJointFloorEvidenceTest(unittest.TestCase):
    def test_missing_empty_and_linked_history_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'empty').mkdir();(root/'link').symlink_to(root/'empty',target_is_directory=True)
            for name in ('missing','empty','link'):
                with self.subTest(name=name),self.assertRaises(ValueError):r.validate(root/name)

    def test_fixture_scope_and_exact_cut_cannot_be_upgraded(self):
        case=dict(profile='5-REPLACE',ordinal=1,cut=r.CUTS[0],handoff=True,historicalOwnershipVerified=False,
                  processDeath=False,nativeRuntime=False,phase3Complete=False)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in r.FILES:(root/name).touch()
            for field,value in [('ordinal',True),('ordinal',5),('cut','unknown'),('handoff',False),
                                ('historicalOwnershipVerified',True),('nativeRuntime',True),('processDeath',True),('phase3Complete',True)]:
                r.h.save(root/'case.json',dict(case,**{field:value}))
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'partial joint (declared case|bounded scope)'):
                    r.validate(root)

    def test_qualify_requires_an_original_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',side_effect=ValueError('original failed')),patch.object(r.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):r.qualify(temp)
            copied.assert_not_called()

    def test_unrelated_rejection_is_not_negative_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            r.h.save(Path(temp)/'case.json',dict(nativeRuntime=False))
            with patch.object(r,'validate',side_effect=[{},ValueError('unrelated')]),self.assertRaisesRegex(ValueError,'unrelated rejection'):
                r.qualify(temp)

    def test_missing_case_blocks_matrix(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'complete matrix'):
            r.matrix(temp)

    def test_duplicate_case_cannot_supply_missing_cut(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for n in range(16):(root/str(n)).mkdir()
            with patch.object(r,'validate',return_value=dict(ordinal=1,cut=r.CUTS[0])),self.assertRaisesRegex(ValueError,'duplicate case'):
                r.matrix(root)

    def test_unknown_mutation_refuses(self):
        with self.assertRaisesRegex(ValueError,'declared mutation'):r.mutate(Path('.'),'unknown')

    def test_exchange_total_includes_every_remote_owner(self):
        rows=[dict(request=node,response='reply') for node in ('node-6','node-6','node-2','node-2','node-5','node-5')]
        copies={node:{'generation.gsr':b'manifest','source.gscp':b'packet'} for node in r.NODES[1:]}
        cap=dict(root='00'*32,cut=dict(view=dict(generation=0,old=[],new=[],operation=None)))
        with patch.object(r,'read',return_value=rows),patch.object(r.joint.generation.t.t,'wire',side_effect=lambda node:('CHUNK',dict(recipient=dict(node=node)))),\
             patch.object(r.joint.generation,'sessions',return_value=[('',[]),('',[])]),patch.object(r.joint.generation,'attempts',return_value=[]),\
             patch.object(r.joint.generation.t,'transcript'):
            self.assertEqual(6,r.transfers(Path('.'),copies,cap,{}))
