"""Profile dispatch and rejection integrity; native executions are separate."""
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from . import joining_profile_network_evidence as e
from .test_joining_attempts import failed_trace
from .test_joining_proposer_installations import INSTALLATION


class JoiningProfileNetworkEvidenceTest(unittest.TestCase):
    def installation(self,profile,change_scope=False):
        size,kind,old,new=e.topology(profile);joining=new[-1];n=e.network
        selected=n.f.sample(n.f.catalog()['records']['SELECTED']['schema'],n.f.catalog()['types'])
        names=[*old[:size//2+1],joining];selected['cut']['index']=9
        selected['sources']=[dict(voter=node,basisId='00000000-0000-0000-0001-'+str(i+1).zfill(12),basisDigest=str(i+1)*64) for i,node in enumerate(names)]
        selected['ballot']['proposer']='node-1';raw=n.f.encode('records','SELECTED',selected);digest=n.sha(raw)
        replay=SimpleNamespace(joining=joining,phases=[{'SELECTED':raw}])
        bases={v['basisDigest']:dict(node=v['voter'],basisId=v['basisId'],ballot=selected['ballot'],capturedEvent=0) for v in selected['sources']}
        members={'selected.gsr':raw,'original.image':b'conditional'}
        events=[dict(event='CAPTURED'),*[dict(node='node-1',event=point) for point in
            ('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN')]]
        rows=[dict(kind='PREPARE',request=dict(sender=dict(node='node-1')),
                   response=dict(payload=dict(basis=v['basisDigest'])),delivered=0)
              for v in selected['sources'] if v['voter']!='node-1']
        for node in names[1:]:
            sent=len(events);events.append(dict(event='SEND'));received=len(events);events.append(dict(event='READ'))
            sequence=['SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN',*INSTALLATION]
            for event in sequence:
                row=dict(node=node,event=event)
                if node==joining:row['scope']='wrong-owner' if change_scope else 'continuation-owner'
                events.append(row)
            offered=len(events);events.append(dict(event='REPLY'))
            delivered=len(events);events.append(dict(event='DELIVERED'))
            rows.append(dict(kind='SELECTED',answer='INSTALL_ACK',sent=sent,received=received,offered=offered,delivered=delivered,
                request=dict(sender=dict(node='node-1'),recipient=dict(node=node),ballot=selected['ballot'],view=selected['view'],payload=dict(selection=digest)),
                response=dict(payload=dict(selection=digest,cut=selected['cut']))))
        events.extend(dict(node='node-1',event=p) for p in [*INSTALLATION,'ACCEPT_VALIDATED'])
        with patch.object(n.disk,'inventory',side_effect=lambda p:p) as inventory, \
             patch.object(n.disk,'current',return_value=('',members,{})):
            result=n.installations('/original',events,rows,replay,bases)
        return result,[str(v.args[0]) for v in inventory.call_args_list],joining,len(names)

    def test_installation_uses_each_profiles_actual_joining_identity_and_snapshot(self):
        for profile in e.PROFILES:
            with self.subTest(profile=profile):
                result,paths,joining,count=self.installation(profile)
                self.assertEqual(dict(boundInstallReplies=count-1,forcedSelections=count,proposerLocalInstallations=1),result)
                self.assertIn('/original/joining-installed-9/replica',paths)
                self.assertNotIn('/original/continuation-installed-9/'+joining,paths)

    def test_another_scope_cannot_stand_in_for_the_joining_installer(self):
        for profile in e.PROFILES:
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining network selection lifetime$'):
                self.installation(profile,True)

    def test_all_five_profiles_require_physical_continuation_then_exact_network_profile(self):
        for profile in e.PROFILES:
            size,kind,_,_=e.topology(profile);order=[]
            def physical(root,chosen):order.append(('physical',chosen));return dict(status='PARTIAL')
            def network(root,**values):order.append(('network',values));return dict(slots=11)
            with self.subTest(profile=profile),patch.object(e.collection,'inventory',return_value={}), \
                 patch.object(e.continuation,'validate',side_effect=physical),patch.object(e.network,'network',side_effect=network):
                result=e.validate('/original',profile)
            self.assertEqual([('physical',profile),('network',dict(size=size,kind=kind))],order)
            self.assertEqual(profile,result['profile']);self.assertEqual('PARTIAL',result['status'])
            self.assertTrue(result['observedNetworkQualified']);self.assertTrue(result['durableACKsQualified'])
            for key in ('phase3Complete','processDeathQualified','forceAndNetworkQualified','completePhysicalQualified',
                        'completeControlExportQualified','maintenanceAndPeerCompositionQualified'):
                self.assertIs(False,result[key],key)

    def test_unknown_profile_is_rejected_before_opening_evidence(self):
        with patch.object(e.collection,'inventory') as inventory:
            for reader in (e.validate,e.qualify):
                with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):reader('/unused','5-ADD')
            inventory.assert_not_called()

    def test_failed_physical_original_cannot_supply_network_qualification(self):
        with patch.object(e.collection,'inventory',return_value={}),patch.object(e.continuation,'validate',side_effect=ValueError('physical')), \
             patch.object(e.network,'network') as network:
            with self.assertRaisesRegex(ValueError,'^physical$'):e.validate('/unused','3-REPLACE')
            network.assert_not_called()

    def test_changed_original_inventory_fails(self):
        with patch.object(e.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(e.continuation,'validate',return_value={}), \
             patch.object(e.network,'network',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining profile network original changed$'):e.validate('/unused','4-REPLACE')

    def test_original_first_prevents_any_disposable_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/unused','4-ADD')
            copied.assert_not_called()

    def negative(self, *, inventory=None, error=None, accepted=False):
        before=dict(files={'immutable': 'hash','events.json':'observation'},directories=['original'])
        with patch.object(e,'validate',return_value={}),patch.object(e,'terminal_pair',return_value=None), \
             patch.object(e.collection,'inventory',side_effect=inventory or [before,before,before]), \
             patch.dict(e.network.NEGATIVES,{'conditional':'expected rejection'},clear=True),patch.object(e.shutil,'copytree'), \
             patch.object(e,'mutate'),patch.object(e.network,'network',side_effect=None if accepted else error or ValueError('expected rejection')) as network:
            result=e.qualify('/unused','5-REPLACE')
            self.assertEqual(dict(size=5,kind='REPLACE'),network.call_args.kwargs)
            return result

    def test_each_negative_uses_the_selected_profile(self):
        result=self.negative();self.assertEqual([dict(case='conditional',status='REJECTED',reason='expected rejection')],result['negatives'])

    def test_negative_cannot_change_non_observation_storage(self):
        a=dict(files={'immutable':'one'},directories=['original']);b=copy.deepcopy(a);b['files']['immutable']='changed'
        with self.assertRaisesRegex(ValueError,'^joining profile network negative changed physical inputs$'):self.negative(inventory=[a,b])

    def test_negative_cannot_change_directories(self):
        a=dict(files={'immutable':'one'},directories=['original']);b=copy.deepcopy(a);b['directories']=[]
        with self.assertRaisesRegex(ValueError,'^joining profile network negative changed physical inputs$'):self.negative(inventory=[a,b])

    def test_wrong_rejection_is_not_counted_as_pass(self):
        with self.assertRaisesRegex(ValueError,'^joining profile unrelated network negative: conditional: unrelated$'):
            self.negative(error=ValueError('unrelated'))

    def test_accepted_mutation_is_not_counted_as_rejection(self):
        with self.assertRaisesRegex(ValueError,'^joining profile network accepted mutation: conditional$'):self.negative(accepted=True)

    def test_terminal_mutations_reject_for_their_designated_reason(self):
        for name,reason in e.TERMINAL_NEGATIVES.items():
            events,wires,ids,root=failed_trace(True)
            with self.subTest(case=name),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);(path/'events.json').write_bytes(e.f.canonical(events));e.mutate(path,name)
                changed=e.collection.read_json(path,'events.json',e.collection.EVENT_BYTES)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):e.network.causal(changed,wires,ids,root)

    def test_later_receiver_terminal_still_belongs_to_its_original_attempt(self):
        events,_,_,_=failed_trace();events[2],events[3]=events[3],events[2]
        with patch.object(e.collection,'read_json',return_value=events):
            self.assertEqual((2,3),e.terminal_pair('/original')[1:])

    def test_pair_selector_does_not_borrow_previous_attempt_terminal(self):
        events,_,_,_=failed_trace();events.pop(3);events.extend([dict(events[1],event=e.attempts.EVENT,direction='OUTBOUND',reason='IO')])
        with patch.object(e.collection,'read_json',return_value=events):self.assertIsNone(e.terminal_pair('/original'))

    def test_absent_terminals_cannot_be_fabricated_for_a_negative(self):
        with patch.object(e.collection,'read_json',return_value=[]):
            self.assertIsNone(e.terminal_pair('/original'))
            with self.assertRaisesRegex(ValueError,'^joining profile negative requires original paired terminal$'):
                e.mutate('/unused','terminal-caller-missing')


if __name__=='__main__':unittest.main()
