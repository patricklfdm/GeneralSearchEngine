"""Composition boundaries; full original TCP histories remain separate evidence."""
from pathlib import Path
from copy import deepcopy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remove_network_evidence as n


class RemoveNetworkEvidenceTest(unittest.TestCase):
    def unselected(self,change=None):
        ballot=dict(counter=4,proposer='node-1',incarnation='original')
        selected=dict(root='root',view='view',ballot=ballot,sources=[dict(voter='node-1'),dict(voter='node-3')])
        basis=dict(ballot=ballot,basisId='basis')
        journal=[('PROMISE',b'promise',dict(ballot=ballot)),('BASIS',b'basis',basis)]
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),ballot=ballot,view='view',payload=dict(promise=n.sha(b'proposer')))
        row=dict(kind='PREPARE',answer='PROMISE',sent=1,received=2,offered=6,delivered=7,
                 request=q,response=dict(payload=dict(basis=n.sha(b'basis'))))
        rows=[row,dict(deepcopy(row),sent=3,received=4,offered=8,delivered=None)]
        events=[dict(node='node-2',event=point) for point in
                ('begin','send','receive','CURRENT_BEFORE_CAPTURE','working','GRANT_BEFORE_RETURN','reply','delivery','reply','end')]
        if change=='selected':selected['sources'].append(dict(voter='node-2'))
        elif change=='journal':journal.append(('SELECTED',b'selected',dict(ballot=ballot)))
        elif change=='force':events[5]['event']='missing'
        elif change=='selection':events[4]['event']='SELECTED_FORCED'
        elif change=='basis':rows[0]['response']['payload']['basis']='forged'
        elif change=='duplicate':rows+=deepcopy(rows)
        elif change=='early-delivery':rows[0]['delivered']=5
        elif change=='cross-phase':rows[0]['delivered']=10
        elif change=='wrong-request':rows[1]['request']['view']='other'
        elif change=='none':
            for row in rows:row['delivered']=None
        files={'node.gsr':b'node','grants.gsr':b'journal','sources/basis/source.gscp':b'packet'}
        with patch.object(n.f,'decode',return_value=dict(identity=dict(node='node-2'))),\
                patch.object(n.c,'journal',return_value=journal),patch.object(n.c.p,'decode',return_value={}),\
                patch.object(n.shared,'grant_capture_order',return_value={3,5}) as forces:
            result=n.cancelled_grant(events,rows,files,selected,b'proposer',0,9)
            forces.assert_called_once_with(events,'node-2',None,3,5,{})
            return result

    def test_unselected_original_grant_does_not_require_a_fabricated_selection_or_delivery(self):
        self.assertEqual({3,5},self.unselected())
        self.assertEqual({3,5},self.unselected('none'))

    def test_unselected_grant_rejects_wrong_authority_missing_force_and_invalid_replies(self):
        for change in ('selected','journal','force','selection','basis','duplicate','early-delivery','cross-phase','wrong-request'):
            with self.subTest(change=change),self.assertRaises(ValueError):self.unselected(change)

    def test_invalid_profile_precedes_filesystem_and_authority(self):
        with patch.object(n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^REMOVE network profile$'):n.validate('/unused','3-REMOVE')
        inventory.assert_not_called()

    def test_physical_failure_prevents_transport_qualification(self):
        with patch.object(n.collection,'inventory',return_value={}),patch.object(n.original,'validate',side_effect=ValueError('bad physical')) as original,patch.object(n,'network') as network:
            with self.assertRaisesRegex(ValueError,'bad physical'):n.validate('/unused','5-REMOVE')
        original.assert_called_once_with(Path('/unused'),'5-REMOVE');network.assert_not_called()

    def test_success_does_not_promote_export_or_process_authority(self):
        with patch.object(n.collection,'inventory',return_value={}),patch.object(n.original,'validate',return_value={}),patch.object(n,'network',return_value={}):
            result=n.validate('/unused','4-REMOVE')
        self.assertEqual('PARTIAL',result['status'])
        for key in ('completeExportAuthorityQualified','maintenanceCompositionQualified','processDeathQualified','phase3Complete'):self.assertIs(result[key],False)
        self.assertTrue(result['observedAttemptsQualified']);self.assertTrue(result['durableActivationAndSlotACKsQualified'])

    def test_changed_original_is_not_qualified(self):
        with patch.object(n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(n.original,'validate',return_value={}),patch.object(n,'network',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):n.validate('/unused','4-REMOVE')

    def test_failed_original_prevents_negative_mutation(self):
        with patch.object(n,'validate',side_effect=ValueError('bad original')),patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):n.qualify('/unused','5-REMOVE')
        mutate.assert_not_called()

    def test_negative_physical_change_is_not_counted_as_network_rejection(self):
        before=dict(files={'original': 'a'},directories=[])
        after=dict(files={'original': 'b'},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(n,'validate',return_value={}),patch.object(n.collection,'inventory',side_effect=[before,after]),patch.object(n,'mutate'),patch.object(n,'network') as network:
            with self.assertRaisesRegex(ValueError,'negative changed physical input'):n.qualify(temp,'4-REMOVE')
        network.assert_not_called()

    def test_unrelated_negative_failure_does_not_count(self):
        before=dict(files={},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(n,'validate',return_value={}),patch.object(n.collection,'inventory',return_value=before),patch.object(n,'mutate'),patch.object(n,'network',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated network negative: missing-send: unrelated'):n.qualify(temp,'4-REMOVE')

    def test_accepted_mutation_is_failure(self):
        before=dict(files={},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(n,'validate',return_value={}),patch.object(n.collection,'inventory',return_value=before),patch.object(n,'mutate'),patch.object(n,'network',return_value={}):
            with self.assertRaisesRegex(ValueError,'mutation accepted: missing-send'):n.qualify(temp,'4-REMOVE')

    def test_remove_slots_do_not_invent_a_joining_identity(self):
        replay=SimpleNamespace(old=('node-1','node-2','node-3'),joining=None,phases=[])
        self.assertEqual({},n.phase.blocks([],replay))
        with self.assertRaisesRegex(ValueError,'unknown owner'):
            n.phase.blocks([dict(node='node-4',event='ACCEPT_VALIDATED')],replay)

    def test_future_lower_comes_from_original_ledger_not_latest_publication(self):
        history=n.History.__new__(n.History);history.applied={(3,'node-1'):{n.d.s.FILE:b'original'}}
        old=dict(cut=dict(index=5));new=dict(cut=dict(index=6))
        with patch.object(n.d.s.r,'decode',return_value=dict(plan=dict(peers=[dict(identity=dict(node='node-2'),possible=[old,new])]))):
            self.assertEqual(old,history.future_lower(3,'node-2'))

    def test_failure_diagnostic_cannot_disappear_or_invent_a_terminal(self):
        row=dict(node='node-4',kind='FUTURE_RETENTION_INTENT',request='r',failure='diagnostic')
        failed=[dict(recipient='node-4',kind='FUTURE_RETENTION_INTENT',requestHash='r',serverFailed=5)]
        for diagnostics,failures in [([],failed),([row],[]),([row,row],failed)]:
            with patch.object(n.collection,'read_json',return_value=diagnostics),self.assertRaisesRegex(ValueError,'complete failure diagnostics'):
                n.failed_controls('/unused',[],failures,SimpleNamespace(phases=[]))

    def test_actual_receiver_failure_kind_and_owner_are_bound(self):
        failed=[dict(recipient='node-4',kind='FUTURE_RETENTION_INTENT',requestHash='r',serverFailed=5)]
        for change in ({'node':'node-3'},{'kind':'PREPARE'},{'request':'other'}):
            row=dict(node='node-4',kind='FUTURE_RETENTION_INTENT',request='r',failure='diagnostic')
            row.update(change)
            with patch.object(n.collection,'read_json',return_value=[row]),self.assertRaisesRegex(ValueError,'complete failure diagnostics'):
                n.failed_controls('/unused',[],failed,SimpleNamespace(phases=[]))

    def test_failure_count_cannot_exceed_existing_attempt_limit(self):
        row=dict(node='node-4',kind='FUTURE_RETENTION_INTENT',request='r',failure='diagnostic')
        failed=[dict(recipient='node-4',kind='FUTURE_RETENTION_INTENT',requestHash='r',serverFailed=5)]*4
        with patch.object(n.collection,'read_json',return_value=[row]*4),self.assertRaisesRegex(ValueError,'bounded failed attempts'):
            n.failed_controls('/unused',[],failed,SimpleNamespace(phases=[]))

    def recovered_control(self,*,offered=True,change=None,diagnostics=None):
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),payload={'selection':'original'})
        answer=dict(payload={'selection':'original'})
        failure=dict(recipient='node-2',kind='SELECTED',requestHash='request',sent=0,
                     serverFailed=4,responseOffered=offered,clientReason='DEADLINE',serverReason='IO')
        rows=[dict(kind='SELECTED',request=q,response=answer,sent=0,delivered=None),
              dict(kind='SELECTED',request=q,response=answer,sent=5,delivered=8)]
        if not offered:rows.pop(0)
        if change:change(failure,rows)
        if diagnostics is None:
            diagnostics=[] if offered else [dict(node='node-2',kind='SELECTED',request='request',failure='handler error')]
        with patch.object(n.collection,'read_json',return_value=diagnostics),patch.object(n.transcript,'wire',return_value=('SELECTED',q)):
            return n.failed_controls('/unused',[{'bytes':'original'}],[failure],SimpleNamespace(phases=[]),rows)

    def test_post_handler_transport_failure_needs_terminal_but_no_handler_exception(self):
        self.assertEqual({'boundFailedControls':1},self.recovered_control())
        self.assertEqual({'boundFailedControls':1},self.recovered_control(offered=False))
        with self.assertRaisesRegex(ValueError,'complete failure diagnostics'):
            self.recovered_control(diagnostics=[dict(node='node-2',kind='SELECTED',request='request',failure='invented')])
        with self.assertRaisesRegex(ValueError,'complete failure diagnostics'):self.recovered_control(offered=False,diagnostics=[])

    def test_failed_control_never_supplies_vote_or_changes_retry_result(self):
        changes=[lambda failure,rows:rows.pop(),
                 lambda failure,rows:rows[-1].update(delivered=True),
                 lambda failure,rows:rows[-1].update(response={'payload':'different'}),
                 lambda failure,rows:failure.update(clientReason='CLOSED'),
                 lambda failure,rows:failure.update(serverReason='PROTOCOL')]
        for index,change in enumerate(changes):
            with self.subTest(change=index),self.assertRaisesRegex(ValueError,'failed control exact recovery'):
                self.recovered_control(change=change)

    def test_future_control_binds_governing_peer_and_distinct_sequence(self):
        selected=dict(ballot=dict(proposer='node-1'),view='v',cut=dict(view=dict(
            old=['node-1','node-2','node-3','node-4','node-5'],new=['node-1','node-2','node-3','node-4'])))
        q=dict(ballot=selected['ballot'],view='v',payload={'original':'intent'},sender=dict(node='node-1'),
            recipient=dict(node='node-4'),sequence=4)
        self.assertTrue(n.future_request_matches('FUTURE_RETENTION_INTENT',q,selected,q['payload']))
        for changes in ({'sequence':1},{'sequence':3},{'recipient':dict(node='node-6')},
                        {'recipient':dict(node='node-1')},{'sender':dict(node='node-2')},{'view':'other'}):
            self.assertFalse(n.future_request_matches('FUTURE_RETENTION_INTENT',dict(q,**changes),selected,q['payload']))

    def test_attempt_bound_counts_both_failed_and_successful_sends(self):
        send=dict(event='NETWORK_SEND',request='same-request')
        events=[dict(send),dict(event='NETWORK_ATTEMPT_FAILED'),dict(send),dict(event='WIRE_RESPONSE'),dict(send)]
        n.bounded_attempts(events)
        with self.assertRaisesRegex(ValueError,'bounded total attempts'):n.bounded_attempts(events+[send])

    def test_status_cannot_name_a_future_or_missing_original_cut(self):
        row=dict(kind='STATUS_PROBE',answer='STATUS',received=10,offered=12,
            request=dict(recipient=dict(node='node-1'),payload=dict(nonce='nonce')),
            response=dict(payload=dict(nonce='nonce',ready=False,cut=dict(index=7))))
        history=SimpleNamespace(root=Path('/unused'),phases=[{}, {}, {}],published={(1,'node-1'):{}})
        physical={(1,'node-1'):dict(PUBLICATION_SELECTOR_FORCED=20,PUBLICATION_BEFORE_RETURN=21)}
        with patch.object(n.c,'inventory',return_value={}),patch.object(n.c,'current',side_effect=lambda files:('',{},dict(capsule=dict(cut=dict(index=4))))):
            with self.assertRaisesRegex(ValueError,'original status window'):n.statuses([row],history,physical)
            row['response']['payload']['cut']=dict(index=4)
            self.assertEqual(dict(boundStatusReplies=1),n.statuses([row],history,physical))


if __name__=='__main__':unittest.main()
