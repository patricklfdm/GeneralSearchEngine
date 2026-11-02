"""Timeline boundaries; synthetic rows do not qualify native competition."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import competing_grant_captures as c


class CompetingGrantCapturesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.events = [dict(node=node, event=event, nanoTime=time) for node,event,time in (
            ('node-1','GRANT_BEFORE_RETURN',10), ('node-2','GRANT_BEFORE_RETURN',20), ('node-3','NODE_OPEN',40))]
        self.links = [dict(node='node-'+str(i), scope='network-owner', event=c.g.EVENT,
            capture=f'grant-captures/capture-{i:04d}', sha256='a'*64, basis='b'*64,
            returnEvent=i-1, capturedAfterEvent=1, nanoTime=20+i) for i in (1,2)]

    def write(self, events=None, links=None):
        (self.root/'events.json').write_bytes(c.f.canonical(self.events if events is None else events))
        (self.root/c.FILE).write_bytes(c.f.canonical(self.links if links is None else links))

    def test_other_owners_can_interleave_and_original_trace_remains_unchanged(self):
        self.write(); before=(self.root/'events.json').read_bytes(); merged=c.timelines(self.root)
        self.assertEqual(['GRANT_BEFORE_RETURN','GRANT_BEFORE_RETURN',c.g.EVENT,c.g.EVENT,'NODE_OPEN'],[v['event'] for v in merged])
        self.assertEqual(before,(self.root/'events.json').read_bytes())
        self.assertEqual([0,1],[i for i,v in enumerate(merged) if v['event']=='GRANT_BEFORE_RETURN'])

    def test_all_timeline_mutations_refuse_for_the_declared_reason(self):
        for name,reason in c.NEGATIVES.items():
            if name=='missing-force':continue
            with self.subTest(name=name):
                self.write(); c.mutate(self.root,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):c.timelines(self.root)

    def test_same_owner_cannot_resume_writing_during_its_capture(self):
        self.events.insert(1,dict(node='node-1',event='BASIS_WRITTEN',nanoTime=15))
        self.links[0]['capturedAfterEvent']=2;self.links[1].update(returnEvent=2,capturedAfterEvent=2)
        self.write()
        with self.assertRaisesRegex(ValueError,'writer advanced before copy'):c.timelines(self.root)

    def test_unobserved_unknown_or_nondecreasing_clock_claims_are_not_ignored(self):
        for changed,reason in ((dict(event='UNKNOWN'),'unknown owner event'),(dict(nanoTime=0),'monotonic owned events')):
            with self.subTest(changed=changed):
                events=copy.deepcopy(self.events);events[-1].update(changed);self.write(events=events)
                with self.assertRaisesRegex(ValueError,reason):c.timelines(self.root)

    def test_sidecar_shape_scope_and_canonical_encoding_are_strict(self):
        for fields in (dict(scope='other'),dict(extra=True),dict(event='other')):
            with self.subTest(fields=fields):
                links=copy.deepcopy(self.links);links[0].update(fields);self.write(links=links)
                with self.assertRaisesRegex(ValueError,'link shape'):c.timelines(self.root)
        self.write();(self.root/c.FILE).write_text('[ {"node":1,"node":2} ]')
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):c.timelines(self.root)

    def test_missing_or_unordered_sidecar_never_silently_downgrades(self):
        self.write(links=[])
        with self.assertRaisesRegex(ValueError,'bounded links'):c.timelines(self.root)
        self.write(links=list(reversed(self.links)))
        with self.assertRaisesRegex(ValueError,'ordered path'):c.timelines(self.root)
        (self.root/c.FILE).unlink()
        with self.assertRaises((ValueError,OSError)):c.timelines(self.root)

    def test_boolean_clock_and_uncounted_return_are_refused(self):
        links=copy.deepcopy(self.links);links[0]['nanoTime']=True;self.write(links=links)
        with self.assertRaisesRegex(ValueError,'monotonic interval'):c.timelines(self.root)
        self.events.append(dict(node='node-3',event='GRANT_BEFORE_RETURN',nanoTime=50));self.write()
        with self.assertRaisesRegex(ValueError,'complete returns'):c.timelines(self.root)

    def test_original_failure_stops_before_copying_or_negative_mutations(self):
        with patch.object(c,'validate',side_effect=ValueError('invalid original')),patch.object(c.g,'qualify') as copies,patch.object(c,'mutate') as mutation:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):c.qualify(self.root)
            copies.assert_not_called();mutation.assert_not_called()

    def test_unrelated_failure_and_accepted_mutation_are_not_coverage(self):
        for next_result,reason in ((ValueError('unrelated'),'unrelated competing capture negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(c,'validate',side_effect=[dict(captures=2),next_result]), \
                 patch.object(c,'timelines',return_value=[]),patch.object(c.g,'qualify',return_value=dict(negatives=[])), \
                 patch.object(c.shutil,'copytree'),patch.object(c,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):c.qualify(self.root)

    def test_joining_profile_cannot_disable_required_learner_retention(self):
        with patch.object(c.g,'collect') as collect:
            with self.assertRaisesRegex(ValueError,'joining requires learner retention'):
                c.g.validate(self.root,[],whole_history=True,learner_retention=False)
            collect.assert_not_called()

    def test_partial_attachment_is_not_historical_legacy_evidence(self):
        for name in (c.FILE,c.g.DIRECTORY):
            with self.subTest(name=name):
                path=self.root/name;path.write_bytes(b'')
                with self.assertRaisesRegex(ValueError,'complete grant capture attachments'):c.p.inventory(self.root)
                path.unlink()


if __name__=='__main__':unittest.main()
