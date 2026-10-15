"""Small oracle boundary tests; actual authority bytes are exercised by the process gate."""
import base64
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from . import public_reads_evidence as e


def blob(value):return struct.pack('>i',len(value))+value
def document(key,value):return struct.pack('>i',key)+value.encode()
def application(docs):
    return b'\0\1'+struct.pack('>ii',0,len(docs))+b''.join(blob(struct.pack('>i',k))+blob(document(k,v)) for k,v in docs)
def b64(value):return base64.b64encode(value).decode()


class PublicReadEvidenceTest(unittest.TestCase):
    def test_same_voter_retries_or_different_ballots_are_not_a_quorum(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'node-1').mkdir();(root/'node-1/manifest.gsr').write_bytes(b'x'*48);(root/'node-1/genesis.gsr').write_bytes(b'g')
            def vote(epoch):return dict(epoch=epoch,incarnation='incarnation',entryDigest='digest',entry=dict(index=1))
            def row(value):return dict(event='FORCE',kind='ACCEPT',record=value)
            with patch.object(e.physical.f,'inspect',return_value={}),patch.object(e.physical,'frame',side_effect=lambda value,*args:value):
                self.assertEqual({},e.context(root,{'node-1':[row(vote(2)),row(vote(2))],'node-2':[row(vote(3))]})[2])
                self.assertEqual({'digest':dict(index=1)},e.context(root,{'node-1':[row(vote(2))],'node-2':[row(vote(2))]})[2])

    def test_noop_progress_is_distinct_from_imported_and_mutation_sequence(self):
        initial=[(1,'old')];payload=b'\0\1'+struct.pack('>i',1)+blob(struct.pack('>i',2))+blob(document(2,'new'))
        genesis=dict(baseSequence=41,application=b64(application(initial)))
        entries={'noop':dict(index=1,operation=9,payload=''),'bulk':dict(index=2,operation=4,payload=b64(payload))}
        snapshot=dict(anchors=[dict(entryDigest='noop'),dict(entryDigest='bulk')],applicationSequence=42,
                      application=b64(application([*initial,(2,'new')])))
        value=e.prefix(snapshot,dict(historyId='history'),genesis,entries)
        self.assertEqual(42,value['sequence']);self.assertEqual([9,4],[v['operation'] for v in value['commands']])
        snapshot['applicationSequence']=43
        with self.assertRaisesRegex(ValueError,'differs from chosen prefix'):e.prefix(snapshot,dict(historyId='history'),genesis,entries)

    def test_missing_chosen_entry_cannot_be_replaced_by_token_progress(self):
        genesis=dict(baseSequence=0,application=b64(application([])))
        snapshot=dict(anchors=[dict(entryDigest='unproven')],applicationSequence=0,application=genesis['application'])
        with self.assertRaisesRegex(ValueError,'unobserved read ancestor'):e.prefix(snapshot,dict(historyId='h'),genesis,{})

    def test_invalid_original_is_not_counted_as_successful_negative_qualification(self):
        with patch.object(e,'traces_at',return_value={}),patch.object(e,'read',return_value=[]),\
                patch.object(e,'validate',side_effect=ValueError('invalid original')) as validate:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.negatives(Path('/unused'),{}, {})
            self.assertEqual(1,validate.call_count)


if __name__=='__main__':unittest.main()
