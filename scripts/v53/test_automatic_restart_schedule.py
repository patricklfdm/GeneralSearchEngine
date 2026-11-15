"""Synthetic schedule/request guards; these do not replace native histories."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_restart_schedule as m
from .test_automatic_restart_lifecycle import fixture,bind


def history(count):
    return [dict(node='node-1',event='ROUND_'+v) for v in
            ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']*count+['SLOT_BEGIN','SLOT_COMPLETE']]


class AutomaticRestartScheduleTest(unittest.TestCase):
    def test_two_sessions_can_include_one_bounded_reconciliation(self):
        for count in (2,3):
            result=m.stages(history(count))
            self.assertEqual(2*count+1,len(result))
            self.assertEqual('published-'+str(count+1),result[-1][2])
            self.assertEqual([-1]+[v[1] for v in result[:-1]],[v[0] for v in result])
        for count in (0,1,4):
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'bounded campaigns'):m.stages(history(count))
        for event in ('ROUND_SLOT_BEGIN','ROUND_BEFORE_READY','ROUND_INSTALLED'):
            rows=history(3);rows.remove(next(v for v in rows if v['event']==event))
            with self.subTest(event=event),self.assertRaises(ValueError):m.stages(rows)

    def test_original_failure_stops_before_request_or_negative_replay(self):
        with patch.object(m.current.physical,'validate',side_effect=ValueError('invalid original')),patch.object(m,'sends') as sends:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.validate('unused')
            sends.assert_not_called()

    def test_requests_require_ordered_anchors_identities_and_bounded_attempts(self):
        cat=m.f.catalog();q=m.f.sample(cat['wire']['STATUS_PROBE']['schema'],cat['types'])
        q['sender']['node']='node-1';q['recipient']['node']='node-2'
        identities={v['node']:v for v in (q['sender'],q['recipient'])}
        def encoded(value):return base64.b64encode(m.f.encode('wire','STATUS_PROBE',value)).decode()
        row=dict(afterEvent=0,bytes=encoded(q));events=history(2)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def read(rows,entries=()):
                (root/'restart-sends.json').write_bytes(m.f.canonical(rows));return m.sends(root,events,entries,identities)
            self.assertEqual(1,len(read([row])))
            for rows in ([],[row]*4,[dict(row,afterEvent=True)],[dict(row,afterEvent=len(events))],
                         [dict(row,afterEvent=1),row],[dict(row,extra=True)]):
                with self.subTest(rows=rows),self.assertRaises(ValueError):read(rows)
            other=copy.deepcopy(q);other['sender']=other['recipient']
            with self.assertRaisesRegex(ValueError,'send identity'):read([dict(row,bytes=encoded(other))])
            response=dict(row=dict(request=row['bytes']),kind='STATUS_PROBE',request=q,offered=1)
            read([row],[response])
            response['offered']=0
            with self.assertRaisesRegex(ValueError,'response without original send'):read([row],[response])

    def test_optional_unused_source_vectors_require_actual_derived_presence(self):
        for count in range(4):
            cases,absent=m.negative_cases(dict(unusedSourcePulls=count))
            self.assertEqual(count>0,'unused-offer-bytes' in cases)
            self.assertEqual(count==0,'unused-offer-bytes' in absent)
            self.assertTrue({'control-profile','send-missing','send-owner','send-retries'}<=set(cases))
        for count in (False,True,None,-1,4,'1'):
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'derived unused sources'):
                m.negative_cases(dict(unusedSourcePulls=count))

    def test_third_native_campaign_does_not_create_another_owner_session(self):
        events,capture,rows=fixture()
        # The synthetic fixture's last operation now contains an internal
        # installation; clocks and the two observed READY callbacks stay bound.
        events.insert(7,dict(node='node-1',event='ROUND_INSTALLED'))
        for row in rows:
            if row['afterEvent']==7:row['afterEvent']=8;row['nanoTime']+=100
        capture['events']=[dict(index=i,nanoTime=100*i,sha256=m.e.digest(m.f.canonical(e))) for i,e in enumerate(events) if i]
        capture['eventsSha256']=m.e.digest(m.f.canonical(events))
        result=bind(events,capture,rows)
        self.assertEqual(2,result['state']['rounds']);self.assertEqual([2,6],result['state']['readyCallbacks'])
        events.insert(7,dict(node='node-1',event='ROUND_INSTALLED'))
        capture['events']=[dict(index=i,nanoTime=100*i,sha256=m.e.digest(m.f.canonical(e))) for i,e in enumerate(events) if i]
        capture['eventsSha256']=m.e.digest(m.f.canonical(events))
        for row in rows:
            if row['afterEvent']==8:row['afterEvent']=9;row['nanoTime']+=100
        with self.assertRaisesRegex(ValueError,'new session before native reactivation'):bind(events,capture,rows)


if __name__=='__main__':unittest.main()
