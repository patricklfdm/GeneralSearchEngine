"""Closed-workload projection tests, with quorum already established by the caller."""
import base64
import copy
import struct
import unittest
from unittest.mock import patch
from . import measurement_projection as p,measurement_model as m,measurement_oracle as o


def blob(value):return struct.pack('>i',len(value))+value


def application(documents):
    return base64.b64encode(b'\0\1'+struct.pack('>i',0)+struct.pack('>i',len(documents))+
        b''.join(blob(struct.pack('>i',d['id']))+blob(m.encode_document(d)) for d in documents)).decode()


def payload(doc):return base64.b64encode(b'\0\1'+struct.pack('>i',1)+blob(struct.pack('>i',doc['id']))+blob(m.encode_document(doc))).decode()


class MeasurementProjectionTest(unittest.TestCase):
    def setUp(self):
        self.program=[c['document'] for c in m.program() if c['kind']=='update']
        self.offered=[dict(opId=f'w{i}',document=self.program[i],outcome=outcome) for i,outcome in enumerate(('SUCCESS','NOT_SUBMITTED','INDETERMINATE'))]
        self.chosen={'a':dict(index=1,operation=9,payload=''),'b':dict(index=2,operation=2,payload=payload(self.program[0])),
                     'c':dict(index=3,operation=9,payload=''),'d':dict(index=4,operation=2,payload=payload(self.program[2]))}
        self.genesis=dict(baseSequence=1,application=application(m.corpus()))

    def project(self):return p.Projection({},self.genesis,self.chosen,self.offered)

    def test_rejected_attempt_does_not_advance_sequence_uncertain_chosen_write_does(self):
        value=self.project();self.assertEqual([1,1,2,2,3],value.sequence_at);self.assertEqual([0,2],value.ordinals)
        self.assertEqual({'w0','w2'},set(value.update_entries));self.assertEqual(self.program[2],value.states[3]['documents'][2])
        request=value.query_input([dict(sequence=3,query=m.query(0))]);self.assertEqual(o.SELECTED_SCHEMA,request['schema']);self.assertEqual([0,2],request['offeredOrdinals'])

    def test_success_requires_chosen_and_rejection_cannot_hide_a_chosen_effect(self):
        self.offered[2]['outcome']='NOT_SUBMITTED'
        with self.assertRaisesRegex(ValueError,'rejected update was chosen'):self.project()
        self.offered[2]['outcome']='SUCCESS';self.chosen.pop('d')
        with self.assertRaisesRegex(ValueError,'successful update not chosen'):self.project()

    def test_missing_reordered_duplicate_foreign_and_non_program_entries_reject(self):
        changes=[lambda:self.chosen.pop('b'),lambda:self.chosen['d'].__setitem__('payload',payload(self.program[0])),
                 lambda:self.chosen['b'].__setitem__('payload',payload(self.program[5])),lambda:self.chosen['a'].__setitem__('operation',3)]
        for change in changes:
            self.setUp();change()
            with self.subTest(change=change),self.assertRaises(ValueError):self.project()

    def test_publication_and_response_follow_exact_chosen_index_and_application(self):
        value=self.project();state=value.states[3]
        snapshot=dict(anchors=[dict(entryDigest=d) for d in value.anchors],applicationSequence=3,application=application(state['documents']),terminalProof='proof')
        with patch.object(p.physical,'frame',return_value=dict(index=4,entryDigest='d',epoch=2)):
            self.assertEqual(3,value.publication(snapshot)['sequence'])
            for key,replacement in (('applicationSequence',4),('application',application(m.corpus())),('anchors',snapshot['anchors'][1:])):
                wrong=copy.deepcopy(snapshot);wrong[key]=replacement
                with self.assertRaises(ValueError):value.publication(wrong)
        with self.assertRaisesRegex(ValueError,'response before chosen publication'):value.update_response(self.offered[0],1)
        self.assertEqual(2,value.update_response(self.offered[0],2)['index'])
        self.assertIsNone(value.update_response(self.offered[1],4))

    def test_noop_cannot_invent_an_application_sequence_or_payload(self):
        self.chosen['a']['payload']=base64.b64encode(b'bad').decode()
        with self.assertRaisesRegex(ValueError,'NO_OP payload'):self.project()


if __name__=='__main__':unittest.main()
