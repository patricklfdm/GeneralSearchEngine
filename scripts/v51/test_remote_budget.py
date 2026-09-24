import unittest
from .remote_budget import Budget


class RemoteBudgetTest(unittest.TestCase):
    def setUp(self):
        self.now = 10**9
        self.rows = []
        self.budget = Budget(clock=lambda:self.now,emit=self.rows.append)

    def advance(self, seconds): self.now += int(seconds*10**9)

    def test_control_gaps_and_in_cell_overhead_are_charged_once(self):
        self.advance(3)
        with self.budget.stage('preparation'): self.advance(20)
        self.advance(5)
        with self.budget.stage('healthy'):
            self.advance(780) # complete scheduled time
            self.advance(30)  # in-cell SSH and boundaries remain inside healthy
        with self.budget.stage('cleanup'): self.advance(12)
        result = self.budget.finish()
        self.assertEqual('PASS',result['status'])
        self.assertEqual(810*10**9,result['spentNanos']['healthy'])
        self.assertEqual(8*10**9,result['spentNanos']['control'])
        self.assertEqual(850*10**9,result['elapsedNanos'])
        self.assertEqual(result['elapsedNanos'],sum(result['spentNanos'].values()))

    def test_unused_cell_allowance_never_extends_another(self):
        with self.budget.stage('healthy'): self.advance(1)
        with self.assertRaisesRegex(ValueError,'maintenance'):
            with self.budget.stage('maintenance'): self.advance(241)
        self.assertEqual('FAIL',self.budget.finish()['status'])
        self.assertEqual(241*10**9,self.rows[-2]['elapsedNanos'])

    def test_renewal_and_collection_overrun_still_allow_cleanup(self):
        with self.assertRaises(ValueError):
            with self.budget.stage('validation-retention'): self.advance(601)
        with self.budget.stage('cleanup'): self.advance(10)
        self.assertEqual('FAIL',self.budget.finish()['status'])

    def test_lost_ssh_time_consumes_control_budget(self):
        self.advance(541)
        with self.assertRaises(ValueError):
            with self.budget.stage('healthy'): self.fail('late work admitted')
        with self.budget.stage('cleanup'): self.advance(1)
        self.assertEqual('FAIL',self.budget.finish()['status'])

    def test_no_nested_or_restartable_cell_deadlines(self):
        with self.budget.stage('leader-loss'):
            with self.assertRaises(ValueError):
                with self.budget.stage('control'): pass
        with self.assertRaises(ValueError):
            with self.budget.stage('leader-loss'): pass

    def test_whole_lease_is_not_extended_by_operation_grace(self):
        with self.assertRaises(ValueError):
            with self.budget.stage('preparation'): self.advance(5401)
        with self.assertRaises(ValueError):
            with self.budget.stage('cleanup'): self.advance(1)
        self.assertEqual('FAIL',self.budget.finish()['status'])

    def test_reserve_and_original_deadline_survive_slow_control(self):
        with self.budget.stage('maintenance') as deadline:
            self.advance(30)
            self.assertEqual(210*10**9,deadline-self.now)
            self.assertLessEqual(deadline,self.budget.start+self.budget.lease-600*10**9)

    def test_backwards_clock_is_rejected(self):
        self.now -= 1
        with self.assertRaises(ValueError): self.budget.finish()
