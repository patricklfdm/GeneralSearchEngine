"""Synthetic scope/ownership regressions, separate from real SSH qualification."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import guest_physical_evidence as e, guest_authority as a, guest_evidence as logical
from . import cloud_guest as guest, remote_command as c, performance_model as m, remote_collection as parts
from . import storage_fixture, storage_inspector, cloud_fake
from .test_guest_healthy_evidence import HealthyFixture
from . import test_remote_rich
from .remote_rich_physical import Calls


class AuthorityTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_copies_only_own_complete_immutable_authority_and_preserves_sealed_path(self):
        original=self.root/'original';original.mkdir();storage_fixture.create(original)
        (original/'node-2/private').write_bytes(b'neighbour')
        copied=self.root/'copied/node-1';a.capture(original,'node-1',copied)
        self.assertEqual(a.inventory(original/'node-1'),a.inventory(copied))
        self.assertFalse((copied.parent/'node-2').exists())
        with self.assertRaisesRegex(ValueError,'seal path'):storage_inspector.inspect(copied)
        location=e.Location(copied.parent,original,{'node-1':a.inventory(copied)})
        self.assertEqual(location.inspect(copied,64<<20,1<<20)['provenThrough'],0)
        (copied/'proofs.gsr').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'inventory differs'):location.inspect(copied,64<<20,1<<20)
    def test_resealed_corrupt_authority_still_fails_storage_inspection(self):
        original=self.root/'original';original.mkdir();storage_fixture.create(original)
        copied=self.root/'copied/node-1';a.capture(original,'node-1',copied)
        (copied/'proofs.gsr').write_bytes(b'changed')
        location=e.Location(copied.parent,original,{'node-1':a.inventory(copied)})
        with self.assertRaises(ValueError):location.inspect(copied,64<<20,1<<20)
    def test_symlink_special_file_owner_and_capacity_fail_before_copy(self):
        source=self.root/'node-1';source.mkdir();(source/'linked').symlink_to('/etc/hosts')
        with self.assertRaisesRegex(ValueError,'path/type'):a.capture(self.root,'node-1',self.root/'copy')
        self.assertFalse((self.root/'copy').exists());(source/'linked').unlink()
        with (source/'large').open('wb') as out:out.truncate(a.MAX_BYTES+1)
        with self.assertRaisesRegex(ValueError,'byte bound'):a.capture(self.root,'node-1',self.root/'copy')
        with self.assertRaisesRegex(ValueError,'owner'):a.capture(self.root,'../node-1',self.root/'copy')
    def fixture(self):
        value=HealthyFixture(self.root/'fixture');row=value.transcript[-1]
        row['request']['payload']={'physical':True};row['receipt']['requestSha256']=m.sha(m.canonical(row['request']))
        value.files['authority/node-1/fixture']=b'synthetic not valid authority';value.render()
        return value
    def test_member_logical_receipt_never_claims_joint_physical_qualification(self):
        value=self.fixture()
        result=logical.validate(value.root,value.config,value.manifest,value.base,value.transcript,active=True,healthy=True,physical=True)
        self.assertFalse(result['physicalHistoryQualified']);self.assertEqual(result['calls'],90)
        with self.assertRaisesRegex(ValueError,'collection receipt'):value.validate()
    def test_foreign_authority_is_rejected_even_with_updated_inventory(self):
        value=self.fixture();foreign=value.root/'authority/node-2';foreign.mkdir();(foreign/'fixture').write_bytes(b'foreign')
        value.reseal()
        with self.assertRaisesRegex(ValueError,'closed inventory'):
            logical.validate(value.root,value.config,value.manifest,value.base,value.transcript,active=True,healthy=True,physical=True)
    def test_missing_duplicate_or_mixed_group_never_reaches_physical_oracle(self):
        value=self.fixture();member=dict(root=value.root,controller=dict(config=value.config,active=True))
        with patch.object(e.physical,'automatic') as oracle:
            for members in ([],[member],[member]*3):
                with self.assertRaisesRegex(ValueError,'member'):e.validate(members,value.manifest)
            members=[deepcopy(member) for _ in range(3)]
            for i,row in enumerate(members,1):row['controller']['config']['binding']['node']='node-'+str(i)
            members[1]['controller']['config']['binding']['attempt']='d'*32
            with self.assertRaisesRegex(ValueError,'group/config binding'):e.validate(members,value.manifest)
            oracle.assert_not_called()
    def test_live_voter_never_enters_physical_capture(self):
        obj=guest.Service.__new__(guest.Service);obj.config={};obj.jvm=Mock(closed=False);obj.ack=Mock();obj.shutting_down=False
        with patch.object(a,'capture') as capture:
            with self.assertRaisesRegex(ValueError,'stopped JVM'):obj.handler('collect',{'physical':True},lambda:None)
            capture.assert_not_called()


class PhysicalScopeTest(unittest.TestCase):
    def test_zero_backup_scope_rejects_unexpected_backup_and_default_still_requires_one(self):
        calls,events,projected,published,votes,promise=test_remote_rich.ConcurrentCutTest().sample()
        def replay(rows,**scope):
            audit=Calls(calls,**scope)
            for row in rows:audit.event('node-1',row,projected,published,votes,promise)
            audit.finish()
        replay(events);replay([r for r in events if r['order']<22],auxiliary_backups=0)
        with self.assertRaisesRegex(ValueError,'accounting'):replay(events,auxiliary_backups=0)
        with self.assertRaisesRegex(ValueError,'accounting'):replay([r for r in events if r['order']<22])
        for value in (True,-1,2):
            with self.assertRaisesRegex(ValueError,'scope'):Calls(calls,auxiliary_backups=value)
    def test_final_observation_only_queries_status_with_original_deadline(self):
        clock=cloud_fake.Clock();calls=[]
        def status(member,end):
            calls.append((member,end));return dict(state='LEADER_READY' if member==1 else 'FOLLOWER',provenIndex=91)
        e.converge([1,2,3],1,status,clock.seconds()+5,clock=clock.seconds,sleep=clock.sleep)
        self.assertEqual([n for n,_ in calls],[1,1,2,3]);self.assertEqual(len({end for _,end in calls}),1)
        def behind(member,end):return dict(state='LEADER_READY',provenIndex=91 if member==1 else 90)
        with self.assertRaisesRegex(ValueError,'deadline'):
            e.converge([1,2,3],1,behind,clock.seconds()+.1,clock=clock.seconds,sleep=clock.sleep)


if __name__=='__main__':unittest.main()
