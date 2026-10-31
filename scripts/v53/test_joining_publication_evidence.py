import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_publication_evidence as j
from . import test_joining_catalog_evidence as fixture


class JoiningPublicationEvidenceTest(unittest.TestCase):
    def fixture(self):
        parts, parent, identities, root = fixture.JoiningCatalogEvidenceTest().phase()
        before = dict(parent, application='c'*64, identities=list(identities.values()))
        after = dict(before, cut=dict(parent['cut'], index=9, entry=j.sha(parts['ENTRY'])))
        replay = SimpleNamespace(root=root, states=[before]*9+[after], catalogs=[b'before']*9+[b'after'], phases=[{}]*8+[parts])
        point = j.anchor(replay, 8)
        plan = dict(root=root, view=parent['cut']['view'], peers=[dict(identity=identities[n], possible=[point])
                    for n in ('node-1', 'node-2', 'node-3')])
        files = {'selector.gsr': parts['SELECTOR'], 'node.gsr': j.f.encode('records', 'NODE', dict(root=root, identity=identities['node-2']))}
        state = dict(root=root, owner=identities['node-2'], revision=7, previous='e'*64, plan=plan)
        files[j.PEERS] = j.peers.frame(state)
        files[j.phases.future.FILE] = j.phases.future.frame(dict(j.phases.future.initial(files), revision=12, previous='d'*64), {})
        for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr'):
            files['applied-end/'+name] = ('original '+name).encode()
        members = dict(zip(('promise.gsr', 'selected.gsr'), (parts['PROMISE'], parts['SELECTED'])))
        return replay, files, state, members

    def promote(self, replay, files, members):
        with patch.object(j.disk, 'current', return_value=('', members, {})):
            return j.promoted_ledgers(replay, files, 9)

    def test_promotion_preserves_original_owner_other_peers_and_view(self):
        replay, files, old, members = self.fixture()
        # An authority change does not itself grant permission to reconcile the
        # peer ledger during this particular publication transaction.
        replay.states[9]['cut']['view'] = dict(replay.states[8]['cut']['view'], new=['node-1','node-2','node-3','node-4'], operation='f'*64)
        projected = self.promote(replay, files, members)
        value = j.peers.decode(projected[j.PEERS])
        self.assertEqual(old['owner'], value['owner'])
        self.assertEqual(old['plan']['view'], value['plan']['view'])
        self.assertEqual(old['plan']['peers'][0], value['plan']['peers'][0])
        self.assertEqual(old['plan']['peers'][2], value['plan']['peers'][2])
        self.assertEqual([j.anchor(replay, 8), j.anchor(replay, 9)], value['plan']['peers'][1]['possible'])
        self.assertEqual(8, value['revision'])
        self.assertEqual(j.sha(files[j.PEERS]), value['previous'])

    def test_promotion_preserves_renewal_debt(self):
        replay, files, state, members = self.fixture()
        point = copy.deepcopy(state['plan']['peers'][1]['possible'][0]); point['cut']['index'] = 7
        state['plan']['peers'][1]['renewals'] = [point]; files[j.PEERS] = j.peers.frame(state)
        value = j.peers.decode(self.promote(replay, files, members)[j.PEERS])
        self.assertEqual([point], value['plan']['peers'][1]['renewals'])

    def test_promotion_refuses_unbound_owner_or_dispatch_lower(self):
        for mode, reason in [('owner','joining publication peer owner'), ('lower','joining publication original dispatch endpoint')]:
            replay, files, state, members = self.fixture()
            if mode == 'owner': state['owner'] = replay.states[8]['identities'][0]
            else: state['plan']['peers'][1]['possible'][0] = j.anchor(replay, 7)
            # Fixture states 7/8 share a cut; make the changed lower explicit.
            if mode == 'lower': state['plan']['peers'][1]['possible'][0]['cut'] = dict(state['plan']['peers'][1]['possible'][0]['cut'], index=7)
            files[j.PEERS] = j.peers.frame(state)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^'+reason+'$'):
                self.promote(replay, files, members)

    def test_cleared_future_names_actual_proof_bytes_not_the_old_empty_state(self):
        replay, files, _, members = self.fixture(); projected = self.promote(replay, files, members)
        value = j.phases.empty_future(projected[j.phases.future.FILE], files)
        self.assertEqual(14, value['revision'])
        self.assertNotEqual(j.sha(files[j.phases.future.FILE]), value['previous'])
        changed = dict(files); changed['applied-end/ack.gsr'] = b'different original ACK'
        other = self.promote(replay, changed, members)
        self.assertNotEqual(projected[j.phases.future.FILE], other[j.phases.future.FILE])
        self.assertEqual(projected[j.PEERS], other[j.PEERS])

    def bridge(self):
        replay, _, _, _ = self.fixture()
        value = dict(root=replay.root, scope='RANGE', start=replay.states[8]['cut'], end=replay.states[9]['cut'],
                     catalogBefore=j.sha(b'before'), catalogAfter=j.sha(b'after'), applicationBefore='c'*64, applicationAfter='c'*64)
        replay.checkpoint = lambda start, end, kind: dict(value, scope=kind)
        statement = j.f.encode('records', 'CHECKPOINT', value); replay.acks = {}
        for identity in replay.states[9]['identities'][:2]:
            replay.acks[j.sha(statement), identity['node']] = j.f.encode('records', 'CHECKPOINT_ACK', dict(root=replay.root,
                voter=identity['node'], incarnation=identity['storage'], cut=value['end'], statement=j.sha(statement)))
        return replay, [statement, *replay.acks.values()]

    def test_retained_ancestry_requires_original_ordered_ack_bytes(self):
        replay, group = self.bridge(); original = b''.join(group)
        self.assertEqual({8: group}, j.original_bridges(replay, {'ancestry.gsr': original}))
        for changed in (group[:-1], [*group, group[-1]], [group[0], group[2], group[1]]):
            with self.subTest(count=len(changed)), self.assertRaisesRegex(ValueError, '^joining publication original ancestry$'):
                j.original_bridges(replay, {'ancestry.gsr': b''.join(changed)})

    def test_rehashed_ancestry_ack_still_needs_an_original_observation(self):
        replay, group = self.bridge(); value = j.f.decode(group[1], 'records', 'CHECKPOINT_ACK')
        value['statement'] = '0'*64; group[1] = j.f.encode('records', 'CHECKPOINT_ACK', value)
        with self.assertRaisesRegex(ValueError, '^joining publication original ancestry$'):
            j.original_bridges(replay, {'ancestry.gsr': b''.join(group)})

    def test_duplicate_ancestry_lower_is_rejected(self):
        replay, group = self.bridge()
        with self.assertRaisesRegex(ValueError, '^joining publication original ancestry$'):
            j.original_bridges(replay, {'ancestry.gsr': b''.join(group*2)})

    def test_unobserved_ack_cannot_create_a_checkpoint_majority(self):
        replay, _ = self.bridge(); replay.acks.pop(next(iter(replay.acks)))
        with self.assertRaisesRegex(ValueError, '^both governing majorities$'):
            j.checkpoint_group(replay, 8, 9, 'RANGE')

    def collected(self,*,change=None):
        from . import joining_transcript as transcript
        replay,group=self.bridge()
        # The joiner wrote a valid ACK, but the overlapping old pair suffices.
        replay.states[9]['cut']['view']=dict(replay.states[9]['cut']['view'],new=['node-1','node-2','node-4'])
        group=[j.f.encode('records','CHECKPOINT',replay.checkpoint(8,9,'RANGE')),*group[1:]];statement=j.sha(group[0])
        group=[group[0],*[j.f.encode('records','CHECKPOINT_ACK',dict(j.f.decode(raw,'records','CHECKPOINT_ACK'),
            cut=replay.states[9]['cut'],statement=statement)) for raw in group[1:]]]
        replay.acks={(statement,j.f.decode(raw,'records','CHECKPOINT_ACK')['voter']):raw for raw in group[1:]}
        identity=replay.states[9]['identities'][3]
        value=j.f.decode(group[1],'records','CHECKPOINT_ACK')
        extra=j.f.encode('records','CHECKPOINT_ACK',dict(value,voter='node-4',incarnation=identity['storage']))
        replay.acks[statement,'node-4']=extra
        local={'applied-end/ack.gsr':group[1]};replay.owner=lambda *args:local
        contents=[dict(kind='RECORD',raw=group[2],offer=dict(sent=11,request=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'))),
                       commit=dict(delivered=19))]
        if change:change(replay,local,contents)
        def transfers(rows,*,contents):contents.extend(self.contents);return {'committedTransfers':len(self.contents)}
        self.contents=contents
        with patch.object(j.semantic.collection,'read_json',return_value=[]),patch.object(transcript,'causal',return_value=[]) as causal, \
             patch.object(transcript,'transfers',side_effect=transfers),patch.object(j.phases,'blocks',return_value={(9,'node-1'):dict(APPLY_BEFORE_RETURN=10,PUBLICATION_VALIDATED=20)}):
            receipts=j.CheckpointReceipts(Path('/original'),replay)
        self.assertTrue(causal.call_args.kwargs['transfer_only'])
        return replay,group,receipts

    def test_publication_uses_only_original_delivered_acknowledgements(self):
        replay,group,receipts=self.collected();replay.publication_receipts=receipts
        self.assertEqual(3,len(replay.acks));self.assertEqual(1,receipts.transfers)
        self.assertEqual(group,j.checkpoint_group(replay,8,9,'RANGE',node='node-1'))
        # Retained ancestry may also contain this exact sufficient subset.
        self.assertEqual({8:group},j.original_bridges(replay,{'ancestry.gsr':b''.join(group)}))
        with self.assertRaisesRegex(ValueError,'^joining publication missing collected statement$'):
            j.checkpoint_group(replay,8,9,'RANGE',node='node-2')

    def test_unrequested_or_out_of_window_ack_cannot_supply_a_publication_majority(self):
        for mode in ('absent','early','late'):
            def change(replay,local,contents):
                if mode=='absent':contents.clear()
                elif mode=='early':contents[0]['offer']['sent']=10
                else:contents[0]['commit']['delivered']=20
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^both governing majorities$'):
                self.collected(change=change)

    def test_retained_ancestry_keeps_a_valid_subset_of_observed_acks(self):
        replay,group,_=self.collected()
        self.assertEqual(3,len(replay.acks))
        self.assertEqual({8:group},j.original_bridges(replay,{'ancestry.gsr':b''.join(group)}))

    def test_delivered_ack_requires_exact_observed_bytes_and_original_voter(self):
        for mode in ('duplicate','peer','statement','bytes','own'):
            def change(replay,local,contents):
                if mode=='duplicate':contents.append(copy.deepcopy(contents[0]))
                elif mode=='peer':contents[0]['offer']['request']['recipient']['node']='node-4'
                elif mode=='own':local['applied-end/ack.gsr']=contents[0]['raw']
                else:
                    value=j.f.decode(contents[0]['raw'],'records','CHECKPOINT_ACK')
                    value['statement' if mode=='statement' else 'incarnation']='e'*64 if mode=='statement' else '00000000-0000-0000-0000-000000000099'
                    contents[0]['raw']=j.f.encode('records','CHECKPOINT_ACK',value)
            reason='local' if mode=='own' else 'delivered'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^joining publication original '+reason+' ACK$'):
                self.collected(change=change)

    def test_invalid_original_is_never_negative_evidence(self):
        with patch.object(j, 'validate', side_effect=ValueError('original failed')), patch.object(j.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^original failed$'): j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_unrelated_failure_cannot_count_as_the_new_physical_check(self):
        with patch.object(j, 'validate', side_effect=[{}, ValueError('wrong gate')]), patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.semantic, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining unrelated publication negative:'): j.qualify(Path('/original'))

    def test_semantically_invalid_mutation_is_not_new_physical_evidence(self):
        with patch.object(j, 'validate', return_value={}) as physical, patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.semantic, 'validate', side_effect=ValueError('semantic failed')):
            with self.assertRaisesRegex(ValueError, '^semantic failed$'): j.qualify(Path('/original'))
            self.assertEqual(1, physical.call_count)

    def test_a_mutation_must_actually_be_rejected(self):
        with patch.object(j, 'validate', return_value={}), patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.semantic, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining publication mutation accepted:'): j.qualify(Path('/original'))


if __name__ == '__main__': unittest.main()
