import copy
from pathlib import Path
import tempfile
import unittest
from . import measurement_model as m,measurement_oracle as o
from .evidence import encoded,digest


class MeasurementOracleTest(unittest.TestCase):
    def setUp(self):
        self.updates=[r['document'] for r in m.program() if r['kind']=='update']
        self.cuts=[dict(sequence=s,query=m.query(i)) for s in (1,2,65,66,181) for i in range(15)]
        self.input=o.prepare(self.cuts,self.updates)

    def test_duplicate_descriptor_only_reuses_same_application_sequence(self):
        value=o.prepare(self.cuts+self.cuts,self.updates);self.assertEqual(self.input,value)
        # Ranked/highlight descriptors repeat within each 15-call slice: eleven
        # distinct queries at each of five application sequences remain.
        self.assertEqual(55,len(value['requests']))
        self.assertEqual(181,len(o.states(value)));self.assertEqual(m.projection(m.program()),o.states(value)[181])

    def test_missing_changed_or_reordered_update_prefix_is_rejected(self):
        for updates in (self.updates[1:],list(reversed(self.updates)),self.updates+[self.updates[-1]]):
            with self.assertRaisesRegex(ValueError,'update prefix'):o.prepare(self.cuts,updates)

    def test_selected_schema_keeps_actual_sequence_separate_from_offered_ordinal(self):
        value=o.prepare_selected([dict(sequence=3,query=m.query(0))],[0,2])
        self.assertEqual(o.SELECTED_SCHEMA,value['schema']);self.assertEqual([self.updates[0],self.updates[2]],value['updates'])
        self.assertEqual(3,len(o.states(value)));self.assertEqual(self.updates[2],o.states(value)[3]['documents'][2])
        for ordinals in ([0,0],[2,0],[True],[180],[-1]):
            with self.subTest(ordinals=ordinals),self.assertRaises(ValueError):o.prepare_selected([dict(sequence=1,query=m.query(0))],ordinals)
        for change in (lambda v:v.__setitem__('schema',o.SCHEMA),lambda v:v['updates'].reverse(),lambda v:v['offeredOrdinals'].__setitem__(1,1)):
            mutated=copy.deepcopy(value);change(mutated)
            with self.assertRaises(ValueError):o.validate(mutated)

    def test_wrong_sequence_or_non_program_query_cannot_be_cached(self):
        for sequence,query in ((True,m.query(0)),(0,m.query(0)),(182,m.query(0)),(1,dict(kind='get',id=65)),(1,dict(kind='get',id=True))):
            with self.subTest(sequence=sequence,query=query),self.assertRaises(ValueError):o.prepare([dict(sequence=sequence,query=query)],self.updates)

    def test_output_cannot_miss_duplicate_reorder_or_borrow_another_state(self):
        state=o.states(self.input)
        original=[dict(**row,stateSha256=digest(encoded(state[row['sequence']])),answer={'synthetic':True}) for row in self.input['requests']]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'answers.jsonl'
            def save(rows):path.write_bytes(b''.join(encoded(r)+b'\n' for r in rows))
            save(original);self.assertEqual(55,len(o.validate_output(self.input,path)))
            mutations=[original[:-1],original+[original[-1]],[original[1],original[0],*original[2:]]]
            wrong=copy.deepcopy(original);wrong[-1]['stateSha256']=wrong[0]['stateSha256'];mutations.append(wrong)
            wrong=copy.deepcopy(original);wrong[0]['sequence']=True;mutations.append(wrong)
            for rows in mutations:
                save(rows)
                with self.assertRaises(ValueError):o.validate_output(self.input,path)
            save(original);path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'completeness'):o.validate_output(self.input,path)

    def test_duplicate_identity_and_input_replay_order_reject(self):
        for transform in (lambda r:[r[0],*r],lambda r:list(reversed(r))):
            value=copy.deepcopy(self.input);value['requests']=transform(value['requests'])
            with self.assertRaises(ValueError):o.validate(value)
        with self.assertRaisesRegex(ValueError,'cut bound'):o.prepare([self.cuts[0]]*(o.MAX_REQUESTS+1),self.updates)


if __name__=='__main__':unittest.main()
