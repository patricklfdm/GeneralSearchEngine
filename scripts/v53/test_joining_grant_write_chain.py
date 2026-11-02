"""Complete original grant-write boundaries, independent of final snapshot bytes."""
from pathlib import Path
import copy
import unittest
from unittest.mock import patch
from . import joining_network_evidence as n


def fixture(images=1):
    # From the native writer's ordinary first-capture transaction. Deliberately
    # do not call the reader's sequence builder to construct these observations.
    names=['CURRENT_BEFORE_CAPTURE','PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED',
        'CAPTURE_INTENT_CREATED','CAPTURE_INTENT_PREFIX_WRITTEN','CAPTURE_INTENT_WRITTEN','CAPTURE_INTENT_FORCED','CAPTURE_INTENT_PARENT_FORCED',
        'SOURCE_BEFORE_CREATE','SOURCE_CREATED','SOURCE_PACKET_CREATED','SOURCE_PACKET_PREFIX_WRITTEN','SOURCE_PACKET_WRITTEN','SOURCE_PACKET_FORCED']
    names+=['SOURCE_IMAGE_CREATED','SOURCE_IMAGE_PREFIX_WRITTEN','SOURCE_IMAGE_WRITTEN','SOURCE_IMAGE_FORCED']*images
    names+=['SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_BEFORE_WRITE','BASIS_PREFIX_WRITTEN','BASIS_WRITTEN','BASIS_FORCED',
        'CAPTURE_INTENT_DELETED','CAPTURE_INTENT_CLEARED','GRANT_BEFORE_RETURN','GRANT_CAPTURED']
    return [dict(node='node-1',event=point) for point in names]


class JoiningGrantWriteChainTest(unittest.TestCase):
    def check(self,events,images=1,scope=None):
        end=next(i for i,v in enumerate(events) if v['event']=='GRANT_BEFORE_RETURN')
        capture=dict(node='node-1',scope=scope or 'network-owner',capture='grant-captures/one',root='a'*64,
            returnEvent=end,capturedEvent=end+1,basisId='original',basisSha256=n.sha(b'basis'),
            ballot=dict(counter=1,proposer='node-1',incarnation='original'))
        members={'grants.gsr':b'journal','sources/original/source.gscp':b'packet'}
        journal=[('PROMISE',b'promise',{}),('BASIS',b'basis',dict(view='view'))]
        with patch.object(n.p.captures,'collect',return_value=[capture]),patch.object(n.disk,'inventory',return_value=members), \
             patch.object(n.disk,'journal',return_value=journal),patch.object(n.disk.p,'decode',return_value=dict(images={str(i):1 for i in range(images)})):
            return n.grants(Path('/conditional'),events,[])

    def test_complete_single_and_multiple_original_images(self):
        for images in (0,1,2):
            result,_=self.check(fixture(images),images)
            self.assertEqual(1,result['forcedGrants'])

    def test_every_created_prefix_written_and_deleted_boundary_is_mandatory(self):
        names=['PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','CAPTURE_INTENT_CREATED','CAPTURE_INTENT_PREFIX_WRITTEN',
               'CAPTURE_INTENT_WRITTEN','SOURCE_BEFORE_CREATE','SOURCE_CREATED','SOURCE_PACKET_CREATED','SOURCE_PACKET_PREFIX_WRITTEN',
               'SOURCE_PACKET_WRITTEN','SOURCE_IMAGE_CREATED','SOURCE_IMAGE_PREFIX_WRITTEN','SOURCE_IMAGE_WRITTEN',
               'BASIS_BEFORE_WRITE','BASIS_PREFIX_WRITTEN','BASIS_WRITTEN','CAPTURE_INTENT_DELETED']
        for name in names:
            events=fixture();events.pop(next(i for i,v in enumerate(events) if v['event']==name))
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(events)

    def test_wrong_scope_or_extra_callback_fields_are_not_original_owner_events(self):
        for change in ({'scope':'other-owner'},{'unbound':'claim'}):
            events=fixture();next(v for v in events if v['event']=='BASIS_WRITTEN').update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(events)

    def test_joining_owner_scope_is_preserved(self):
        events=fixture()
        for row in events:row['scope']='continuation-owner'
        self.check(events,scope='continuation-owner')

    def test_duplicate_and_reordered_writes_reject(self):
        for changed in ('duplicate','reordered'):
            events=fixture();at=next(i for i,v in enumerate(events) if v['event']=='BASIS_PREFIX_WRITTEN')
            if changed=='duplicate':events.insert(at,dict(events[at]))
            else:events[at],events[at+1]=events[at+1],events[at]
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(events)

    def test_original_image_count_determines_complete_write_multiplicity(self):
        with self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(fixture(1),2)

    def test_late_or_early_writes_cannot_borrow_another_transaction(self):
        for where in ('before','after'):
            events=fixture();at=next(i for i,v in enumerate(events) if v['event']=='SOURCE_PACKET_PREFIX_WRITTEN');row=events.pop(at)
            events.insert(0 if where=='before' else len(events),row)
            with self.subTest(where=where),self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(events)

    def test_foreign_owner_unknown_and_orphan_capture_callbacks_reject(self):
        for extra in (dict(node='foreign',event='BASIS_WRITTEN'),dict(node='node-1',event='CAPTURE_INTENT_UNKNOWN'),
                      dict(node='node-1',event='SOURCE_PACKET_WRITTEN')):
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'^joining network unbound grant capture callback$'):
                self.check([*fixture(),extra])

    def test_unrelated_callbacks_do_not_create_spurious_capture_boundaries(self):
        events=fixture();events.insert(2,dict(node='node-2',event='NETWORK_RECEIVED'))
        events.append(dict(node='node-1',event='SOURCE_RETIREMENT_CLEARED'));self.check(events)
