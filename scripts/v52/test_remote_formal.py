from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_voter_scope as scope,remote_delivery_package as package,remote_voter_export as export
from . import remote_voter as v,remote_voter_guest as guest,remote_voter_lifecycle as lifecycle
from . import remote_voter_lifecycle_evidence as evidence,remote_formal_qualification as qualification
from . import cloud_suite,measurement_bundle as bundle
from . import test_remote_delivery as fixture


def binding(spec):
    profile=spec['profile'];family=spec['family']
    return dict(mode=spec['mode'],measurementProfile=profile,programSha256=scope.partition.model.PLAN_SHA,
                readParameters=profile['parameters'] if family in ('M02','M03') else scope.partition.options.parameters(),
                remoteFormal=scope.FORMAL_EXECUTION)


class ScopeTest(unittest.TestCase):
    def test_every_full_profile_keeps_exact_frozen_parameters_and_counts(self):
        plan=cloud_suite.load();selected=[n for n,s in plan['histories'].items() if s['family'] in ('M01','M02','M03')]
        self.assertEqual(26,len(qualification.history_names(selected)))
        for name in selected:
            spec=plan['histories'][name];bound=binding(spec)
            self.assertEqual(spec['profile'],scope.history(bound));self.assertTrue(scope.formal(bound))
            if spec['family']=='M01':
                self.assertEqual((1801,180),qualification.counts(spec))
                self.assertEqual(180_000_000_000,spec['profile']['durationNanos']);self.assertEqual(125,spec['profile']['drainSeconds'])
        self.assertEqual((66,4),qualification.counts(plan['histories']['m03-p65']))
        self.assertEqual((31,3),qualification.counts(plan['histories']['m02-above-0']))
        self.assertEqual((31,4),qualification.counts(plan['histories']['m02-above-1000']))

    def test_short_mixed_smoke_changed_deadline_and_parameter_profiles_reject(self):
        cases=('candidate-explicit-strong-r1','m02-above-1000','m03-p65')
        for name in cases:
            bound=binding(cloud_suite.load()['histories'][name])
            for mutate in (lambda b:b['measurementProfile'].update(businessRetries=1),
                           lambda b:b['readParameters'].update(operationTimeoutMillis=1),
                           lambda b:b.update(driverExercise=True),lambda b:b.update(faultParameters={}),
                           lambda b:b.update(remoteRestart=scope.RESTART_EXECUTION),lambda b:b.update(mode='unknown')):
                wrong=deepcopy(bound);mutate(wrong)
                with self.assertRaises(ValueError):scope.history(wrong)
        bound=binding(cloud_suite.load()['histories']['candidate-minimum-r1'])
        bound['measurementProfile']['durationNanos']=1
        with self.assertRaisesRegex(ValueError,'exact M01'):scope.history(bound)

    def test_implicit_second_generation_and_unknown_or_duplicate_histories_reject(self):
        for name in ('candidate-minimum-r1','m02-above-1000','m03-p65'):
            with self.assertRaisesRegex(ValueError,'undeclared generation'):scope.generation(dict(binding=binding(cloud_suite.load()['histories'][name]),generation=2))
        for names in ([],['m03-p4','m03-p4'],['unknown'],[scope.RESTART_CASE],['candidate-minimum-untimed-smoke']):
            with self.assertRaises(ValueError):qualification.history_names(names)


class PackageTest(fixture.Fixture):
    def formal(self,name):
        bound={k:v for k,v in self.binding.items() if k!='driverExercise'};spec=cloud_suite.load()['histories'][name]
        bound.update(binding(spec))
        if spec['family'] in ('M02','M03'):package.h.runtime.save(self.producer/package.h.options.FILE,bound['readParameters'])
        return bound
    def test_m01_capsule_keeps_no_options_or_fault_file(self):
        bound=self.formal('candidate-minimum-r1');archive,meta=package.create(self.producer,self.root/'formal',bound)
        self.assertEqual(bound['measurementProfile'],meta['measurement']);self.assertNotIn('recovery',meta)
        self.assertNotIn(package.h.options.FILE,meta['members']);self.assertNotIn(package.h.recovery.FILE,meta['members'])
        package.verify_archive(archive,meta)

    def test_m02_m03_capsules_include_exact_options_and_detect_changed_bytes(self):
        for name in ('m02-above-1000','m03-p65'):
            bound=self.formal(name);archive,meta=package.create(self.producer,self.root/name,bound)
            self.assertIn(package.h.options.FILE,meta['members'])
            target=bundle.unpack(archive,self.root/(name+'-installed'));package.installed(target,meta)
            (target/package.h.options.FILE).write_text('{}')
            with self.assertRaisesRegex(ValueError,'installed input changed'):package.installed(target,meta)

    def test_missing_wrong_family_duplicate_or_changed_capsule_profile_reject(self):
        archive,meta=package.create(self.producer,self.root/'formal',self.formal('m03-p65'))
        for mutate in (lambda m:m.pop('measurement'),lambda m:m.update(recovery=scope.partition.recovery.profile(scope.RESTART_CASE)),
                       lambda m:m['members'].pop(package.h.options.FILE),lambda m:m['measurement']['parameters'].update(pendingLimit=64),
                       lambda m:m.update(mode='published-v51-legacy-strong')):
            wrong=deepcopy(meta);mutate(wrong)
            with self.assertRaises(ValueError):package.validate(wrong)


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config=dict(node='node-1',binding=binding(cloud_suite.load()['histories']['candidate-minimum-r1']))
    def meta(self,index):
        return dict(schema=export.SCHEMA,configSha256='a'*64,node='node-1',bytes=1,sha256='b'*64,inventory=export.summary(index),terminal={})
    def test_large_inventory_uses_small_digest_envelope_and_closed_original_limits(self):
        index={f'node-1/files/{n}.gsr':dict(bytes=16384,sha256='a'*64) for n in range(8426)}
        meta=self.meta(index);export.manifest(meta,self.config,'a'*64)
        self.assertLess(len(v.encoded(meta)),4096);self.assertGreater(meta['inventory']['expandedBytes'],64<<20)
        self.assertEqual(index,export.verify_inventory(index,meta))
        self.assertEqual(bundle.LIMITS,dict(files=400000,directories=4096,expanded=4<<30,compressed=4<<30,member=256<<20,inventory=64<<20))

    def test_legacy_export_limits_are_unchanged_and_formal_limit_checked_before_hash(self):
        own=self.root/'node-1';own.mkdir();(own/'one').write_text('one');(own/'two').write_text('two')
        with patch.object(guest,'MAX_FILES',1),patch.object(guest,'MAX_ARCHIVE',1):
            with self.assertRaisesRegex(ValueError,'collection bound'):guest.selected(self.root,'node-1')
            self.assertEqual(2,len(guest.selected(self.root,'node-1',self.config)))
        with patch.dict(bundle.LIMITS,{'member':1}),patch.object(bundle,'sha_file') as hashed:
            with self.assertRaisesRegex(ValueError,'collection bound'):guest.selected(self.root,'node-1',self.config)
            hashed.assert_not_called()

    def test_changed_count_hash_size_or_oversized_expansion_reject(self):
        index={'node-1/one':dict(bytes=3,sha256='a'*64)};meta=self.meta(index)
        for mutate in (lambda m:m['inventory'].update(files=0),lambda m:m['inventory'].update(files=True),
                       lambda m:m['inventory'].update(bytes=bundle.LIMITS['inventory']+1),
                       lambda m:m['inventory'].update(expandedBytes=bundle.LIMITS['expanded']),
                       lambda m:m['inventory'].update(sha256='wrong'),lambda m:m.update(bytes=bundle.LIMITS['compressed']+1)):
            wrong=deepcopy(meta);mutate(wrong)
            with self.assertRaises(ValueError):export.manifest(wrong,self.config,'a'*64)
        wrong=deepcopy(meta);wrong['inventory']['files']=2
        with self.assertRaisesRegex(ValueError,'inventory changed'):export.verify_inventory(index,wrong)

    def test_missing_formal_scope_cannot_use_large_export(self):
        meta=self.meta({'node-1/one':dict(bytes=3,sha256='a'*64)});config=deepcopy(self.config);config['binding'].pop('remoteFormal')
        with self.assertRaisesRegex(ValueError,'exact history'):export.manifest(meta,config,'a'*64)
        with self.assertRaisesRegex(ValueError,'collection identity'):evidence.manifest(meta,config,'a'*64)

    def test_combined_budget_is_checked_before_next_download(self):
        index={'node-1/one':dict(bytes=3,sha256='a'*64)};meta=self.meta(index)
        with patch.dict(bundle.LIMITS,{'expanded':meta['inventory']['bytes']+3}):
            export.aggregate([meta])
            with self.assertRaisesRegex(ValueError,'combined bound'):export.aggregate([meta,meta])
        with self.assertRaisesRegex(ValueError,'mixed'):export.aggregate([dict(meta,schema=guest.SCHEMA)])

    def test_first_inventory_hash_and_expansion_admit_before_extraction(self):
        stage=self.root/'source';stage.mkdir();(stage/'node-1-log').write_text('original')
        archive=self.root/'export.tar.gz';index=bundle.pack(stage,archive);meta=self.meta(index)
        target=lifecycle.unpack_export(archive,self.root/'downloaded',meta);self.assertEqual(index,bundle.inventory(target))
        for mutate in (lambda m:m['inventory'].update(sha256='0'*64),lambda m:m['inventory'].update(bytes=1),
                       lambda m:m['inventory'].update(expandedBytes=0),lambda m:m['inventory'].update(files=2)):
            wrong=deepcopy(meta);mutate(wrong)
            with patch.object(bundle,'unpack') as unpack:
                with self.assertRaises(ValueError):lifecycle.unpack_export(archive,self.root/'wrong',wrong)
                unpack.assert_not_called()

    def test_self_consistent_foreign_or_circular_inventory_is_rejected_before_extraction(self):
        for ordinal,name in enumerate(('node-2-log','binding.json','node-1-control/lifecycle.json','node-1-control-g2/ssh-streams.json')):
            stage=self.root/str(ordinal);stage.mkdir();path=stage/name;path.parent.mkdir(exist_ok=True)
            path.write_text('foreign');archive=self.root/(str(ordinal)+'.tar.gz')
            meta=self.meta(bundle.pack(stage,archive))
            with patch.object(bundle,'unpack') as unpack:
                with self.assertRaisesRegex(ValueError,'foreign collection|circular collection'):
                    lifecycle.unpack_export(archive,self.root/'wrong',meta)
                unpack.assert_not_called()


if __name__=='__main__':unittest.main()
