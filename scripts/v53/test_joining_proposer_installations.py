"""Ordinary proposers need the same complete installation as remote voters."""
import unittest
from . import joining_network_evidence as n


def fixture():
    members={'application.image':b'image','selected.gsr':b'selection'}
    names=['SELECTED_FORCED','SELECTED_BEFORE_RETURN','SEND_A','SEND_B','ACK_A','ACK_B',
           *n.install_forces(members),'ACCEPT_VALIDATED']
    events=[dict(node='node-1',event=p) for p in names]
    replies=[dict(sent=2,delivered=4),dict(sent=3,delivered=5)]
    return events,replies,members


class JoiningProposerInstallationTest(unittest.TestCase):
    def check(self,data):
        events,replies,members=data
        upper=next(i for i,v in enumerate(events) if v['event']=='ACCEPT_VALIDATED')
        n.proposer_forces(events,'node-1',None,0,upper,replies,members)

    def test_complete_force_chain_runs_after_every_original_ACK(self):self.check(fixture())

    def test_missing_or_noninteger_delivery_is_not_an_ACK(self):
        for delivered in (None,True,'5'):
            data=fixture();data[1][-1]['delivered']=delivered
            with self.assertRaisesRegex(ValueError,'^joining network proposer delivered ACKs$'):self.check(data)

    def test_late_last_peer_prevents_early_local_installation(self):
        data=fixture();data[1][-1]['delivered']=6
        with self.assertRaisesRegex(ValueError,'^joining network proposer installation after ACKs$'):self.check(data)

    def test_selection_return_precedes_first_selected_send(self):
        for change in ('missing','late'):
            data=fixture()
            if change=='missing':data[0][1]['event']='MISSING'
            else:data[1][0]['sent']=1
            with self.assertRaisesRegex(ValueError,'^joining network proposer selection return$'):self.check(data)

    def test_each_image_member_and_parent_force_is_mandatory(self):
        for point in ('INSTALL_IMAGE_FORCED','INSTALL_MEMBER_FORCED','INSTALL_GENERATION_FORCED',
                      'INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED',
                      'CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED',
                      'CURRENT_DIRECTORY_FORCED','INSTALL_BEFORE_RETURN'):
            data=fixture();next(v for v in data[0] if v['event']==point)['event']='MISSING'
            with self.subTest(point=point),self.assertRaisesRegex(ValueError,'^joining network proposer complete installation order$'):self.check(data)

    def test_duplicate_force_and_wrong_owner_scope_cannot_pass(self):
        for change in ('duplicate','scope'):
            data=fixture();events=data[0];at=next(i for i,v in enumerate(events) if v['event']=='INSTALL_MEMBER_FORCED')
            if change=='duplicate':events.insert(at,dict(events[at]))
            else:events[at]['scope']='closed-owner'
            with self.assertRaisesRegex(ValueError,'^joining network proposer complete installation order$'):self.check(data)

    def test_installation_must_finish_before_first_slot_is_accepted(self):
        data=fixture();events=data[0];at=next(i for i,v in enumerate(events) if v['event']=='INSTALL_BEFORE_RETURN')
        events.append(events.pop(at))
        with self.assertRaisesRegex(ValueError,'^joining network proposer complete installation order$'):self.check(data)

    def test_member_force_count_is_derived_from_complete_installed_inventory(self):
        data=fixture();data[2]['ancestry.gsr']=b'original'
        with self.assertRaisesRegex(ValueError,'^joining network proposer complete installation order$'):self.check(data)


if __name__=='__main__':unittest.main()
