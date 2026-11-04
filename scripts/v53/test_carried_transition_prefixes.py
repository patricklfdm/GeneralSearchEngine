import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import carried_transition_prefixes as p
from . import test_remove_retirement_prefixes as fixtures


class CarriedTransitionPrefixesTest(unittest.TestCase):
    def fixture(self,base,kind):
        root,sidecar,files=fixtures.RemoveRetirementPrefixesTest().fixture(base)
        (root/'carried-transition-result.json').write_bytes(p.f.canonical(dict(kind=kind)))
        path=sidecar/'collection.json';header=json.loads(path.read_bytes());header.update(schema=p.SCHEMA,profile=kind,
            resultSha256=p.sha((root/'carried-transition-result.json').read_bytes()));path.write_bytes(p.f.canonical(header))
        return root,sidecar,files

    def test_separate_kind_and_result_binding_cannot_alias_ordinary_remove(self):
        for kind in ('INTENT','FINAL'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root,sidecar,files=self.fixture(Path(temp),kind)
                self.assertEqual(files,p.collect(root,sidecar,kind)[0][0]['files'])
                for other in ('FINAL' if kind=='INTENT' else 'INTENT','4-REMOVE','DATA'):
                    with self.assertRaises(ValueError):p.collect(root,sidecar,other)
                with self.assertRaisesRegex(ValueError,'collection header'):p.p.collect(root,sidecar,'4-REMOVE')
                (root/'carried-transition-result.json').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'original history binding'):p.collect(root,sidecar,kind)

    def test_shared_rows_keep_exact_original_owner_and_collector_bounds(self):
        names=('missing-copy','history-binding','profile-binding','duplicate-index','wrong-callback',
               'missing-object','altered-object','extra-object','boolean-size','wrong-owner','result-binding','kind-binding')
        for kind in ('INTENT','FINAL'):
            for name in names:
                with self.subTest(kind=kind,name=name),tempfile.TemporaryDirectory() as temp:
                    root,sidecar,_=self.fixture(Path(temp),kind);p.mutate(sidecar,name)
                    with self.assertRaisesRegex(ValueError,'^'+p.NEGATIVES[name]+'$'):p.collect(root,sidecar,kind)

    def test_carried_plans_and_ledger_origin_are_not_replaced_by_default_remove(self):
        self.assertIs(p.Replay.plans,p.r.Replay.plans)
        self.assertIs(p.Replay.initial_states,p.r.r.PeerReplay.initial_states)
        self.assertIs(p.Replay.transaction,p.p.Replay.transaction)
        self.assertLess(p.Replay.__mro__.index(p.r.Replay),p.Replay.__mro__.index(p.p.r.Replay))

    def test_missing_original_or_unbound_extra_capture_cannot_earn_credit(self):
        with patch.object(p.r,'validate',side_effect=ValueError('original failed')),patch.object(p,'collect') as collect,patch.object(p,'mutate') as mutate:
            with tempfile.TemporaryDirectory() as temp:
                root,sidecar,_=self.fixture(Path(temp),'INTENT')
                with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify(root,sidecar,'INTENT')
        collect.assert_not_called();mutate.assert_not_called()
        value=p.Replay.__new__(p.Replay);value.captured_used=set();value.copies={0:{}}
        with patch.object(p.p.r.Replay,'run',return_value={}):
            with self.assertRaisesRegex(ValueError,'unbound observation'):value.run()

    def test_pending_negative_needs_actual_vote_and_changes_only_one_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,_=self.fixture(Path(temp),'INTENT');objects=sidecar/'objects'
            for at,raw in ((1,b'original pending vote'),(2,p.r.c.EMPTY)):
                path=sidecar/f'capture-{at:04d}.json';value=json.loads(path.read_bytes());value['point']='RETIREMENT_OLD_FILES_FORCED'
                digest=p.sha(raw);(objects/digest).write_bytes(raw);value['files'].append(dict(name='pending.accept',identity=dict(size=len(raw),sha256=digest)))
                value['files'].sort(key=lambda v:v['name']);path.write_bytes(p.f.canonical(value))
            before=(sidecar/'capture-0002.json').read_bytes();p.mutate(sidecar,'pending-cleared')
            value=json.loads((sidecar/'capture-0001.json').read_bytes());entry=next(v for v in value['files'] if v['name']=='pending.accept')
            self.assertEqual(p.r.c.EMPTY,(objects/entry['identity']['sha256']).read_bytes())
            self.assertEqual(before,(sidecar/'capture-0002.json').read_bytes())
            self.assertFalse((objects/p.sha(b'original pending vote')).exists())
            with self.assertRaisesRegex(ValueError,'requires actual pending vote'):p.mutate(sidecar,'pending-cleared')


if __name__=='__main__':unittest.main()
