import copy
import json
import unittest
from . import case_inventory as i


class CaseInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((i.DOCS/'acceptance-plan.json').read_text());cls.value=i.generate(cls.plan)

    def test_full_frozen_axes_are_expanded_without_runtime_claims(self):
        result=i.validate(self.value,self.plan)
        self.assertEqual(3310,result['scenarios']);self.assertEqual(24,result['negativeFamilies']);self.assertFalse(result['runtimeQualified'])
        self.assertEqual({f'N{n:02}' for n in range(1,25)},{r['id'] for r in self.value['negatives']})
        joint=[r for r in self.value['scenarios'] if r['scenario']=='S02' and r['context']['era']=='joint']
        self.assertEqual(112,len(joint));self.assertEqual(7,len({r['context']['profile'] for r in joint}))
        self.assertEqual({3,4,5},{r['context']['initial'] for r in self.value['scenarios'] if r['scenario']=='S07'})
        self.assertEqual({'ADD','REPLACE'},{r['context']['change'] for r in self.value['scenarios'] if r['scenario']=='S03'})
        self.assertTrue(all(r['inapplicablePolicy']=='explicit-refusal-with-unchanged-bytes' for r in self.value['scenarios']))
        self.assertEqual(self.value,i.generate(self.plan))

    def test_missing_duplicate_and_invented_rows_cannot_pass(self):
        for field in ('scenarios','negatives'):
            for mode in ('missing','duplicate','invented','changed'):
                value=copy.deepcopy(self.value);rows=value[field]
                if mode=='missing':rows.pop()
                elif mode=='duplicate':rows.append(copy.deepcopy(rows[0]))
                elif mode=='invented':rows[0]['id']='invented'
                else:rows[0]['state']='PASS'
                with self.subTest(field=field,mode=mode),self.assertRaisesRegex(ValueError,'inventory'):i.validate(value,self.plan)

    def test_no_mode_or_era_can_be_dropped_or_relabelled(self):
        for mutate in (lambda v:v['scenarios'].pop(next(n for n,r in enumerate(v['scenarios']) if r['mode']=='kill')),
                       lambda v:v['scenarios'][200]['context'].update(era='unknown'),
                       lambda v:v.update(runtimeQualified=True),lambda v:v.update(planSha256='f'*64)):
            value=copy.deepcopy(self.value);mutate(value)
            with self.assertRaises(ValueError):i.validate(value,self.plan)
        changed=copy.deepcopy(self.plan);changed['scenarios'][0]['modes'].remove('kill')
        with self.assertRaises(ValueError):i.validate(i.generate(changed),changed)


if __name__=='__main__':unittest.main()
