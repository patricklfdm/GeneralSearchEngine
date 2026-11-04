"""Bounded collection, exact reservation handoff, and original-first rejection tests."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from . import publication_resource_evidence as r
from . import publication_resource_negatives as n


class PublicationResourceEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        catalog = r.f.catalog()
        def record(kind, **changes):
            value = r.f.sample(catalog['records'][kind]['schema'],catalog['types']); value.update(changes)
            return r.f.encode('records',kind,value)
        self.before = {'root.gsr':record('ROOT'), 'node.gsr':record('NODE'),
            'selector.gsr':record('SELECTOR',generation='a'), 'pending.accept':b'vote',
            'generations':None,'generations/a':None,'generations/a/generation.gsr':b'manifest',
            'generations/a/application.image':b'old-image', 'sources':None,'sources/old':None,
            'sources/old/source.gscp':b'packet','sources/old/application.image':b'old-image',
            'applied-end':None,'applied-end/certificate.gsr':record('CERTIFICATE',index=1),
            'applied-end/application.image':b'new-image'}
        self.after = {k:v for k,v in self.before.items() if k != 'applied-end' and not k.startswith('applied-end/')}
        self.after.update({'generations/b':None,'generations/b/generation.gsr':b'new-manifest',
                          'generations/b/application.image':b'new-image','selector.gsr':record('SELECTOR',generation='b'),
                          'pending.accept':r.disk.EMPTY})
        self.plans = {('node-1',1):(self.before,self.after)}
        self.events = []; self.rows = []
        for at,(point,files,charges) in enumerate(r.derived(self.before,self.after)):
            self.events.append(dict(node='node-1',event=point))
            use = dict(charges,counts={**charges['counts'],'CONTROL':2,'WAITER':1},queued=10,leases=charges['leases']+3)
            self.rows.append(dict(schema='gse-v53-publication-resource-capture-v1',node='node-1',scope='',
                point=point,eventIndex=at,usageBefore=copy.deepcopy(use),usageAfter=copy.deepcopy(use),files=files))
        self.save(self.root,self.rows)

    @staticmethod
    def save(root, rows):
        directory = root/r.DIRECTORY; objects = directory/'objects'; objects.mkdir(parents=True)
        index = []
        for at,row in enumerate(rows):
            files = []
            for name,raw in sorted(row['files'].items()):
                if raw is None: identity = dict(directory=True)
                else:
                    digest = r.sha(raw); (objects/digest).write_bytes(raw); identity = dict(size=len(raw),sha256=digest)
                files.append(dict(name=name,identity=identity))
            raw = r.f.canonical(dict(row,files=files)); name = f'capture-{at:04d}.json'
            (directory/name).write_bytes(raw); index.append(dict(path=name,sha256=r.sha(raw)))
        (directory/'index.json').write_bytes(r.f.canonical(dict(schema='gse-v53-publication-resource-index-v1',complete=True,captures=index)))

    def test_exact_handoff_keeps_completion_image_until_reload_commits(self):
        rows = r.collect(self.root,self.events); result = r.compare(rows,self.plans)
        self.assertEqual(11,result['observedBoundaries']); self.assertEqual(6,result['maximumObservedStorage']['applications'])
        # Independently counted: one source packet, two old images, 4 maximum
        # reservations; new metadata is charged before its files exist.
        self.assertEqual(6+9+9+4*64*r.MIB,rows[0][0]['storage']['staging'])
        self.assertEqual(34*r.MIB+8+6,rows[0][0]['storage']['metadata'])
        self.assertEqual(34*r.MIB+8+6+12,rows[0][1]['storage']['metadata'])
        self.assertEqual(rows[0][0]['storage']['staging'],rows[0][7]['storage']['staging'])
        self.assertEqual(6+9+9+9+3*64*r.MIB,rows[0][8]['storage']['staging'])
        self.assertEqual(33,rows[0][9]['storage']['staging'])

    def test_all_declared_negative_reasons_are_exact_and_self_consistent(self):
        for name,reason in n.NEGATIVES.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp); shutil.copytree(self.root/r.DIRECTORY,target/r.DIRECTORY); n.mutate(target,name)
                with self.assertRaises(ValueError) as error: r.compare(r.collect(target,self.events),self.plans)
                self.assertEqual('publication resources '+reason,str(error.exception))

    def test_capture_order_may_interleave_owners_but_not_reorder_callbacks(self):
        rows = copy.deepcopy(self.rows); rows[0],rows[1] = rows[1],rows[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.save(root,rows)
            self.assertEqual(11,r.compare(r.collect(root,self.events),self.plans)['observedBoundaries'])
        events = copy.deepcopy(self.events); events[0],events[1] = events[1],events[0]
        with self.assertRaisesRegex(ValueError,'exact event'): r.collect(self.root,events)

    def test_linked_collection_and_objects_are_rejected(self):
        path = next((self.root/r.DIRECTORY/'objects').iterdir()); raw = path.read_bytes()
        other = self.root/'external'; other.write_bytes(raw); path.unlink(); path.symlink_to(other)
        with self.assertRaises(ValueError): r.collect(self.root,self.events)

    def test_missing_transaction_and_comparison_boundary_cannot_zip_truncate(self):
        rows = r.collect(self.root,self.events)
        with self.assertRaisesRegex(ValueError,'exact transaction count'): r.compare(rows,{})
        with self.assertRaisesRegex(ValueError,'exact boundary count'): r.compare([rows[0][:-1]],self.plans)

    def test_both_entry_points_require_original_before_capture_rejection(self):
        for run in (r.validate,n.qualify):
            with self.subTest(entry=run.__name__),patch.object(r,'original',side_effect=ValueError('invalid original')),patch.object(r,'collect') as collect:
                with self.assertRaisesRegex(ValueError,'invalid original'): run(self.root)
                collect.assert_not_called()

    def test_invalid_profile_cannot_select_another_reader(self):
        with self.assertRaisesRegex(ValueError,'unknown profile'): r.original(self.root,'other')

    def test_resource_sidecar_requires_explicit_native_layout_opt_in(self):
        names = {'initial','original-plan.gsbp','original-application.image','before-network','installed',
                 'applied-1','published-1','applied-2','published-2','after-close','calls.json','events.json',
                 'wire.json','failures.json','result.json','selected.gsr'}
        for name in names: (self.root/name).write_bytes(b'layout only')
        with patch.object(r.native,'physical',side_effect=ValueError('next independent gate')) as physical:
            with self.assertRaisesRegex(ValueError,'case inventory'): r.native.validate(self.root)
            physical.assert_not_called()
            with self.assertRaisesRegex(ValueError,'next independent gate'): r.native.validate(self.root,publication_resources=True)
            physical.reset_mock(); (self.root/'unknown-sidecar').mkdir()
            with self.assertRaisesRegex(ValueError,'case inventory'): r.native.validate(self.root,publication_resources=True)
            physical.assert_not_called()

    def test_full_history_events_use_the_existing_writer_envelope(self):
        rows = [dict(event='original',bytes='x'*600_000)]*15
        (self.root/'events.json').write_bytes(r.f.canonical(rows))
        with self.assertRaises(ValueError): r.native.read(self.root/'events.json')
        self.assertEqual(rows,r.events(self.root))
        # Keep the shared individual-row and total-row bounds, rather than
        # replacing the old reader with an unbounded json.load.
        (self.root/'events.json').write_bytes(r.f.canonical([dict(event='original')]*(r.history.HISTORY_ROWS+1)))
        with self.assertRaisesRegex(ValueError,'history row capacity'): r.events(self.root)


if __name__ == '__main__': unittest.main()
