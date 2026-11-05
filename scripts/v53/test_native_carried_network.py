import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_network as m
from . import test_node_owner_network as fixture


class NativeCarriedNetworkTest(unittest.TestCase):
    def phases(self):
        boundaries=[(-1,4),(4,9),(9,14),(14,19),(19,24)]
        events=[dict(incarnation=1 if i<9 else 2) for i in range(24)]
        rows={str(i):[dict(at=start+1,received=start+2,response=start+3)] for i,(start,stop) in enumerate(boundaries)}
        return rows,boundaries,events

    def test_all_five_phases_bind_every_sender_receiver_and_reply_to_its_group_life(self):
        rows,bounds,events=self.phases();m.request_phases(rows,bounds,events)
        for key in ('at','received','response'):
            altered=deepcopy(events);altered[rows['2'][0][key]]['incarnation']=1
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'wrong group lifetime'):
                m.request_phases(rows,bounds,altered)

    def test_response_and_read_cannot_cross_death_or_completed_phase(self):
        for phase in ('0','1','2','3'):
            for key in ('received','response'):
                rows,bounds,events=self.phases();rows[phase][0][key]=bounds[int(phase)][1]+1
                with self.subTest(phase=phase,key=key),self.assertRaisesRegex(ValueError,'crosses phase or death'):
                    m.request_phases(rows,bounds,events)

    def test_silent_attempt_is_not_promoted_to_received_or_answered(self):
        rows,bounds,events=self.phases();rows['1'][0].update(received=None,response=None)
        m.request_phases(rows,bounds,events)
        self.assertIsNone(rows['1'][0]['received']);self.assertIsNone(rows['1'][0]['response'])

    def test_original_reply_cannot_arrive_in_the_replacement_process(self):
        rows,bounds,events=self.phases()
        m.request_phases(rows,bounds,events,[dict(offered=3,deliveries=[7])])
        with self.assertRaisesRegex(ValueError,'delivery crosses group death'):
            m.request_phases(rows,bounds,events,[dict(offered=3,deliveries=[10])])

    def test_request_at_cut_or_outside_history_is_rejected(self):
        for at in (-1,4,9,14,19,24,25):
            rows,bounds,events=self.phases();rows['0'][0]['at']=at
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'outside history'):m.request_phases(rows,bounds,events)

    def test_physical_process_failure_precedes_wire_or_negative_interpretation(self):
        with patch.object(m.process,'validate',side_effect=ValueError('bad original')),patch.object(m,'replay') as replay, \
                patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('unused')
            replay.assert_not_called();copied.assert_not_called()

    def test_full_wire_component_does_not_admit_phase_or_cohort(self):
        with patch.object(m.process,'validate',return_value={'cut':m.p.CUTS[0],'status':'PARTIAL'}), \
                patch.object(m,'replay',return_value={'fullWireReplay':True}):
            result=m.validate('unused')
        self.assertEqual('PASS',result['status']);self.assertTrue(result['processHistoryQualified'])
        for key in ('phase3Complete','cohortAdmitted','powerLoss','publicRuntime'):self.assertIs(False,result[key])

    def test_snapshot_aliases_keep_all_original_lives_and_distinct_slots(self):
        root=Path('/original');view=m.View(root)
        names={'selected-1.gsr':'life-1-installed-1.gsr','selected-2.gsr':'life-2-installed-1.gsr',
            'installed-1':'life-1-installed-1','installed-2':'life-2-installed-1',
            'before-reopen':'life-2-opened','published-1':'life-2-published-1',
            'applied-2':'life-2-applied-2','at-cut':'at-cut','wire.json':'wire.json'}
        self.assertEqual({k:root/v for k,v in names.items()},{k:view/k for k in names})

    def test_heartbeat_schedule_rejects_foreign_or_ambiguous_physical_stages_before_io(self):
        invalid=[{},[],{True:'installed-1'},{-1:'installed-1'},{5:'installed-1'},
                 {1:'installed-1',0:'published-1'},{0:'installed-../other'},
                 {0:'published-0'},{0:'published-01'},{0:'copied-1'},{0:1}]
        for stages in invalid:
            with self.subTest(stages=stages),patch.object(m.a,'group') as group:
                with self.assertRaisesRegex(ValueError,'physical stage schedule'):
                    m.current.heartbeats(None,[],[],{},[(-1,1)]*5,stages=stages)
                group.assert_not_called()

    def test_network_mutation_keeps_bytes_digests_and_child_views_consistent(self):
        request,identities,send,received,_=fixture.NodeOwnerNetworkTest().fixture()
        answer=dict(request,sender=request['recipient'],recipient=request['sender'],
                    payload=dict(cut=m.f.sample(m.f.catalog()['types']['cut'],m.f.catalog()['types']),nonce=request['payload']['nonce'],ready=False))
        reply=m.f.encode('wire','STATUS',answer);rhash=m.e.digest(reply)
        send['incarnation']=1;received['incarnation']=1
        response=dict(event=dict(node=received['node'],incarnation=1,event='WIRE_RESPONSE',request=send['request'],response=rhash),
                      wire=dict(request=send['bytes'],response=base64.b64encode(reply).decode(),withheld=False))
        messages=[dict(action='event',value=send),dict(action='event',value=received),dict(action='response',value=response),
                  dict(action='event',value=dict(node=send['node'],incarnation=1,event='NETWORK_RECEIVED',kind='STATUS',response=rhash))]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'process').mkdir()
            m.process.write_messages(root/'process/life-1.jsonl',messages)
            m.process.write_messages(root/'process/life-2.jsonl',[dict(action='started',value={})])
            m.mutate(root,'network-discovery-cut')
            changed=m.process.process.transcript(root/'process/life-1.jsonl')
            wire=m.process.read(root/'wire.json');self.assertEqual(1,len(wire))
            raw=base64.b64decode(wire[0]['response']);self.assertEqual(99,m.f.decode(raw,'wire','STATUS')['payload']['cut']['index'])
            self.assertEqual(m.e.digest(raw),changed[2]['value']['event']['response'])
            self.assertEqual(m.e.digest(raw),changed[3]['value']['response'])
            self.assertEqual([v['value'] if v['action']=='event' else v['value']['event'] for v in changed],
                             m.process.read(root/'events.json')[:-1])

    def test_all_original_process_negatives_remain_mandatory(self):
        for point in m.p.CUTS:
            cases=m.negative_cases(point);original=m.process.negative_cases(point)
            self.assertEqual(original,{k:cases[k] for k in original})
            self.assertTrue(set(m.NETWORK_NEGATIVES)<=set(cases))
            self.assertEqual(point!='APPLY_ACK_DIRECTORY_FORCED','network-pregrant-retirement' in cases)


if __name__=='__main__':unittest.main()
