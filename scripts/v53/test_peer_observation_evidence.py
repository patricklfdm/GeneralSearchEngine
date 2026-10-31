"""Conditional expected-ledger checks; they do not establish copy durability."""
import base64
import copy
import unittest
from unittest.mock import patch
from . import peer_observation_evidence as e
from .test_peer_confirmation_evidence import fixture


def inputs():
    state, generation = fixture(); old = copy.deepcopy(state['plan']['peers'][2]['renewals'][0])
    for row in state['plan']['peers']:
        row.pop('confirmation', None); row.pop('renewals', None); row['possible'] = [copy.deepcopy(old)]
    state.update(revision=0, previous=None)
    return state, generation, state['plan']['peers'][2]['identity']


class PeerObservationEvidenceTest(unittest.TestCase):
    def test_genesis_retains_exact_bytes_and_does_not_create_revision(self):
        state, generation, peer = inputs(); record=e.f.decode(generation,'records','GENERATION')
        record.update(state['plan']['peers'][2]['possible'][0]); raw=e.r.frame(state)
        self.assertEqual(raw,e._observed(raw,peer,e.f.encode('records','GENERATION',record)))

    def test_real_observation_retains_old_renewal_and_later_unconfirmed_target(self):
        state, generation, peer = inputs(); future=copy.deepcopy(state['plan']['peers'][2]['possible'][0]);future['cut']['index']=3
        state['plan']['peers'][2]['possible'].append(future);raw=e.r.frame(state)
        value=e.r.decode(e._observed(raw,peer,generation));row=value['plan']['peers'][2]
        self.assertEqual([2,3],[v['cut']['index'] for v in row['possible']])
        self.assertEqual([0],[v['cut']['index'] for v in row['renewals']])
        self.assertEqual(generation,base64.b64decode(row['confirmation']))
        self.assertEqual((1,e.r.sha(raw)),(value['revision'],value['previous']))

    def test_equivalent_or_older_observation_preserves_original_proof_bytes(self):
        state,generation,peer=inputs();raw=e._observed(e.r.frame(state),peer,generation)
        record=e.f.decode(generation,'records','GENERATION');record['generation']='b'
        self.assertEqual(raw,e._observed(raw,peer,e.f.encode('records','GENERATION',record)))
        record['cut']['index']=1
        self.assertEqual(raw,e._observed(raw,peer,e.f.encode('records','GENERATION',record)))

    def test_foreign_manifest_and_recycled_identity_refuse_before_noop(self):
        state,generation,peer=inputs();raw=e.r.frame(state)
        for field,value in (('node','node-2'),('root','f'*64),('view',dict(state['plan']['view'],generation=1))):
            record=e.f.decode(generation,'records','GENERATION');record['cut']['index']=0
            if field=='view':record['cut']['view']=value
            else:record[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):e._observed(raw,peer,e.f.encode('records','GENERATION',record))
        with self.assertRaisesRegex(ValueError,'permanent identity'):e._observed(raw,dict(peer,storage='00000000-0000-0000-0000-000000000099'),generation)

    def test_conflicting_endpoint_and_renewal_capacity_are_not_discarded(self):
        state,generation,peer=inputs();point={k:v for k,v in e.f.decode(generation,'records','GENERATION').items() if k in ('cut','catalog','application')}
        state['plan']['peers'][2]['possible']=[dict(point,catalog='f'*64)]
        with self.assertRaisesRegex(ValueError,'conflicting endpoint'):e._observed(e.r.frame(state),peer,generation)
        state,generation=fixture();peer=state['plan']['peers'][2]['identity'];record=e.f.decode(generation,'records','GENERATION');record['cut']['index']=3
        with self.assertRaisesRegex(ValueError,'renewal capacity'):e._observed(e.r.frame(state),peer,e.f.encode('records','GENERATION',record))

    def test_incomplete_original_inventory_cannot_reach_metadata_projection(self):
        with patch.object(e,'_observed') as projection:
            with self.assertRaises(KeyError):e.observe_same_cut(b'not-authority',{}, {})
            projection.assert_not_called()

    def test_explicit_maintenance_defers_third_renewal_without_any_write(self):
        state,generation=fixture();peer=state['plan']['peers'][2]['identity']
        record=e.f.decode(generation,'records','GENERATION');record['cut']['index']=3
        observed=e.f.encode('records','GENERATION',record)
        for later in (False,True):
            before=copy.deepcopy(state)
            if later:before['plan']['peers'][2]['possible'].append({k:record[k] for k in ('cut','catalog','application')})
            raw=e.r.frame(before)
            self.assertEqual(raw,e._observed(raw,peer,observed,defer_renewal=True))
            with self.assertRaisesRegex(ValueError,'renewal capacity'):e._observed(raw,peer,observed)

    def test_full_debt_does_not_suppress_original_validation(self):
        state,generation=fixture();peer=state['plan']['peers'][2]['identity']
        record=e.f.decode(generation,'records','GENERATION');record['cut']['index']=3
        for field,value in (('root','f'*64),('node','node-2')):
            bad=dict(record,**{field:value})
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'root/identity'):
                e._observed(e.r.frame(state),peer,e.f.encode('records','GENERATION',bad),defer_renewal=True)
        state['plan']['peers'][2]['possible'].append({k:record[k] for k in ('cut','catalog','application')})
        record['catalog']='f'*64
        with self.assertRaisesRegex(ValueError,'conflicting endpoint'):
            e._observed(e.r.frame(state),peer,e.f.encode('records','GENERATION',record),defer_renewal=True)


if __name__=='__main__':unittest.main()
