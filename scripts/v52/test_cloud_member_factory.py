"""Actual native admission factory with modeled provider/JDK external effects."""
from pathlib import Path
import unittest
from unittest.mock import patch
from . import cloud_native_runner as n,cloud_staging as s,remote_java_package as java
from . import test_cloud_native_runner as fixture
from .test_cloud_inputs import roots


class NativePreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.NativeRunnerTest.setUpClass()
    def setUp(self):
        self.base=fixture.NativeRunnerTest();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.root=self.base.root/'staged-checkout';self.root.mkdir();self.stage=s.stage;self.staged=[];self.builds=[]
        self.java_error=False;self.order=[]
        def stage(root,source,build,package,output,**kwargs):
            self.assertEqual([],self.base.mutations());self.order.append('stage')
            with patch.object(s.inputs.build,'layout',return_value=roots()):
                value=self.stage(self.root,source,build,package,output,**kwargs)
            self.staged.append(value);return value
        def image(root,expected,output):
            self.assertEqual([],self.base.mutations());self.order.append('java')
            self.assertEqual(self.base.arguments['proof']['source'],expected)
            self.staged[-1].check();self.builds.append(output)
            if self.java_error:raise ValueError('original JDK failed')
            output.mkdir();(output/'runtime.tar.gz').write_bytes(b'synthetic image, not executed')
            return {'source':expected,'synthetic':True}
        self.base.stack.enter_context(patch.object(s,'stage',side_effect=stage))
        self.base.stack.enter_context(patch.object(java,'create',side_effect=image))
    def test_prepares_original_inputs_before_provider_mutation_and_owns_handles_through_close(self):
        with self.base.open(prepare_workload=True) as session:
            self.assertEqual(['stage','java'],self.order);self.assertFalse(session.staged.closed)
            self.assertEqual(5,len(session.staged.files));self.assertIsNotNone(session.java)
            self.assertFalse(session.result['engineWorkloadExecuted']);self.assertFalse(session.member_started)
        self.assertTrue(session.staged.closed);self.assertEqual({},self.base.case.server.resources)
        self.assertEqual({'FAIL'},{r['status'] for r in self.base.state()['attempts'].values()})
    def test_jdk_failure_never_acquires_lease_and_closes_staging(self):
        self.java_error=True
        with self.assertRaisesRegex(ValueError,'original JDK failed'):self.base.open(prepare_workload=True)
        self.assertTrue(self.staged[-1].closed);self.assertEqual([],self.base.mutations());self.assertEqual([],self.base.case.calls)
        failure=n.strict((self.base.output/'failure.json').read_bytes())
        self.assertEqual('java-package',failure['phase']);self.assertFalse(failure['fullRemoteQualification'])
    def test_conflicting_input_never_builds_java_or_calls_provider(self):
        path=self.root/s.paths()[-1];path.parent.mkdir(parents=True);path.write_bytes(b'conflict')
        with self.assertRaisesRegex(ValueError,'type/size|bytes changed'):self.base.open(prepare_workload=True)
        self.assertEqual([],self.builds);self.assertEqual([],self.base.mutations());self.assertEqual([],self.base.case.calls)
        self.assertEqual([path],list(p for p in self.root.rglob('*') if p.is_file()))


if __name__=='__main__':unittest.main()
