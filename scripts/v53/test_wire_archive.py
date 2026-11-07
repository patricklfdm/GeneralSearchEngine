"""Registry, shared inventory and transport adapter checks; fixtures are not native evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import wire_archive as a
from . import connection_transcript as connection
from . import joining_transcript as transcript
from . import joining_phase_evidence as phase
from . import test_connection_transcript as fixture
from . import test_joining_network_evidence as legacy_fixture


class WireArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def save(self,path,value):path.write_bytes(a.segmented.f.canonical(value))

    def original(self,histories=None,missing=()):
        root=self.root/a.DIRECTORY;root.mkdir();entries=[]
        histories=histories or {name:[{'first':True},{'later':True}] for name in a.LIMITS}
        for name,rows in sorted(histories.items()):
            base=root/name[:-5];base.mkdir();(base/'segments').mkdir();(base/'cuts').mkdir()
            observed=name!='wire.json' and name not in missing;parts=[rows[:1],rows[1:]] if observed else [rows];segments=[]
            for part in parts:
                if not part:continue
                filename=f'segment-{len(segments):04d}.jsonl';raw=b''.join(a.segmented.f.canonical(row)+b'\n' for row in part)
                (base/'segments'/filename).write_bytes(raw)
                segments.append(dict(path=filename,rows=len(part),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            def index(parts):return dict(schema=a.segmented.SCHEMA,rows=sum(v['rows'] for v in parts),bytes=sum(v['bytes'] for v in parts),segments=parts)
            self.save(base/'complete.json',index(segments));digest=None
            if observed:
                self.save(base/'cuts/observed.json',index(segments[:1]));digest=hashlib.sha256((base/'cuts/observed.json').read_bytes()).hexdigest()
            entries.append(dict(file=name,completeSha256=hashlib.sha256((base/'complete.json').read_bytes()).hexdigest(),observedSha256=digest))
        registry=dict(schema=a.SCHEMA,histories=entries);self.save(root/'index.json',registry);return registry

    def open(self,**kwargs):return a.Archive(self.root,bootstrap_source=a.source.BACKUP,**kwargs)

    def test_six_logical_histories_bind_complete_lifetime_and_original_auxiliary_cut(self):
        self.original();reader=self.open()
        for name in a.LIMITS:
            rows=reader.read(name);self.assertEqual(2 if name=='wire.json' else 1,len(rows))
            self.assertEqual(2,rows.complete['rows']);self.assertEqual({'first':True},rows[0])
        reader.check_unchanged()

    def test_shared_cap_counts_all_histories_and_metadata_before_payload_decode(self):
        self.original();total=sum(p.stat().st_size for p in (self.root/a.DIRECTORY).rglob('*') if p.is_file())
        self.assertEqual(total,self.open(maximum=total).before['bytes'])
        with patch.object(a.segmented,'Reader') as decode:
            with self.assertRaisesRegex(ValueError,'shared byte capacity'):self.open(maximum=total-1)
            decode.assert_not_called()

    def test_source_and_layout_are_explicit_and_cannot_be_selected_by_files(self):
        self.original()
        with self.assertRaisesRegex(ValueError,'unexpected layout'):a.read(self.root,'wire.json')
        for source in (a.source.EMPTY,None,'from-receipt'):
            with self.subTest(source=source),self.assertRaises(ValueError):a.read('/absent','wire.json',bootstrap_source=source,layout=a.SEGMENTED)
        rows=a.read(self.root,'wire.json',bootstrap_source=a.source.BACKUP,layout=a.SEGMENTED)
        self.assertEqual(2,len(rows))
        with self.assertRaisesRegex(ValueError,'explicit layout'):a.read('/absent','wire.json',layout='automatic')

    def test_legacy_reader_keeps_original_names_and_capacities(self):
        for name,maximum in a.LIMITS.items():
            with self.subTest(name=name),patch.object(a.legacy,'read_json',return_value=[]) as read:
                self.assertEqual([],a.read(self.root,name));read.assert_called_once_with(self.root,name,maximum)
        with self.assertRaisesRegex(ValueError,'logical name'):a.read(self.root,'../wire.json')

    def test_registry_rejects_missing_main_duplicates_unknown_shapes_and_order(self):
        original=self.original();path=self.root/a.DIRECTORY/'index.json'
        for mutation in ('main','duplicate','order','extra','name','main-cut'):
            value=copy.deepcopy(original)
            if mutation=='main':value['histories']=[r for r in value['histories'] if r['file']!='wire.json']
            elif mutation=='duplicate':value['histories'][1]=value['histories'][0]
            elif mutation=='order':value['histories'].reverse()
            elif mutation=='extra':value['maximum']=a.segmented.MAXIMUM
            elif mutation=='name':value['histories'][0]['file']='../outside.json'
            else:next(r for r in value['histories'] if r['file']=='wire.json')['observedSha256']='a'*64
            self.save(path,value)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.open()

    def test_complete_and_cut_bytes_must_match_registry_hashes(self):
        original=self.original();path=self.root/a.DIRECTORY/'index.json'
        for key in ('completeSha256','observedSha256'):
            value=copy.deepcopy(original);value['histories'][0][key]='a'*64;self.save(path,value)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'binding'):self.open()

    def test_missing_observed_cut_cannot_be_replaced_by_final_lifetime(self):
        self.original(missing=('joining-head-wire.json',));reader=self.open()
        with self.assertRaisesRegex(ValueError,'missing observed cut'):reader.read('joining-head-wire.json')
        self.assertEqual(2,len(reader.read('wire.json')))

    def test_unknown_or_unlisted_history_and_cut_are_not_silently_ignored(self):
        self.original();root=self.root/a.DIRECTORY
        extra=root/'unknown';extra.mkdir()
        with self.assertRaisesRegex(ValueError,'inventory'):self.open()
        extra.rmdir();extra=root/'wire/cuts/foreign.json';extra.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'exact cuts'):self.open()

    def test_legacy_alias_and_staging_conflict_are_rejected(self):
        self.original()
        for name in ('wire.json','auxiliary-wire-spools'):
            path=self.root/name;path.write_bytes(b'[]')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'legacy conflict'):self.open()
            path.unlink()

    def test_linked_payload_refused_before_any_history_is_admitted(self):
        self.original();path=self.root/a.DIRECTORY/'wire/segments/segment-0000.jsonl';retained=self.root/'retained'
        path.rename(retained);path.symlink_to(retained)
        with self.assertRaisesRegex(ValueError,'regular file'):self.open()

    def test_registry_change_after_read_and_missing_history_are_rejected(self):
        value=self.original({'wire.json':[{'row':1}]});reader=self.open()
        with self.assertRaisesRegex(ValueError,'missing history'):reader.read('joining-head-wire.json')
        value['schema']='changed';self.save(self.root/a.DIRECTORY/'index.json',value)
        with self.assertRaisesRegex(ValueError,'changed'):reader.read('wire.json')

    def test_connection_and_causal_readers_accept_checked_rows_without_weakening_bindings(self):
        events,wires,ids,root=fixture.trace();self.original({'wire.json':wires});checked=self.open().read('wire.json')
        self.assertEqual(connection.replay(events,wires,ids,root),connection.replay(events,checked,ids,root))
        self.assertEqual(transcript.causal(events,wires,ids,root),transcript.causal(events,checked,ids,root))
        changed=copy.deepcopy(events);changed[-1]['response']='a'*64
        with self.assertRaisesRegex(ValueError,'delivered response binding'):connection.replay(changed,checked,ids,root)

    def test_legacy_causal_vocabulary_keeps_all_checks_with_segmented_input(self):
        events,wires,ids,root=legacy_fixture.JoiningNetworkEvidenceTest().exchange(True)
        self.original({'wire.json':wires});checked=self.open().read('wire.json')
        self.assertEqual(phase.exchanges(events,wires,ids,root),phase.exchanges(events,checked,ids,root))
        self.assertEqual(transcript.causal(events,wires,ids,root),transcript.causal(events,checked,ids,root))

    def test_arbitrary_sequences_cannot_claim_checked_segmented_input(self):
        events,wires,ids,root=fixture.trace()
        for value in (tuple(wires),iter(wires),type('Unvalidated', (list,), {})(wires)):
            with self.subTest(value=type(value)),self.assertRaisesRegex(ValueError,'bounded observations'):
                connection.replay(events,value,ids,root)


if __name__=='__main__':unittest.main()
