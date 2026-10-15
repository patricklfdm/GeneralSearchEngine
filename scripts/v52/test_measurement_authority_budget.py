import base64
import json
import unittest
from unittest.mock import patch
from . import measurement_authority_budget as b
from .evidence import digest,encoded


def frame(value):
    raw=encoded(value);return base64.b64encode(b'X'*16+bytes.fromhex(digest(raw))+raw).decode()
def decode(raw,kind,manifest):return json.loads(base64.b64decode(raw)[48:])
def wire(raw,manifest):return json.loads(raw[48:])
def row(event,**values):return dict(event=event,node='node-1',groupId='group',manifestDigest='manifest',**values)
def reply(kind,payload,sender='node-1'):return row('REPLY',frame=frame(dict(type=kind,payload=payload,sender=sender)))


class MeasurementAuthorityBudgetTest(unittest.TestCase):
    def validate(self,rows):
        # Resource accounting unit fixtures only. Real retained evidence exercises
        # the unpatched canonical/contextual frame inspectors separately.
        with patch.object(b.physical,'frame',side_effect=decode),patch.object(b.physical.f,'wire',side_effect=wire):
            return b.validate({'node-1':rows},dict(groupId='group',digest='manifest'))

    def test_exact_retries_charge_once_and_changed_retry_never_replaces_retained_bytes(self):
        retained=b.Retained('fixture',2,3);self.assertTrue(retained.add('a',b'xx'));self.assertFalse(retained.add('a',b'xx'))
        with self.assertRaisesRegex(ValueError,'changed retained'):retained.add('a',b'yy')
        with self.assertRaisesRegex(ValueError,'retained budget'):retained.add('b',b'xx')
        self.assertEqual(dict(count=1,bytes=2),retained.report())
        retained.add('b',b'x')
        with self.assertRaisesRegex(ValueError,'retained budget'):retained.add('c',b'')
        self.assertEqual(dict(count=2,bytes=3),retained.report())

    def test_acceptance_and_ballot_maps_are_bounded_independently(self):
        entry=frame(dict(index=1));vote=dict(entry=entry,entryDigest='digest',epoch=1,incarnation='one')
        rows=[row('FORCE',kind='ACCEPT',record=frame(vote))]*3
        result=self.validate(rows);self.assertEqual(1,result['retained']['entries']['count']);self.assertEqual(1,result['retained']['votes']['count'])
        rows.append(row('FORCE',kind='ACCEPT',record=frame(dict(vote,epoch=2))))
        with patch.dict(b.LIMITS,{'votes':(1,1<<20)}),self.assertRaisesRegex(ValueError,'budget votes'):self.validate(rows)
        with patch.dict(b.LIMITS,{'entries':(1,1)}),self.assertRaisesRegex(ValueError,'budget entries'):self.validate(rows)
        with patch.dict(b.LIMITS,{'entries':(0,1<<20)}),self.assertRaisesRegex(ValueError,'entry index bound'):self.validate(rows)

    def test_tiny_basis_chunks_are_counted_and_empty_chunks_cannot_grow_maps(self):
        def chunk(offset,value):return reply('BASIS_CHUNK',dict(action='DATA',basisId='basis',offset=offset,chunk=base64.b64encode(value).decode()))
        with patch.dict(b.LIMITS,{'basisChunks':(1,1<<20)}),self.assertRaisesRegex(ValueError,'budget basisChunks'):
            self.validate([chunk(0,b'x'),chunk(1,b'y')])
        with self.assertRaisesRegex(ValueError,'empty retained'):self.validate([chunk(0,b'')])
        with self.assertRaisesRegex(ValueError,'changed retained'):self.validate([chunk(0,b'x'),chunk(0,b'y')])

    def test_shared_bases_are_charged_for_each_selected_reconstruction(self):
        bases=[frame(dict(node='node-'+str(i),basisId='basis-'+str(i),imageBytes=100)) for i in (1,2)]
        pair=[dict(node='node-'+str(i),basisId='basis-'+str(i),basisDigest=base64.b64decode(raw)[16:48].hex()) for i,raw in zip((1,2),bases)]
        rows=[reply('SELECTED_OFFER',dict(response=True,bases=bases,selected=frame(dict(bases=pair,ballot=i)))) for i in (1,2)]
        self.assertEqual(400,self.validate(rows)['selectedExpansionBytes'])
        with patch.object(b,'MAX_SELECTION_EXPANSION',399),self.assertRaisesRegex(ValueError,'selected expansion budget'):self.validate(rows)
        # Repeated receipt of one selection is not a second allocation.
        self.assertEqual(200,self.validate([rows[0],rows[0]])['selectedExpansionBytes'])

    def test_other_aggregate_limits_and_foreign_authority_reject(self):
        rows=[reply('PING',{})]
        with patch.dict(b.LIMITS,{'replies':(0,1<<20)}),self.assertRaisesRegex(ValueError,'budget replies'):self.validate(rows)
        with patch.object(b,'MAX_SELECTORS',1),self.assertRaisesRegex(ValueError,'selector count'):
            self.validate([row('STORAGE_CUT',cut='SELECTOR_BEFORE_ACK')]*2)
        rows[0]['groupId']='foreign'
        with self.assertRaisesRegex(ValueError,'trace authority'):self.validate(rows)


if __name__=='__main__':unittest.main()
