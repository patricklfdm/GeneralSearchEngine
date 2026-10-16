"""Process-namespace boundaries only; fabricated rows never qualify an execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import runtime_evidence as evidence


class RuntimeProcessGenerationTest(unittest.TestCase):
    def run_rows(self,rows,**kwargs):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'node-1').mkdir()
            for name in ('manifest','genesis'):(root/'node-1'/(name+'.gsr')).write_bytes(b'x'*48)
            manifest=dict(members=[dict(node='node-'+str(i)) for i in (1,2,3)])
            genesis=dict(application='',baseSequence=0)
            with patch.object(evidence.f,'inspect',side_effect=[manifest,genesis]),\
                 patch.object(evidence,'application',return_value=([],{})),\
                 patch.object(evidence.storage,'inspect',return_value=dict(provenThrough=0,acceptedDigests=[])):
                evidence.validate(root,rows,**kwargs)

    def rows(self):
        rows={node:[dict(pid=42,generation=1,order=1,event='FIXTURE_ONLY')] for node in ('node-1','node-2','node-3')}
        rows['node-1'].append(dict(pid=42,generation=2,order=1,event='FIXTURE_ONLY'))
        return rows

    def test_pid_reuse_requires_opt_in_and_never_skips_physical_completeness(self):
        with self.assertRaisesRegex(ValueError,'retained-disk restart required'):self.run_rows(self.rows())
        with self.assertRaisesRegex(ValueError,'incomplete runtime execution'):
            self.run_rows(self.rows(),process_generations=True)

    def test_trace_order_is_still_strict_inside_each_generation(self):
        rows=self.rows();rows['node-1'].append(dict(pid=42,generation=2,order=1,event='FIXTURE_ONLY'))
        with self.assertRaisesRegex(ValueError,'process trace order'):self.run_rows(rows,process_generations=True)

    def test_closed_generation_numbers_do_not_create_arbitrary_processes(self):
        for value in (None,True,0,3,'2'):
            rows=self.rows();rows['node-1'][-1]['generation']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'runtime process generation'):
                self.run_rows(rows,process_generations=True)

    def test_legacy_rows_without_generation_keep_the_default_path(self):
        rows=self.rows();rows['node-1'][-1]['pid']=43
        for values in rows.values():
            for row in values:row.pop('generation')
        with self.assertRaisesRegex(ValueError,'incomplete runtime execution'):self.run_rows(rows)
        with self.assertRaisesRegex(ValueError,'runtime process generation'):self.run_rows(rows,process_generations=True)

    def test_non_boolean_mode_rejects_before_reading_files(self):
        for value in (None,1,'yes',{}):
            with self.assertRaisesRegex(ValueError,'runtime process generation mode'):
                evidence.validate('nonexistent',process_generations=value)


if __name__=='__main__':unittest.main()
