"""Negative witnesses for reservation leaks, false capacity and early force claims."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from .public_pressure_evidence import reservations,delayed_force
from . import storage_fixture


class TransportAccountingTest(unittest.TestCase):
    def row(self,identity,event='OUTBOUND_ADMITTED',peer=b'2',pid=1):
        row=dict(event='TRANSPORT',transition=event,pid=pid,reservation=identity,bytes=64 if event.startswith('OUTBOUND') else 0)
        if event.startswith('OUTBOUND'):row['request']=base64.b64encode(peer*64).decode()
        return row

    def released(self,row):return dict(row,transition=row['transition'].replace('ADMITTED','RELEASED'))
    def check(self,rows):return reservations(rows,lambda value:dict(recipient=base64.b64decode(value)[:1].decode()),64)

    def test_concurrent_distinct_reservations_can_retry_identical_requests(self):
        one=self.row(1);two=self.row(2)
        result=self.check([one,two,self.released(two),self.released(one)])
        self.assertEqual(dict(inbound=0,outbound=2,bytes=128),result['peaks'])

    def test_peer_and_inbound_limits_are_independent(self):
        rows=[self.row(i+1,peer=b'2' if i<2 else b'3') for i in range(4)]
        rows += [self.row(i+5,'INBOUND_ADMITTED') for i in range(8)]
        self.assertEqual(12,self.check(rows+[self.released(r) for r in rows])['reservations'])

    def test_a_third_peer_reservation_or_ninth_inbound_is_rejected(self):
        for rows in ([self.row(i+1) for i in range(3)],[self.row(i+1,'INBOUND_ADMITTED') for i in range(9)]):
            with self.subTest(size=len(rows)),self.assertRaisesRegex(ValueError,'admission bound'):
                self.check(rows+[self.released(r) for r in rows])

    def test_missing_duplicate_or_changed_releases_are_rejected(self):
        one=self.row(1)
        for rows in ([one],[self.released(one)],[one,self.released(one),self.released(one)],
                     [one,dict(self.released(one),request=self.row(2,peer=b'3')['request'])]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.check(rows)

    def test_reusing_an_identity_after_release_is_rejected(self):
        one=self.row(1)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.check([one,self.released(one),one,self.released(one)])

    def test_new_process_can_start_its_own_reservation_sequence(self):
        one=self.row(1);two=self.row(1,pid=2)
        self.assertEqual(2,self.check([one,self.released(one),two,self.released(two)])['reservations'])

    def test_accounted_bytes_must_match_exact_wire_bytes(self):
        one=self.row(1);one['bytes']=63
        with self.assertRaisesRegex(ValueError,'byte identity'):self.check([one,self.released(one)])

    def test_capacity_rejection_never_acquires_a_reservation(self):
        one=self.row(1);two=self.row(2);rejected=dict(self.row(0,'OUTBOUND_REJECTED'),bytes=0)
        result=self.check([one,two,rejected,self.released(one),self.released(two)])
        self.assertEqual(2,result['rejected'][0]['count'])
        rejected['reservation']=3
        with self.assertRaisesRegex(ValueError,'reserved capacity'):self.check([one,rejected,self.released(one)])

    def test_empty_observations_cannot_prove_accounting(self):
        with self.assertRaisesRegex(ValueError,'missing actual'):self.check([])


class SlowForceEvidenceTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        record=storage_fixture.create(Path(temp.name))['ACCEPT'];encoded=base64.b64encode(record).decode()
        self.cut=dict(event='CUT_REACHED',pid=10,order=2,localNanos=100,cut='ACCEPT_AFTER_WRITE',mode='pause')
        self.rows=[dict(event='ACCEPT_AFTER_WRITE',pid=10,order=1,record=encoded),self.cut,
                   dict(event='CUT_RELEASED',pid=10,order=3,cut='ACCEPT_AFTER_WRITE',localNanos=1_400_000_100),
                   dict(event='FORCE',pid=10,order=4,kind='ACCEPT',record=encoded)]

    def test_complete_bytes_are_not_a_force_until_pause_released(self):
        self.assertEqual(4,delayed_force(self.rows,self.cut,'ACCEPT',1200)['firstForce']['order'])

    def test_force_before_release_or_in_another_process_is_rejected(self):
        for change in (dict(order=1),dict(order=2),dict(order=3),dict(pid=11)):
            rows=copy.deepcopy(self.rows);rows[-1].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):delayed_force(rows,self.cut,'ACCEPT',1200)

    def test_missing_actual_bytes_force_or_release_is_rejected(self):
        for removed in (0,2,3):
            rows=copy.deepcopy(self.rows);rows.pop(removed)
            with self.subTest(removed=removed),self.assertRaises(ValueError):delayed_force(rows,self.cut,'ACCEPT',1200)

    def test_short_delay_does_not_cover_the_request_deadline(self):
        rows=copy.deepcopy(self.rows);rows[2]['localNanos']=1_199_000_100
        with self.assertRaisesRegex(ValueError,'deadline'):delayed_force(rows,self.cut,'ACCEPT',1200)


if __name__=='__main__':unittest.main()
