import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_dispatch_evidence as evidence


class NativeDispatchEvidenceTest(unittest.TestCase):
    def test_discovery_original_failure_stops_before_any_negative(self):
        with patch.object(evidence, 'validate', side_effect=ValueError('invalid original')) as original:
            with patch.object(evidence.tempfile, 'TemporaryDirectory') as mutations:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    evidence.qualify('invalid-root', discovery=True)
                original.assert_called_once_with('invalid-root', discovery=True)
                mutations.assert_not_called()

    def test_finite_identical_activation_replies_can_have_different_event_positions(self):
        rows = [('SELECTED', {'trace':'same'}, 'INSTALL_ACK', {'selection':'original'}, at) for at in (10,20,30)]
        self.assertEqual(rows, evidence.activation_attempts(rows))

    def test_missing_and_exhausted_activation_attempts_reject(self):
        for rows in ([], [('SELECTED', {}, 'INSTALL_ACK', {}, 1)]*4):
            with self.assertRaisesRegex(ValueError, '^native dispatch activation controls$'):
                evidence.activation_attempts(rows)

    def test_activation_retry_cannot_change_request_or_acknowledgement(self):
        original = ('SELECTED', {'trace':'original'}, 'INSTALL_ACK', {'selection':'original'}, 10)
        for changed in [('SELECTED', {'trace':'other'}, 'INSTALL_ACK', {'selection':'original'}, 20),
                        ('SELECTED', {'trace':'original'}, 'INSTALL_ACK', {'selection':'other'}, 20)]:
            with self.assertRaisesRegex(ValueError, '^native dispatch activation controls$'):
                evidence.activation_attempts([original, changed])

    def test_only_exact_original_local_image_bytes_allow_omitting_download(self):
        first, second = b'original application one', b'original application two'
        h1, h2 = evidence.e.digest(first), evidence.e.digest(second)
        members = {'source.gscp': b'packet', h1+'.image': first, h2+'.image': second}
        packet = {'images': {h1: len(first), h2: len(second)}}
        for local in ({}, {h1+'.image': b'changed'}, {h1: first}):
            full, borrowed = evidence.prefix_transfers('cut', members, packet, local)
            self.assertEqual(full, borrowed)
        full, borrowed = evidence.prefix_transfers('cut', members, packet, {h1+'.image': first})
        self.assertEqual(3, len(full))
        self.assertEqual([('cut', b'packet', 'CAPSULE'), (h2, second, 'APPLICATION')], borrowed)
        full, borrowed = evidence.prefix_transfers('cut', members, packet, members)
        self.assertEqual([('cut', b'packet', 'CAPSULE')], borrowed)

    def test_invalid_original_stops_before_any_negative_is_generated(self):
        with patch.object(evidence, 'validate', side_effect=ValueError('invalid original')) as original:
            with patch.object(evidence.tempfile, 'TemporaryDirectory') as mutations:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    evidence.qualify('invalid-root')
                original.assert_called_once_with('invalid-root')
                mutations.assert_not_called()

    def test_packet_only_maintenance_requires_every_original_local_image(self):
        images = [b'original one', b'original two']
        members = {'source.gscp': b'original packet', **{evidence.e.digest(raw)+'.image': raw for raw in images}}
        packet = dict(capsule=dict(root='root-a', cut=dict(index=1, entry='entry-a')),
                      images={evidence.e.digest(raw): len(raw) for raw in images})
        reference = evidence.current_reference(packet['capsule'], 'retained-current-packet')
        expected = [(reference, b'original packet', 'CAPSULE')]
        for local in ({}, {evidence.e.digest(images[0])+'.image': images[0]},
                      dict(members, **{evidence.e.digest(images[1])+'.image': b'wrong bytes'})):
            self.assertNotIn(expected, evidence.maintenance_prefixes(members, packet, local))
        self.assertIn(expected, evidence.maintenance_prefixes(members, packet, members))

    def test_generation_metadata_alias_keeps_every_original_metadata_member(self):
        members = {'source.gscp': b'packet', 'ancestry.gsr': b'ancestry', 'promise.gsr': b'promise',
                   'selected.gsr': b'selected', 'application.image': b'image'}
        packet = dict(capsule=dict(root='root-a', cut=dict(index=1, entry='entry-a')))
        variants = evidence.maintenance_generations(b'manifest', members, packet)
        self.assertEqual(2, len(variants))
        self.assertNotEqual(variants[0][0][0], variants[1][0][0])
        for records in variants:
            self.assertEqual([b'manifest', b'ancestry', b'promise', b'selected'], [row[1] for row in records])
            self.assertTrue(all(row[2]=='RECORD' for row in records))
        self.assertEqual(variants[0][1:], variants[1][1:])

    def test_current_lookup_aliases_are_bound_to_root_cut_and_export_scope(self):
        cap = dict(root='root-a', cut=dict(index=1, entry='entry-a'))
        packet = evidence.current_reference(cap, 'retained-current-packet')
        for other in (dict(cap, root='root-b'), dict(cap, cut=dict(index=2, entry='entry-b'))):
            self.assertNotEqual(packet, evidence.current_reference(other, 'retained-current-packet'))
        self.assertNotEqual(packet, evidence.current_reference(cap, 'retained-current-generation-metadata'))


    def test_precommand_window_starts_only_after_prior_completed_publication(self):
        events=[{'event':n} for n in ('SLOT_BEGIN','PUBLICATION_BEFORE_RETURN','ROUND_SLOT_COMPLETE',
                'FLOOR_PARENT_FORCED','SLOT_BEGIN','ROUND_SLOT_COMPLETE')]
        self.assertEqual(2,evidence.round_maintenance_boundary(events,[0,4]))
        for names in (['SLOT_BEGIN','SLOT_BEGIN'],['ROUND_SLOT_COMPLETE','SLOT_BEGIN','SLOT_BEGIN','ROUND_SLOT_COMPLETE'],
                      ['SLOT_BEGIN','ROUND_SLOT_COMPLETE','ROUND_SLOT_COMPLETE','SLOT_BEGIN','ROUND_SLOT_COMPLETE'],
                      ['SLOT_BEGIN','SLOT_BEGIN','ROUND_SLOT_COMPLETE','ROUND_SLOT_COMPLETE']):
            with self.subTest(names=names),self.assertRaisesRegex(ValueError,'serialized round boundaries'):
                evidence.round_maintenance_boundary([{'event':n} for n in names],[i for i,n in enumerate(names) if n=='SLOT_BEGIN'])

    def test_precommand_completion_must_bind_original_physical_publication(self):
        raw=b'original local acknowledgement';selection=dict(root='root',view='view',ballot={'counter':1})
        identity={'node':'node-1'};first=dict(originals=[b'entry',b'accept',b'proof',b'certificate'],upper={'index':1},
            published={'node-1':{'g/generation.gsr':b'generation'}})
        ack=dict(selection,sender=identity,recipient=identity,sequence=1,payload=dict(certificate=evidence.e.digest(b'certificate'),
            selection=evidence.e.digest(b'selected'),published=first['upper'],generation=evidence.e.digest(b'generation')))
        row=dict(node='node-1',event='ROUND_SLOT_COMPLETE',record=evidence.e.digest(raw),bytes=base64.b64encode(raw).decode())
        events=[{'event':'SLOT_BEGIN'},row,{'event':'FLOOR_PARENT_FORCED'},{'event':'SLOT_BEGIN'},{'event':'ROUND_SLOT_COMPLETE'}]
        def boundary(value):
            with patch.object(evidence.c,'current',return_value=('g/',{},{})),patch.object(evidence.f,'encode',return_value=b'selected'),patch.object(evidence.f,'decode',return_value=value):
                return evidence.round_publication_boundary(events,[0,3],first,selection,identity)
        self.assertEqual(1,boundary(ack))
        for key,value in [('root','other'),('view','other'),('ballot',{'counter':2}),('sender',{'node':'node-2'}),('recipient',{'node':'node-2'}),('sequence',2)]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'original publication acknowledgement'):boundary(dict(ack,**{key:value}))
        for key in ack['payload']:
            changed=copy.deepcopy(ack);changed['payload'][key]='forged'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'original publication acknowledgement'):boundary(changed)
        events[1]['record']='0'*64
        with self.assertRaisesRegex(ValueError,'round event digest'):boundary(ack)

    def test_observation_mutation_targets_precommand_floor_without_moving_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);names=['SLOT_BEGIN','ROUND_SLOT_COMPLETE','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
                *evidence.s.r.POINTS,'SLOT_BEGIN','ROUND_SLOT_COMPLETE']
            rows=[dict(node='node-1',event=n) for n in names];(root/'events.json').write_text(json.dumps(rows))
            evidence.mutate_observation(root,'observation-missing-force',precommand_maintenance=True)
            after=evidence.read(root/'events.json')
            self.assertEqual([row for row in rows if row['event']!='RETENTION_FORCED'],after)
            self.assertLess(next(i for i,v in enumerate(after) if v['event']=='FLOOR_PARENT_FORCED'),
                            [i for i,v in enumerate(after) if v['event']=='SLOT_BEGIN'][1])

    def test_precommand_original_failure_still_precedes_all_negative_mutations(self):
        with patch.object(evidence,'validate',side_effect=ValueError('broken original')) as validate,patch.object(evidence.tempfile,'TemporaryDirectory') as copy:
            with self.assertRaisesRegex(ValueError,'broken original'):evidence.qualify('/original',precommand_maintenance=True,confirmed_retention=True)
        validate.assert_called_once_with('/original',precommand_maintenance=True,confirmed_retention=True);copy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
