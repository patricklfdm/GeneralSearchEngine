import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import discovered_service_evidence as d
from . import discovered_service_negatives as n


class DiscoveredServiceEvidenceTest(unittest.TestCase):
    def test_invalid_physical_original_stops_before_service_network(self):
        with patch.object(d,'physical',side_effect=ValueError('invalid original')), patch.object(d,'slot_network') as network:
            with self.assertRaisesRegex(ValueError,'^invalid original$'): d.inspect('unused')
            network.assert_not_called()

    def test_negative_qualification_does_not_repair_original(self):
        with patch.object(d,'inspect',side_effect=ValueError('invalid original')), patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'): n.qualify('unused')
            copied.assert_not_called()

    def test_original_failed_diagnostics_never_grant_authority(self):
        row = dict(node='node-3',kind='CHUNK',request='a'*64,
            failure='java.lang.IllegalArgumentException: activation endpoint scope unavailable')
        with patch.object(d.native,'read',return_value=[row]*3):
            self.assertEqual(dict(records=3,exchanges=1,authority=False,requestBodiesRetained=False),
                             d.rejection_diagnostics(Path('unused')))
        for rows in ([row]*4,[dict(row,node='node-2')],[dict(row,failure='timeout')]):
            with self.subTest(rows=rows), patch.object(d.native,'read',return_value=rows), self.assertRaises(ValueError):
                d.rejection_diagnostics(Path('unused'))

    @staticmethod
    def source(sequence, offered, deliveries):
        return dict(request=dict(trace='transfer',sequence=sequence,sender=dict(node='node-1'),
            recipient=dict(node='node-2'),payload=dict(digest='a'*64)),offered=offered,deliveries=deliveries,
            row=dict(request='request-'+str(sequence),response='response-'+str(sequence)))

    def test_source_progress_requires_received_previous_chunk(self):
        rows = [self.source(1,1,[4]),self.source(2,5,[6])]
        self.assertEqual(6,d.Transfers(rows,{},{}).available[0]['delivered'])
        rows[1]['offered'] = 3
        with self.assertRaisesRegex(ValueError,'^discovered service source delivery order$'): d.Transfers(rows,{},{})

    def test_missing_middle_source_message_is_not_a_complete_trace(self):
        rows = [self.source(1,1,[2]),self.source(3,3,[4])]
        with self.assertRaisesRegex(ValueError,'^discovered service contiguous source trace$'): d.Transfers(rows,{},{})

    def test_late_response_can_finish_three_identical_source_attempts(self):
        rows = [self.source(1,1,[]),self.source(1,2,[]),self.source(1,3,[4]),self.source(2,5,[6])]
        self.assertEqual(1,d.Transfers(rows,{},{}).count)
        changed = copy.deepcopy(rows); changed[1]['row']['response'] = 'other'
        with self.assertRaisesRegex(ValueError,'^discovered selection identical bounded attempts$'): d.Transfers(changed,{},{})

    def test_received_diagnostic_without_any_actual_offer_is_rejected(self):
        events = [dict(node='node-5',event='ROUND_ADOPTED'),dict(node='node-4',event='ROUND_ADOPTED'),
            dict(node='node-4',event='ROUND_INSTALLED'),dict(node='node-4',event='NETWORK_RECEIVED',kind='CHUNK',response='a'*64)]
        with patch.object(d.native,'read',return_value=[]):
            with self.assertRaisesRegex(ValueError,'^discovered service received without original offer$'):
                d.network_coverage(Path('unused'),events,[(4,6),(7,9)])

    def test_missing_peer_is_not_silently_added_to_service_checkpoint(self):
        service = object.__new__(d.Service)
        view = dict(old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3','node-4'],operation=None)
        self.assertEqual({'node-1','node-2','node-4'},service.checkpoint_voters(view,'node-4'))
        for node,other in [('node-3',view),('node-4',dict(view,new=view['new'][:-1]))]:
            with self.subTest(node=node), self.assertRaisesRegex(ValueError,'^discovered service stable checkpoint quorum$'):
                service.checkpoint_voters(other,node)

    def test_shared_reader_still_requires_both_checkpoint_majorities(self):
        reader = object.__new__(d.transition.NativeSlot)
        for size in (3,4,5):
            old=['node-'+str(i) for i in range(1,size+1)];new=old[:-1]
            for node in old:
                chosen=reader.checkpoint_voters(dict(old=old,new=new),node)
                self.assertGreater(len(chosen&set(old)),len(old)//2)
                self.assertGreater(len(chosen&set(new)),len(new)//2)
                self.assertIn(node,chosen)


if __name__ == '__main__': unittest.main()
