"""Actual selection owners must not obtain credit for omitted writes."""
import unittest
from . import test_joining_proposer_installations as proposer
from . import test_joining_same_view_network as recovery


class JoiningInstallWriteChainTest(unittest.TestCase):
    def fixture(self, role):
        if role=='proposer':
            return proposer.fixture(), 'node-1', proposer.JoiningProposerInstallationTest().check, 'proposer complete installation'
        return recovery.fixture(), ('node-1' if role=='remote' else 'node-4'), \
            recovery.JoiningSameViewNetworkTest().check, ('durable installation' if role=='remote' else 'recovery local installation')

    def mutate(self, role, change, point='INSTALL_MANIFEST_WRITTEN'):
        data, node, check, reason = self.fixture(role); events=data[0]
        at=next(i for i,v in enumerate(events) if v.get('node')==node and v['event']==point)
        if change=='missing':events[at]['event']='OMITTED'
        elif change=='scope':events[at]['scope']='other-owner'
        elif change=='shape':events[at]['claimedWritten']=True
        elif change in ('duplicate','extra-install','extra-current'):
            event=dict(events[at])
            if change!='duplicate':event['event']='INSTALL_UNKNOWN' if change=='extra-install' else 'CURRENT_UNKNOWN'
            events.insert(at,event)
            for row in data[1]:
                for key in ('sent','received','offered','delivered'):
                    if type(row.get(key)) is int and row[key]>=at:row[key]+=1
        elif change=='reorder':events[at],events[at+1]=events[at+1],events[at]
        elif change=='unknown-install':events[at]['event']='INSTALL_UNKNOWN'
        elif change=='unknown-current':events[at]['event']='CURRENT_UNKNOWN'
        with self.assertRaisesRegex(ValueError, '^joining network '+reason+' order$'):check(data)

    def test_complete_explicit_sequences_for_all_three_owners(self):
        for role in ('proposer','remote','recovery'):
            data,_,check,_=self.fixture(role)
            with self.subTest(role=role):check(data)

    def test_each_previously_unchecked_creation_write_and_validation_is_required(self):
        for role in ('proposer','remote','recovery'):
            for point in ('INSTALL_DIRECTORY_CREATED','INSTALL_MANIFEST_WRITTEN','INSTALL_IMAGE_WRITTEN',
                          'INSTALL_MEMBER_WRITTEN','INSTALL_SELECTOR_WRITTEN','CURRENT_VALIDATED'):
                with self.subTest(role=role,point=point):self.mutate(role,'missing',point)

    def test_writes_require_exact_owner_and_shape(self):
        for role in ('proposer','remote','recovery'):
            for change in ('scope','shape'):
                with self.subTest(role=role,change=change):self.mutate(role,change)

    def test_duplicate_and_write_after_force_are_rejected(self):
        for role in ('proposer','remote','recovery'):
            for change in ('duplicate','reorder'):
                with self.subTest(role=role,change=change):self.mutate(role,change)

    def test_unknown_install_and_current_callbacks_cannot_replace_writes(self):
        for role in ('proposer','remote','recovery'):
            for change in ('unknown-install','unknown-current'):
                with self.subTest(role=role,change=change):self.mutate(role,change)

    def test_unknown_callbacks_alongside_complete_writes_are_rejected(self):
        for role in ('proposer','remote','recovery'):
            for change in ('extra-install','extra-current'):
                with self.subTest(role=role,change=change):self.mutate(role,change)


if __name__=='__main__':unittest.main()
