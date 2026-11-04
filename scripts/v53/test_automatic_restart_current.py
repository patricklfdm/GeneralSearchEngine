"""Focused current restart composition; synthetic contact data is not native proof."""
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_restart_current as m


def contact_fixture():
    events=[dict(node='node-1',event='NONE') for _ in range(30)]
    stages=('installed-1','published-1','installed-2','published-2','published-3')
    boundaries=[(-1,3),(3,8),(8,13),(13,18),(18,28)]
    view=dict(old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'])
    groups={'before-network':{n:dict(capsule=dict(cut=dict(index=0))) for n in view['old']}}
    for i,stage in enumerate(stages):
        start,stop=boundaries[i];installed=stage.startswith('installed');index=[0,1,1,2,3][i]
        selected=dict(ballot=dict(counter=2 if i<2 else 4),cut=dict(view=view),sources=[dict(voter=n) for n in view['old'][:2]])
        group={n:dict(capsule=dict(cut=dict(index=index if n!='node-3' else 0)),selected=selected) for n in view['old']}
        groups[stage]=group
        for offset,node in enumerate(view['old'][:2],1):events[start+offset]=dict(node=node,event='INSTALL_SELECTOR_FORCED' if installed else 'PUBLICATION_SELECTOR_FORCED')
        if installed:events[stop]=dict(node='node-1',event='ROUND_INSTALLED')
    def row(peer,offered,delivered,cut):
        request=dict(sender=dict(node='node-1'),recipient=dict(node=peer),sequence=int(peer[-1])-1,
                     trace='contact',ballot=dict(counter=4),payload=dict(cut=dict(index=2),activated=True))
        return dict(kind='HEARTBEAT',answer='HEARTBEAT_ACK',request=request,response=dict(payload=dict(cut=dict(index=cut))),
                    row={'original':peer},offered=offered,deliveries=delivered)
    return events,[row('node-2',19,[20],2),row('node-3',19,[20],0)],boundaries,groups


def contacts(events,rows,boundaries,groups):
    with patch.object(m.network,'group',side_effect=lambda root,stage:groups[stage]), \
         patch.object(m.network.c,'current',side_effect=lambda files:('',{'selected.gsr':files.get('selected')},files)), \
         patch.object(m.network.f,'decode',side_effect=lambda raw,*args:raw):
        return m.heartbeats(Path('synthetic'),events,rows,boundaries)


class AutomaticRestartCurrentTest(unittest.TestCase):
    def test_contact_is_not_publication_and_missing_delivery_never_supplies_majority(self):
        events,rows,bounds,groups=contact_fixture();rows[0]['deliveries']=[]
        result=contacts(events,rows,bounds,groups)
        self.assertEqual(1,result['samples']);self.assertTrue(result['contactOnly']);self.assertFalse(result['completeAttemptsQualified'])
        rows[1]['deliveries']=[]
        with self.assertRaisesRegex(ValueError,'original responding majority'):contacts(events,rows,bounds,groups)

    def test_request_and_reply_cuts_are_derived_from_original_selector_positions(self):
        for part in ('request','response'):
            events,rows,bounds,groups=contact_fixture();rows[0][part]['payload']['cut']['index']=99
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'original '+part+' cut'):contacts(events,rows,bounds,groups)

    def test_contact_cannot_cross_replacement_or_hide_other_protocol_messages(self):
        for changed in ('replacement','hidden'):
            events,rows,bounds,groups=contact_fixture()
            if changed=='replacement':
                events[22]=dict(node='node-1',event='ROUND_INSTALLED');rows[0]['deliveries']=[23]
            else:rows.append(dict(rows[0],kind='PREPARE'))
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'crosses replacement|cannot hide protocol work'):
                contacts(events,rows,bounds,groups)

    def test_contact_retries_require_exact_original_bytes_and_bound(self):
        for count,alter in ((4,False),(2,True)):
            events,rows,bounds,groups=contact_fixture();extra=[copy.deepcopy(rows[0]) for _ in range(count-1)]
            if alter:extra[-1]['row']['original']='changed'
            rows+=extra
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'exact bounded retries'):contacts(events,rows,bounds,groups)

    def test_contact_must_follow_installation_and_keep_sender_sequence_and_ballot(self):
        for edit in ('early','sequence','ballot'):
            events,rows,bounds,groups=contact_fixture()
            if edit=='early':rows[0]['offered']=0
            elif edit=='sequence':rows[0]['request']['sequence']=2
            else:rows[0]['request']['ballot']['counter']=2
            with self.subTest(edit=edit),self.assertRaisesRegex(ValueError,'before installation|original request cut'):
                contacts(events,rows,bounds,groups)

    def test_unused_source_is_optional_but_never_ambiguous_or_substituted(self):
        source=dict(sender='node-1',peer='node-3',first='basis');expected=[('basis',b'bytes','RECORD')]
        for values in ([],[source]):
            phase=SimpleNamespace(sources=values)
            with patch.object(m.sources,'unused_source') as replay:
                m.unused_source(phase,expected,{},1)
                self.assertEqual(len(values),replay.call_count)
        with self.assertRaisesRegex(ValueError,'one unused source'):m.unused_source(SimpleNamespace(sources=[source,source]),expected,{},1)

    def test_diagnostic_rejection_requires_actual_first_contact(self):
        events=[dict(event='ROUND_SLOT_BEGIN')]
        with self.assertRaisesRegex(ValueError,'unused peer contact before slot'):m.rejection_reason(None,events,[],0)
        events.insert(0,dict(event='NONE'));row=dict(kind='HEARTBEAT',request=dict(sender=dict(node='node-1'),recipient=dict(node='node-3')),offered=0)
        self.assertEqual('retention intent installed selection required',m.rejection_reason(None,events,[row],0))

    def test_physical_original_failure_prevents_contact_and_retention_replay(self):
        with patch.object(m,'replay_physical',side_effect=ValueError('bad original')),patch.object(m,'heartbeats') as contact, \
                patch.object(m.confirmations,'installation_retention') as retention:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.validate('unused')
            contact.assert_not_called();retention.assert_not_called()

    def test_qualifier_rejects_bad_original_before_generating_mutations(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m,'validate',side_effect=ValueError('bad original')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify(temp)
            mutate.assert_not_called()

    def test_qualifier_does_not_count_unrelated_or_missing_rejection(self):
        for bad,reason in ((ValueError('other'),'unrelated negative'),({},'accepted negative')):
            with tempfile.TemporaryDirectory() as temp,patch.object(m,'validate',side_effect=[{},bad]),patch.object(m,'mutate'):
                with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):m.qualify(temp)

    def test_ordinary_slot_payload_and_current_maintenance_compose_without_pending_tail(self):
        service=m.Service.__new__(m.Service);service.group={'original':'bytes'};service.voters=('node-1','node-2')
        with patch.object(service,'maintenance',return_value={'derived':'bytes'}) as maintain,patch.object(service,'publish') as publish:
            service.advance('DATA')
            maintain.assert_called_once_with({'original':'bytes'},service.voters)
            self.assertEqual({'derived':'bytes'},service.group)
            kind,payload=publish.call_args.args;self.assertEqual('DATA',kind);self.assertTrue(payload.endswith(b'100:next-slot'))
        self.assertEqual([(100,'next-slot')],service.data_documents())


if __name__=='__main__':unittest.main()
