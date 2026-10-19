"""Actual native Session/storage factories; provider/SSH effects remain modeled."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import cloud_storage as s,remote_java_ssh as js,remote_java_receiver as j
from . import test_cloud_storage as storage_fixture
from .test_remote_java import fixture


class NativeJavaTest(unittest.TestCase):
    def setUp(self):
        self.base=storage_fixture.NativeStorageTest('test_actual_factory_original_mount_install_and_complete_history_placement')
        self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.storage=self.base.prepare();self.group=self.base.group;self.calls=[];self.installers=[];self.records={};self.fail=False;self.drift=False
        self.value,raw=fixture(self.storage.source);self.path=self.base.root/'java.tar.gz';self.path.write_bytes(raw)
        outer=self
        class Installer(js.Installer):
            def __init__(self,target,descriptor):
                super().__init__(target,descriptor);self.node='node-'+str(target['port']-21000);outer.installers.append(self)
            def exchange(self,action,parent,archive=None):
                self.calls.append(action);outer.calls.append((self.node,action))
                if action=='install':
                    j.verify_archive(archive,self.value)
                    if outer.fail and self.node=='node-2':raise ValueError('original partial installation')
                    outer.records[self.node]=dict(schema=j.RECEIPT,descriptorSha256=self.pin,root=str(Path(parent)/('java-'+self.value['sha256'])),
                        filesSha256=j.p.digest(j.p.encoded(self.value['files'])),java=self.value['source']['java'],
                        host=deepcopy(outer.storage.installations[self.node]['host']))
                    if self.node=='node-1':raise ConnectionError('lost original Java reply')
                result=deepcopy(outer.records[self.node])
                if outer.drift:result['host']['parentInode']+=1
                return result
        p=patch.object(js,'Installer',Installer);p.start();self.addCleanup(p.stop)

    def test_original_source_once_only_installation_and_placement_binding(self):
        wrong=deepcopy(self.value);wrong['source']['java']['java.vendor']='other'
        with self.assertRaisesRegex(ValueError,'input source changed'):self.storage.install_java(self.group,wrong,self.path)
        self.assertFalse(self.calls);self.assertFalse(self.storage.java_started)
        self.storage.install_java(self.group,self.value,self.path)
        self.assertEqual([('node-1','install'),('node-1','verify'),('node-2','install'),('node-3','install')],self.calls)
        self.assertTrue(all(i.closed for i in self.installers))
        name=self.base.session.owner.request['selection']['member']['histories'][0]
        placement=self.storage.placement(self.group,name)
        receiver=placement.factory(name)(self.base.root/'history',name,self.storage.source)
        self.assertEqual(self.records['node-2']['root'],receiver.python_context('node-2')['java']['root'])
        self.assertEqual(self.value,placement.java['descriptor'])
        receipt=s.strict((self.storage.output/'java-receipt.json').read_bytes())
        self.assertEqual('JAVA_READY_NOT_QUALIFIED',receipt['status']);self.assertFalse(receipt['engineWorkloadExecuted'])
        with self.assertRaisesRegex(ValueError,'already consumed'):self.storage.install_java(self.group,self.value,self.path)
        self.drift=True
        other=self.base.session.owner.request['selection']['member']['histories'][1]
        with self.assertRaisesRegex(ValueError,'installed Java changed'):self.storage.placement(self.group,other)
        self.base.session.close();self.assertEqual({},self.base.base.base.case.server.resources)

    def test_partial_java_installation_blocks_work_and_cannot_be_resubmitted(self):
        self.fail=True
        with self.assertRaisesRegex(ValueError,'original partial'):self.storage.install_java(self.group,self.value,self.path)
        self.assertIsNone(self.storage.java);self.assertTrue(self.storage.java_started)
        self.assertEqual(['node-1'],s.strict((self.storage.output/'java-failure.json').read_bytes())['installedNodes'])
        name=self.base.session.owner.request['selection']['member']['histories'][0]
        before=list(self.calls)
        with self.assertRaisesRegex(ValueError,'installation incomplete'):self.storage.placement(self.group,name)
        with self.assertRaisesRegex(ValueError,'already consumed'):self.storage.install_java(self.group,self.value,self.path)
        self.assertEqual(before,self.calls);self.assertTrue(all(i.closed for i in self.installers))
        self.base.session.close();self.assertEqual({},self.base.base.base.case.server.resources)


if __name__=='__main__':unittest.main()
