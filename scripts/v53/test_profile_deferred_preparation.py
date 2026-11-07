"""Replay the retained hosted grant boundary; no synthetic expected ledger.

The compressed fixture records the independently derived pre-PREPARE group and
original grant captures from run 42418110516 / 3-REPLACE at source 5652d074.
Only the subsequent wire check is isolated; physical maintenance, grants,
capsules, ledgers and complete captured inventories use the real readers.
"""
import base64
import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joining_profile_continuation_evidence as e


def decoded(value):
    if isinstance(value,dict):
        if set(value)=={'base64'}:return base64.b64decode(value['base64'],validate=True)
        return {k:decoded(v) for k,v in value.items()}
    if isinstance(value,list):return [decoded(v) for v in value]
    return value


class ProfileDeferredPreparationTest(unittest.TestCase):
    def fixture(self):
        path=Path(__file__).with_name('fixtures')/'profile-deferred-preparation.json.gz'
        return decoded(json.loads(gzip.decompress(path.read_bytes())))

    def continuation(self,value):
        c=object.__new__(e.Continuation);c.root=Path('/unused-wire');c.replay=SimpleNamespace(root=value['root'])
        c.group=copy.deepcopy(value['group']);c.identifiers=set(value['identifiers']);c.voters=tuple(value['voters'])
        c.initialization=SimpleNamespace(voters=tuple(value['oldVoters']));c.joining=value['joining']
        compared=[]
        def match(node,files):
            e.need({k:v for k,v in files.items() if k!='.'}==value['captured'][node], 'fixture exact original capture')
            compared.append(node)
        c.captures=SimpleNamespace(counter=value['ballot']['counter'],original=lambda node,ballot:value['captured'][node],match=match)
        return c,compared

    def test_original_profile_compacts_superseded_source_after_fresh_promise(self):
        value=self.fixture();before=copy.deepcopy(value);c,compared=self.continuation(value)
        with patch.object(e,'prepared_exchanges',return_value={'wire':'separate gate'}) as wire:
            self.assertEqual({'wire':'separate gate'},c.preparation())
        self.assertEqual(value['oldVoters'],compared);wire.assert_called_once()
        self.assertEqual(before,value,'reader mutated retained original')
        for node in value['oldVoters']:
            initial=value['group'][node];self.assertTrue(e.deferred(initial,value['ballot']))
            old_sources={k for k in initial if k.startswith('sources/') and k.endswith('/source.gscp')}
            self.assertTrue(old_sources-set(c.group[node]),'obsolete source was not reclaimed')

    def test_wrong_or_truncated_captured_grants_cannot_authorize_reclamation(self):
        for mode in ('missing-prefix','wrong-promise'):
            with self.subTest(mode=mode):
                value=self.fixture();node=value['oldVoters'][0];files=value['captured'][node]
                rows=e.disk.journal(files['grants.gsr'],value['root'],node)
                if mode=='missing-prefix':files['grants.gsr']=b''.join(raw for _,raw,_ in rows[-2:])
                else:
                    promise=copy.deepcopy(rows[-2][2]);promise['ballot']['counter']+=1
                    files['grants.gsr']=b''.join(raw for _,raw,_ in rows[:-2])+e.f.encode('records','PROMISE',promise)+rows[-1][1]
                c,_=self.continuation(value)
                with patch.object(e,'prepared_exchanges') as wire,self.assertRaises(ValueError):c.preparation()
                wire.assert_not_called()

    def test_capture_cannot_omit_a_source_or_modify_frozen_content(self):
        for mode in ('missing-source','changed-packet'):
            with self.subTest(mode=mode):
                value=self.fixture();files=value['captured'][value['oldVoters'][0]]
                key=next(k for k in files if k.startswith('sources/') and k.endswith('/source.gscp'))
                if mode=='missing-source':del files[key]
                else:files[key]=files[key]+b'changed'
                c,_=self.continuation(value)
                with patch.object(e,'prepared_exchanges') as wire,self.assertRaisesRegex(ValueError,'exact original capture'):c.preparation()
                wire.assert_not_called()

    def test_inactive_generation_still_blocks_deferred_preparation(self):
        value=self.fixture();node=value['oldVoters'][0];files=value['group'][node]
        prefix,_,_=e.disk.current(files);files['generations/'+('b' if prefix=='generations/a/' else 'a')]=None
        c,_=self.continuation(value)
        with self.assertRaisesRegex(ValueError,'deferred predecessor still owned'):c.preparation()


if __name__=='__main__':unittest.main()
