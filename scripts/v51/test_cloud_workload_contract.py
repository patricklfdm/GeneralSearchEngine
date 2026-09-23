"""Cloud workload arithmetic and closure, without cloud credentials or a runner."""
import copy
import unittest
from . import cloud_workload_contract as c, performance_model as m


class CloudContractTest(unittest.TestCase):
    def setUp(self):self.plan=c.load()

    def test_full_plan_counts_and_budget(self):
        r=c.validate(self.plan)
        self.assertFalse(r['paidAdmission']);self.assertEqual(5400,r['allocatedSeconds'])
        self.assertEqual(1368,r['canonicalScheduledCallsMaximum']);self.assertEqual(27,r['maximumVmHours'])
        self.assertEqual(4050,r['maximumDiskGiBHours']);self.assertEqual(dict(experiment=4,failureDrill=12,canonical=15),r['presetCellCounts'])
        self.assertEqual((260,208,52,212,68),tuple(r['workloads']['healthy'][k] for k in ('calls','mutations','reads','finalSequence','peakDocuments')))

    def test_every_canonical_call_is_scheduled_once_without_catchup(self):
        for cell,expected in [('healthy',260),('read-heavy',120),('sustained',180)]:
            rows=list(c.program(self.plan,cell));self.assertEqual(expected,len(rows))
            self.assertEqual(len(rows),len({(r['window'],r['lane'],r['dueMillis']) for r in rows}))
            self.assertTrue(all(r['dueMillis']>=0 for r in rows))
        rows=list(c.program(self.plan,'sustained'))
        self.assertEqual([0]*4,[r['dueMillis'] for r in rows[:4]])
        self.assertEqual([0,1,2,3],[r['lane'] for r in rows[:4]])

    def test_sustained_lanes_have_disjoint_keys_and_complete_lifecycles(self):
        rows=list(c.program(self.plan,'sustained'));seen=set()
        for lane in range(4):
            own=[r for r in rows if r['lane']==lane]
            self.assertEqual(['ADD','UPDATE','GET','QUERY','REMOVE']*9,[r['operation'] for r in own])
            keys={r['keys'][0] for r in own if r['keys']};self.assertFalse(keys&seen);seen|=keys
        self.assertEqual(64,c.projection(self.plan,'sustained')['finalDocuments'])

    def test_all_mutations_fit_existing_independent_decoder(self):
        for cell in ('healthy','read-heavy','sustained'):
            for row in c.program(self.plan,cell):
                if row['operation'] in m.OP_IDS:m.decode_command(m.OP_IDS[row['operation']],row['payload'])
        self.assertEqual(76,c.projection(self.plan,'healthy','experiment')['finalSequence'])

    def test_unknown_or_changed_plan_is_not_admitted_even_with_valid_json(self):
        for change in (lambda v:v.update(paidAdmission=True),lambda v:v.update(extra='unreviewed'),
                       lambda v:v['scheduler'].update(catchUp=True),lambda v:v['corpus'].update(documents=65),
                       lambda v:v['environment'].update(imageId='1')):
            value=copy.deepcopy(self.plan);change(value)
            with self.assertRaisesRegex(ValueError,'unreviewed'):c.validate(value)

    def test_independent_arithmetic_rejects_drift_without_relying_on_pin(self):
        changes=[lambda v:v['budgets'].update(cleanupSeconds=0),lambda v:v['cells'][0].update(seconds=901),
                 lambda v:v['cells'].pop(),lambda v:v['faultProgram'].update(logicalSlotsMaximum=192),
                 lambda v:v['presets']['failureDrill']['cells'].pop(),lambda v:v['evidence'].update(parts=255),
                 lambda v:v['environment'].update(voters=4),lambda v:v['automaticPolicy'].update(operationTimeoutMillis=10000),
                 lambda v:v['sustained'].update(seconds=176),lambda v:v['healthy'].update(modeSeconds=200)]
        for change in changes:
            value=copy.deepcopy(self.plan);change(value)
            with self.subTest(value=value),self.assertRaises(ValueError):c.audit(value)

    def test_static_projection_is_not_a_concurrent_linearizability_receipt(self):
        r=c.validate(self.plan)
        self.assertEqual('cloud-workload-contract-only',r['execution']);self.assertFalse(r['paidAdmission'])
        self.assertEqual(90,r['workloads']['read-heavy']['reads']);self.assertEqual(72,r['workloads']['sustained']['reads'])


    def test_retained_calibration_matches_the_exact_proposal_and_claims_no_cloud_run(self):
        value=m.strict_json(c.PLAN.with_name('phase6-cloud-calibration.json').read_bytes())
        self.assertEqual(c.PLAN_SHA256,value['planSha256'])
        self.assertEqual(c.validate(self.plan),value['arithmetic'])
        self.assertFalse(value['cloudExecution']);self.assertFalse(value['cloudScheduleExecuted']);self.assertFalse(value['paidAdmission'])
        self.assertFalse(value['encodings']['fullRuntimeRetentionQualified'])
        self.assertEqual(512,value['encodings']['slots'])
        self.assertEqual(value['source'],value['githubEvidence']['source'])
