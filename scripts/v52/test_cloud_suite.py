import copy
import itertools
import unittest
from unittest.mock import patch
from . import cloud_suite as c


def binding():
    return dict(source='a'*40, checkoutSha256='b'*64, sequence='c'*32,
                suiteSha256=c.PLAN_SHA, programSha256=c.model.PLAN_SHA,
                buildManifestSha256='d'*64, packageSha256='e'*64,
                controlsManifestSha256=c.load()['controlsManifestSha256'])


def selections():
    owner=binding()
    return [c.selection(owner, name, f'{index:032x}') for index, name in enumerate(c.MEMBERS, 1)]


class CloudSuiteTest(unittest.TestCase):
    def test_five_members_cover_every_formal_history_once_with_separate_smoke(self):
        plan=c.load();names=[n for member in plan['members'].values() for n in member['histories']]
        self.assertEqual((33,33),(len(names),len(set(names))))
        self.assertEqual(set(plan['histories']),set(names))
        formal={n for n in names if plan['histories'][n]['family']!='UNTIMED'}
        self.assertEqual(set(c.machine.members()),formal)
        self.assertEqual({'members':5,'histories':33,'formalHistories':28,'reads':27428,'updates':2760,
                          'nominalM01Seconds':2700,'formalNegativesPerLocation':439},plan['totals'])
        for key in ('reads','updates','nominalM01Seconds'):
            self.assertEqual(plan['totals'][key],sum(v[key] for v in plan['members'].values()))
        self.assertEqual(439,sum(map(len,plan['formalNegativeRules'].values())))
        self.assertTrue(all(p['measurement'] is False for p in plan['histories'].values() if p['family']=='UNTIMED'))

    def test_canonical_windows_and_drill_parameters_are_the_existing_full_profiles(self):
        plan=c.load()
        for name,spec in c.machine.members().items():self.assertEqual(spec,plan['histories'][name])
        for repetition in (1,2,3):
            member=c.member(f'canonical-{repetition}')
            self.assertEqual(5,len(member['profiles']))
            self.assertTrue(all(v['profile']['durationNanos']==180_000_000_000 for v in member['profiles'].values()))
            self.assertTrue(all(v['profile']['repetition']==repetition for v in member['profiles'].values()))
        self.assertEqual([*c.minimum.CASES,*c.recovery.CASES],c.member('failure-drill')['histories'])

    def test_any_member_can_be_selected_first_and_all_orders_remain_unqualified(self):
        rows=selections();plan=c.load()
        # Only cache the already independently checked immutable fixture bytes;
        # production load() still validates the exact file on every operation.
        with patch.object(c,'load',return_value=plan):
            for order in itertools.permutations(rows):
                result=c.complete_selection(list(order))
                self.assertEqual('COMPLETE_SELECTION_NOT_QUALIFIED',result['status'])
                self.assertFalse(result['qualified']);self.assertFalse(result['paidCloud'])
        for name in c.MEMBERS:self.assertEqual(name,c.selection(binding(),name,'1'*32)['member']['name'])

    def test_unknown_partial_or_forged_qualification_cannot_become_a_selection(self):
        for name in ('canonical','canonical-0','canonical-4','healthy','experiment-extra',None):
            with self.subTest(name=name),self.assertRaises(ValueError):c.member(name)
        for mutate in (lambda v:v['member']['histories'].pop(),lambda v:v['member'].__setitem__('reads',1),
                       lambda v:v.__setitem__('qualified',True),lambda v:v.__setitem__('status','PASS'),
                       lambda v:v.__setitem__('paidCloud',True),lambda v:v['member']['profiles'].clear()):
            row=selections()[2];mutate(row)
            with self.assertRaises(ValueError):c.validate_selection(row)

    def test_incomplete_duplicate_and_mixed_sets_are_rejected(self):
        rows=selections()
        with self.assertRaisesRegex(ValueError,'incomplete'):c.complete_selection(rows[:-1])
        with self.assertRaisesRegex(ValueError,'incomplete'):c.complete_selection(rows+rows[:1])
        duplicate=copy.deepcopy(rows);duplicate[-1]=copy.deepcopy(rows[0]);duplicate[-1]['attempt']='9'*32
        with self.assertRaisesRegex(ValueError,'reused'):c.complete_selection(duplicate)
        duplicate=copy.deepcopy(rows);duplicate[-1]['attempt']=duplicate[0]['attempt']
        with self.assertRaisesRegex(ValueError,'reused'):c.complete_selection(duplicate)
        for field in ('source','checkoutSha256','sequence','buildManifestSha256','packageSha256'):
            changed=copy.deepcopy(rows);changed[-1]['binding'][field]='f'*len(changed[-1]['binding'][field])
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'mixed'):c.complete_selection(changed)

    def test_digest_shape_closed_fields_and_frozen_program_controls_are_required(self):
        for field in c.BINDING_FIELDS:
            for wrong in ('',None,True,'g'*64):
                value=binding();value[field]=wrong
                with self.subTest(field=field,wrong=wrong),self.assertRaises(ValueError):c.validate_binding(value)
        value=binding();value['unused']='x'
        with self.assertRaisesRegex(ValueError,'fields'):c.validate_binding(value)
        for field in ('suiteSha256','programSha256','controlsManifestSha256'):
            value=binding();value[field]='f'*64
            with self.assertRaisesRegex(ValueError,'plan/control drift'):c.validate_binding(value)
        for attempt in ('',None,True,'f'*31,'F'*32):
            with self.assertRaisesRegex(ValueError,'attempt'):c.selection(binding(),'experiment',attempt)

    def test_plan_hash_and_derived_profiles_both_detect_drift(self):
        value=copy.deepcopy(c.load());value['histories']['candidate-stale-r1']['profile']['durationNanos']=1
        with self.assertRaisesRegex(ValueError,'unreviewed'):c.validate(value)
        with patch.object(c,'PLAN_SHA',c.digest(c.encoded(value))):
            with self.assertRaisesRegex(ValueError,'program drift'):c.validate(value)
        value=copy.deepcopy(c.load());value['execution']['workloadRetries']=1
        with self.assertRaisesRegex(ValueError,'unreviewed'):c.validate(value)

    def test_returned_selections_do_not_mutate_input_binding_or_frozen_plan(self):
        owner=binding();original=copy.deepcopy(owner);row=c.selection(owner,'experiment','1'*32)
        row['binding']['source']='f'*40;row['member']['histories'].clear()
        self.assertEqual(original,owner);self.assertEqual(5,len(c.member('experiment')['histories']))


if __name__=='__main__':unittest.main()
