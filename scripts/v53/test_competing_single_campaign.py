"""Synthetic claims only; native evidence is checked separately by the reader."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import competing_single_campaign as m
from . import competing_export_evidence as exports


def fixture():
    ballot=dict(counter=1,proposer='node-2',incarnation='storage-2');nodes=['node-1','node-2','node-3']
    caps=[dict(node=n,ballot=dict(ballot),basisId=n,basisSha256=n+'-basis') for n in nodes[:2]]
    selected=dict(ballot=dict(ballot),sources=[dict(voter=c['node'],basisId=c['basisId'],basisDigest=c['basisSha256']) for c in caps])
    owners={}
    for node in nodes:
        events=['START','ROUND_BEGIN']+(['READY'] if node=='node-2' else [])+['CLOSE','SESSION_CLOSED','TERMINATED','DRAINED']
        owners[node]=[dict(node=node,event=e,rounds=int(i>0),pending=0,afterEvent=0 if i<2 else 30) for i,e in enumerate(events)]
    return dict(nodes=nodes,stop=30,allocations=[dict(node='node-2',ballot=dict(ballot),start=1,end=7)],captures=caps,
        selections=[dict(raw=b'original-selection',value=selected)],
        bindings=[dict(node=n,selection=m.p.sha(b'original-selection'),forced=10+i) for i,n in enumerate(nodes[:2])],
        campaigns=[dict(kind='STATUS_PROBE',request=dict(sender=dict(node='node-2')))],owners=owners)


class CompetingSingleCampaignTest(unittest.TestCase):
    def test_idle_sessions_are_not_losing_campaigns_or_votes(self):
        value=fixture();before=copy.deepcopy(value);result=m.bind(value)
        self.assertEqual(before,value)
        self.assertEqual(dict(winner='node-2',automaticOwners=3,nativeCampaigns=1,selectedVoters=['node-1','node-2'],
            idleAutomaticSessions=['node-1','node-3'],competingLossQualified=False),result)

    def test_every_negative_rejects_for_its_own_reason(self):
        for name,reason in m.NEGATIVES.items():
            value=fixture();m.mutate(value,name)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^'+reason+'$'):m.bind(value)

    def test_selected_grants_and_both_forces_cannot_be_invented(self):
        for change in (lambda v:v['captures'][0].update(node='node-2'),
                       lambda v:v['bindings'][0].update(node='node-3'),
                       lambda v:v['bindings'][0].update(forced=v['stop']),
                       lambda v:v['selections'][0]['value']['sources'][0].update(basisId='foreign')):
            value=fixture();change(value)
            with self.assertRaises(ValueError):m.bind(value)

    def test_idle_session_must_begin_before_activation_and_close_after_it(self):
        for node in fixture()['nodes']:
            value=fixture();value['owners'][node][1]['afterEvent']=value['stop']
            with self.assertRaisesRegex(ValueError,'original owner interval'):m.bind(value)
            value=fixture();next(r for r in value['owners'][node] if r['event']=='CLOSE')['afterEvent']=29
            with self.assertRaisesRegex(ValueError,'original owner interval'):m.bind(value)

    def test_bad_original_or_lifecycle_never_runs_negative_mutations(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(exports.Replay,'run',side_effect=ValueError('bad original')),\
                patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):m.qualify(Path(temp))
            mutate.assert_not_called()
        with tempfile.TemporaryDirectory() as temp,patch.object(exports.Replay,'run',return_value={}),\
                patch.object(m.life,'validate',side_effect=ValueError('bad lifecycle')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad lifecycle'):m.qualify(Path(temp))
            mutate.assert_not_called()
