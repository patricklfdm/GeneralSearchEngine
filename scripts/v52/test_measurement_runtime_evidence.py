import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from . import measurement_model as model,measurement_runtime_evidence as e


class MeasurementRuntimeEvidenceTest(unittest.TestCase):
    def test_ordinary_smoke_requires_selected_pair_without_extra_campaign_traffic(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'artifacts').mkdir()
            names=['general-search-engine-5.2.0-SNAPSHOT.jar','general-search-engine-replication-5.2.0-SNAPSHOT.jar']
            for name in names:(root/'artifacts'/name).write_bytes(name.encode())
            bound=dict(mode='candidate-minimum',origin=str(root),programSha256=model.PLAN_SHA,classes={},
                       artifacts={name:e.digest(name.encode()) for name in names})
            processes=[]
            for i in range(1,4):
                node='node-'+str(i)
                processes.append(dict(node=node,pid=i,generation=1,exitCode=0,identity=dict(node=node,pid=i,mode=bound['mode'],
                    coreSource=str(root/'artifacts'/names[0]),replicationSource=str(root/'artifacts'/names[1]))))
            for name,value in [('binding.json',bound),('history.json',[]),('scenario.json',dict(mode=bound['mode'])),('processes.json',processes)]:
                (root/name).write_text(json.dumps(value))
            (root/'bundle-members.json').write_text(json.dumps(e.bundle.members(root)))
            with patch.object(e.physical,'validate',side_effect=ValueError('physical sentinel')) as physical:
                with self.assertRaisesRegex(ValueError,'physical sentinel'):e.validate(root,bound,traces={})
                self.assertEqual('selected-quorums',physical.call_args.kwargs['basis_coverage'])
                self.assertFalse(physical.call_args.kwargs['require_restart'])

    def test_only_published_control_may_lack_new_application_generation(self):
        for mode in model.MODES:
            self.assertEqual(7,e.publication_generation(dict(applicationGeneration=7),mode))
            if mode=='published-v51-legacy-strong':self.assertIsNone(e.publication_generation({},mode))
            else:
                with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'missing application generation'):e.publication_generation({},mode)
            for value in (True,0,-1,'1',None):
                with self.subTest(mode=mode,value=value),self.assertRaisesRegex(ValueError,'generation type'):e.publication_generation(dict(applicationGeneration=value),mode)

    def test_invalid_original_never_counts_as_successful_negative_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('original physical evidence failed')) as check:
            with self.assertRaisesRegex(ValueError,'original physical evidence failed'):e.negatives('unused',{}, {})
        check.assert_called_once_with('unused',{}, {},package=e.bundle)


if __name__=='__main__':unittest.main()
