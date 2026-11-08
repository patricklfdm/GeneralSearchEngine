"""Retained 42463390918 / 4-REPLACE grant race, not a native rerun.

The fixture holds independently derived predecessor files and original captured
and installed inventories. Exact physical reconstruction runs here; network and
force qualification remain mandatory on the whole retained history.
"""
import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from . import joining_profile_continuation_evidence as e
from .test_profile_deferred_preparation import decoded


class ProfileUnselectedPreparationTest(unittest.TestCase):
    def fixture(self):
        path=Path(__file__).with_name('fixtures')/'profile-unselected-preparation.json.gz'
        return decoded(json.loads(gzip.decompress(path.read_bytes())))

    def replay(self,value):
        c=object.__new__(e.Continuation);c.root=Path('/unused');c.replay=SimpleNamespace(root=value['root'])
        c.group=copy.deepcopy(value['group']);c.identifiers=set(value['identifiers']);c.voters=tuple(value['voters'])
        c.initialization=SimpleNamespace(voters=tuple(value['oldVoters']));c.joining=value['joining']
        compared=[]
        def match(node,files):
            e.need({k:v for k,v in files.items() if k!='.'}==value['captured'][node], 'fixture exact original capture')
            compared.append(node)
        c.captures=SimpleNamespace(by_ballot={(n,e.f.canonical(value['ballot'])):{} for n in value['captured']},
            original=lambda node,ballot:value['captured'][node],match=match)
        def installed(label):
            self.assertEqual('continuation-installed-9',label)
            for node,files in c.group.items():
                e.need({k:v for k,v in files.items() if k!='.'}==value['installed'][node], 'fixture exact installed inventory: '+node)
        c.match=installed
        # Standalone files duplicate the installed selected journals; no other
        # source/capture/installation check is mocked or substituted.
        from unittest.mock import patch
        with patch.object(Path,'read_bytes',side_effect=[value['installed'][n]['grants.gsr'] for n in c.voters]):
            c.install_campaign(value['cut'],value['ballot']['counter'],value['selected'])
        return c,compared

    def test_unselected_grant_is_derived_without_installing_or_voting(self):
        value=self.fixture();before=copy.deepcopy(value);c,compared=self.replay(value)
        self.assertEqual(['node-1','node-2','node-3','node-5'],compared)
        self.assertNotIn('node-5',c.voters)
        self.assertEqual(value['group']['node-5']['selector.gsr'],c.group['node-5']['selector.gsr'])
        self.assertNotEqual(value['group']['node-5']['grants.gsr'],c.group['node-5']['grants.gsr'])
        self.assertEqual(before,value)

    def test_missing_selected_or_foreign_capture_cannot_change_cohort(self):
        for change in ('missing-selected','foreign'):
            value=self.fixture()
            if change=='missing-selected':del value['captured']['node-2']
            else:value['captured']['node-99']=value['captured']['node-5']
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'campaign prepared owners'):self.replay(value)

    def test_unselected_source_is_compared_not_copied(self):
        for change in ('missing-source','changed-source','changed-journal'):
            value=self.fixture();files=value['captured']['node-5']
            key=next(k for k in files if k.startswith('sources/') and k.endswith('/source.gscp'))
            if change=='missing-source':del files[key]
            elif change=='changed-source':files[key]+=b'forged'
            else:files['grants.gsr']=value['group']['node-5']['grants.gsr']
            with self.subTest(change=change),self.assertRaises(ValueError):self.replay(value)

    def test_missing_unselected_grant_or_changed_final_file_is_rejected(self):
        for change in ('missing-capture','changed-installed'):
            value=self.fixture()
            if change=='missing-capture':del value['captured']['node-5']
            else:value['installed']['node-5']['unexplained']=b'bad'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'exact installed inventory: node-5'):self.replay(value)


if __name__=='__main__':unittest.main()
