"""Fail closed on missing physical authority, observation gaps and scope drift."""
from pathlib import Path
import base64
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import carried_transition_network as m
from . import test_joining_connections as fixture


class CarriedTransitionNetworkTest(unittest.TestCase):
    def test_basic_history_requires_connections_instead_of_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'events.json').write_text('[]');(root/'wire.json').write_text('[]')
            with patch.object(m.network,'replay') as old,self.assertRaisesRegex(ValueError,'original connection observations absent'):
                m.replay(root,'INTENT')
            old.assert_not_called()

    def test_connection_mutations_reject_overlapping_late_terminal_on_exact_socket(self):
        for name in m.network.profile_network.TERMINAL_NEGATIVES:
            events,wires,ids,identity=fixture.joined()
            result=m.connected.connections.replay(events,wires,ids,identity)
            with self.subTest(case=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'events.json').write_bytes(m.network.f.canonical(events));(root/'wire.json').write_bytes(m.network.f.canonical(wires))
                with patch.object(m,'failed_attempts',return_value=(events,result)):m.mutate(root,'INTENT',name)
                changed,wire=m.observations(root)
                with self.assertRaises(ValueError) as caught:m.connected.connections.replay(changed,wire,ids,identity)
                self.assertEqual(m.NEGATIVES[name],str(caught.exception))

    def test_excess_attempts_use_distinct_invocations_to_reach_actual_bound(self):
        events,wires,ids,identity=fixture.joined();events.pop(7);wires.pop(0)
        result=m.connected.connections.replay(events,wires,ids,identity);failed=result['failed'][0]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'events.json').write_bytes(m.network.f.canonical(events));(root/'wire.json').write_bytes(m.network.f.canonical(wires))
            (root/'failures.json').write_bytes(m.network.f.canonical([dict(node=failed['recipient'],kind=failed['kind'],request=failed['requestHash'],failure='original')]))
            with patch.object(m,'failed_attempts',return_value=(events,result)):m.mutate(root,'INTENT','failed-control-over-attempts')
            changed,wire=m.observations(root)
            replay=m.connected.connections.replay(changed,wire,ids,identity)
            self.assertEqual(4,replay['attempts'])
            with self.assertRaisesRegex(ValueError,'bounded total attempts'):m.network.bounded_attempts(changed)

    def test_exact_kind_precedes_filesystem(self):
        for kind in ('BARRIER','DATA','',None,True):
            with patch.object(m.network.collection,'inventory') as inventory,self.assertRaisesRegex(ValueError,'exact kind'):
                m.validate('/unused',kind)
            inventory.assert_not_called()

    def test_old_entry_index_selects_complete_unsplit_lifetime(self):
        for kind,indices in (('INTENT',(5,6,7)),('FINAL',(6,7))):
            with patch.object(m.network,'History') as history:m.history('/original',kind)
            history.assert_called_once_with('/original','4-REMOVE',indices=indices)
        for indices in ((7,),(5,7),[5,6,7],(True,6,7),(4,5,6,7)):
            with patch.object(m.network.c,'inventory') as inventory,self.assertRaisesRegex(ValueError,'original slot indices'):
                m.network.History('/unused','4-REMOVE',indices=indices)
            inventory.assert_not_called()

    def test_invalid_physical_original_never_enters_network(self):
        with patch.object(m.network.collection,'inventory',return_value={}),patch.object(m.physical,'validate',side_effect=ValueError('bad original')),\
             patch.object(m,'replay') as replay,self.assertRaisesRegex(ValueError,'^bad original$'):
            m.validate('/original','INTENT')
        replay.assert_not_called()

    def test_pass_preserves_remaining_scope_and_checks_original_unchanged(self):
        for inventory in ([{},{}],[{},dict(changed=True)]):
            with patch.object(m.network.collection,'inventory',side_effect=inventory),patch.object(m.physical,'validate',return_value={'original':True}),\
                 patch.object(m,'replay',return_value={'network':True}):
                if inventory[-1]:
                    with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original','FINAL')
                else:
                    result=m.validate('/original','FINAL');self.assertEqual('PARTIAL',result['status'])
                    for field in ('completeExportAuthorityQualified','maintenanceCompositionQualified','processDeathQualified','publicReady','phase3Complete'):
                        self.assertIs(result[field],False)
                    self.assertIs(result['observedAttemptsQualified'],True);self.assertIs(result['durableActivationAndSlotACKsQualified'],True)

    def test_failed_original_prevents_negative_credit(self):
        with patch.object(m,'validate',side_effect=ValueError('bad original')),patch.object(m.network,'mutate') as mutate,\
             self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('/original','FINAL')
        mutate.assert_not_called()

    def test_replay_workers_are_bounded_before_original_or_execution(self):
        for workers in (0,5,True,1.5,'2'):
            with patch.object(m,'validate') as original,patch.object(m,'ProcessPoolExecutor') as pool,\
                 self.assertRaisesRegex(ValueError,'replay workers'):m.qualify('/original','FINAL',workers=workers)
            original.assert_not_called();pool.assert_not_called()

    def test_changed_physical_file_and_unrelated_error_cannot_count(self):
        before=dict(files={'owner/selector.gsr':'original'},directories=['owner'])
        for after,error,reason in ((dict(files={'owner/selector.gsr':'changed'},directories=['owner']),None,'negative changed physical'),
                                   (before,ValueError('other'), 'unrelated network negative'),(before,None,'mutation accepted')):
            with tempfile.TemporaryDirectory() as temp,patch.object(m,'validate',return_value={}),\
                 patch.object(m.network.collection,'inventory',side_effect=[before,after]),patch.object(m,'mutate'),\
                 patch.object(m,'replay',side_effect=error),patch.object(m,'NEGATIVES',{'one':'expected'}):
                with self.assertRaisesRegex(ValueError,reason):m.qualify(temp,'INTENT')

    def test_missing_native_requests_cannot_be_inferred_from_responses(self):
        # The complete response parser has already bound an original reply,
        # but no original send or receive observation exists for it.
        row=dict(requestHash='r',responseHash='a',offered=0)
        with patch.object(m.network.transcript.phase,'exchanges',return_value=[row]),self.assertRaisesRegex(ValueError,'response without request'):
            m.network.transcript.causal([dict(event='WIRE_RESPONSE')],[],{},'root')

    def test_early_promise_mutation_tracks_actual_receiver_not_first_voter(self):
        shared=m.network.shared
        for receiver in ('node-2','node-3'):
            for unrelated_first in (False,True):
                with tempfile.TemporaryDirectory() as temp:
                    root=Path(temp);response=base64.b64encode(b'original reply').decode()
                    own=dict(node=receiver,event='BASIS_FORCED')
                    other=dict(node='node-3' if receiver=='node-2' else 'node-2',event='BASIS_FORCED')
                    reply=dict(node=receiver,event='WIRE_RESPONSE',response=shared.sha(b'original reply'))
                    events=([other,own] if unrelated_first else [own,other])+[reply]
                    (root/'events.json').write_bytes(shared.f.canonical(events))
                    (root/'wire.json').write_bytes(shared.f.canonical([dict(request='request',response=response,withheld=False)]))
                    with patch.object(shared,'wire',return_value=('PREPARE',dict(recipient=dict(node=receiver)))):
                        shared.mutate(root,'early-promise')
                    changed=json.loads((root/'events.json').read_text())
                    self.assertEqual(changed.index(reply)+1,changed.index(own))
                    self.assertEqual([v for v in events if v is not reply],[v for v in changed if v!=reply])

    def test_status_windows_end_after_the_actual_number_of_rounds(self):
        history=SimpleNamespace(root=Path('/unused'),phases=[{},{}],published={(1,'node-1'):{'cut':6},(2,'node-1'):{'cut':7}})
        physical={(i,'node-1'):dict(PUBLICATION_SELECTOR_FORCED=i*10,PUBLICATION_BEFORE_RETURN=i*10+1) for i in (1,2)}
        def current(files):return '',{},dict(capsule=dict(cut=dict(index=files['cut'])))
        request=dict(recipient=dict(node='node-1'),payload=dict(nonce='n'))
        row=dict(kind='STATUS_PROBE',answer='STATUS',request=request,response=dict(payload=dict(nonce='n',cut=dict(index=7),ready=False)),received=25,offered=26)
        with patch.object(m.network.c,'inventory',return_value={'cut':5}),patch.object(m.network.c,'current',side_effect=current):
            self.assertEqual({'boundStatusReplies':1},m.network.statuses([row],history,physical))
            row['received']=row['offered']=5
            with self.assertRaisesRegex(ValueError,'original status window'):m.network.statuses([row],history,physical)


if __name__=='__main__':unittest.main()
