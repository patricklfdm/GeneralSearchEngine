"""Original-source and causality guards; these fixtures are not native evidence."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import competing_campaign_prefix as c


def fixture():
    r=c.Replay.__new__(c.Replay);r.root=Path('/original')
    r.identities={node:dict(node=node,storage=f'00000000-0000-0000-0000-{i:012d}',host='127.0.0.1',port=19000+i)
                  for i,node in enumerate(('node-1','node-2','node-3'),1)}
    view=dict(generation=0,old=sorted(r.identities),new=sorted(r.identities),operation=None)
    root='a'*64; authority=c.sha(c.f.canonical(dict(root=root,**view)))
    ballot=dict(counter=2,proposer='node-1',incarnation=r.identities['node-1']['storage'])
    r.by_basis={};r.starts={};refs=[]
    for i,node in enumerate(('node-1','node-2'),1):
        value=dict(root=root,view=authority,ballot=ballot,basisId=f'00000000-0000-0000-0001-{i:012d}')
        promise=c.f.encode('records','PROMISE',value)
        basis=c.f.encode('records','BASIS',dict(value,voter=node,cut=dict(index=0,entry='b'*64,view=view),capsule='c'*64,inventory='d'*64,accepted=None))
        cap=dict(node=node,root=root,ballot=ballot,basisId=value['basisId'],basisSha256=c.sha(basis),
                 capturedEvent=1 if i==1 else 6,basis=basis,promise=promise)
        r.by_basis[c.sha(basis)]=cap;r.starts[c.sha(basis)]=0 if i==1 else 4
        refs.append(dict(voter=node,basisId=value['basisId'],basisDigest=c.sha(basis)))
    value=dict(root=root,view=authority,ballot=ballot,cut=dict(index=0,entry='b'*64,view=view),sources=refs,nextEntry=None)
    selected=c.f.encode('records','SELECTED',value);digest=c.sha(selected)
    r.selections={digest:dict(raw=selected,value=value)}
    r.bindings=[dict(node='node-1',selection=digest,forced=11),dict(node='node-2',selection=digest,forced=18)]
    r.events=[dict(node='node-3',event='NODE_OPEN') for _ in range(21)]
    for node,start in (('node-1',9),('node-2',16)):
        for i,point in enumerate(c.selection_writes.WRITES):r.events[start+i]=dict(node=node,event=point)
    own,peer=list(r.by_basis.values())
    request=dict(root=root,view=authority,ballot=ballot,sender=r.identities['node-1'],recipient=r.identities['node-2'],payload=dict(promise=c.sha(own['promise'])))
    r.attempts=[dict(kind='PREPARE',request=request,sent=2,received=3),
                dict(kind='SELECTED',request=dict(request,payload=dict(selection=digest)),sent=14,received=15)]
    r.rows=[dict(kind='PREPARE',answer='PROMISE',request=request,response=dict(payload=dict(basis=peer['basisSha256'])),offered=7,delivered=8)]
    return r


class CompetingCampaignPrefixTest(unittest.TestCase):
    def test_selected_sources_follow_original_grants_and_delivered_promise(self):
        r=fixture();self.assertEqual(dict(selections=2,callbacks=8),r.choices());r.grant_requests()

    def test_failed_unselected_requests_cannot_escape_original_authority_checks(self):
        for kind,reason in (('PREPARE','PREPARE send lacks original grant'),('SELECTED','SELECTED send lacks original decision')):
            with self.subTest(kind=kind):
                r=fixture();r.choices();row=copy.deepcopy(next(v for v in r.attempts if v['kind']==kind))
                row['received']=None;row['request']['recipient']=r.identities['node-3']
                row['request']['payload']={k:'0'*64 for k in row['request']['payload']};r.attempts.append(row)
                with self.assertRaisesRegex(ValueError,reason):r.grant_requests()

    def test_missing_late_or_substituted_promise_is_not_selected_authority(self):
        for fields in (dict(delivered=None),dict(delivered=12),dict(response=dict(payload=dict(basis='0'*64)))):
            with self.subTest(fields=fields):
                r=fixture();r.rows[0].update(fields)
                with self.assertRaisesRegex(ValueError,'selection before delivered promise'):r.choices()

    def test_remote_selection_requires_prior_original_proposer_force(self):
        for fields in (dict(sent=10),dict(received=19)):
            with self.subTest(fields=fields):
                r=fixture();r.attempts[1].update(fields)
                with self.assertRaisesRegex(ValueError,'remote selection before proposer'):r.choices()

    def test_every_selected_write_boundary_is_mandatory(self):
        for at in (9,10,12,16,17,19):
            with self.subTest(at=at):
                r=fixture();r.events[at]=dict(node=r.events[at]['node'],event='NODE_OPEN')
                reason='selection journal incomplete transaction' if at in (12,19) else 'selection journal complete write order'
                with self.assertRaisesRegex(ValueError,reason):r.choices()

    def test_original_basis_id_ballot_and_copy_order_are_checked(self):
        for fields in (dict(basisId='foreign'),dict(ballot=dict(counter=3,proposer='node-1',incarnation='foreign')),dict(capturedEvent=20)):
            with self.subTest(fields=fields):
                r=fixture();next(iter(r.by_basis.values())).update(fields)
                with self.assertRaisesRegex(ValueError,'original selected grant'):r.choices()

    def test_unowned_carried_entry_cannot_be_added_to_an_abandoned_selection(self):
        r=fixture();next(iter(r.selections.values()))['value']['nextEntry']='f'*64
        with self.assertRaisesRegex(ValueError,'exact derived selection'):r.choices()

    def test_remote_grant_needs_a_received_original_prepare(self):
        for received in (None,4,7):
            with self.subTest(received=received):
                r=fixture();r.attempts[0]['received']=received
                with self.assertRaisesRegex(ValueError,'grant after original PREPARE'):r.grant_requests()

    def test_grant_proposer_incarnation_is_not_a_diagnostic_label(self):
        r=fixture();r.identities['node-1']=dict(r.identities['node-1'],storage='changed')
        with self.assertRaisesRegex(ValueError,'proposer incarnation'):r.grant_requests()

    def test_later_grants_are_not_silently_counted_as_replayed_prefix(self):
        r=fixture();r.events[3]=dict(node='node-1',event='FLOOR_RESERVED')
        with self.assertRaisesRegex(ValueError,'later grant needs continuation replay'):r.physical_prefix()

    def test_new_retirement_vocabulary_does_not_accept_unknown_writes(self):
        self.assertIn('SOURCE_RETIREMENT_JOURNAL_PRUNED',c.p.OWNER_POINTS)
        self.assertIn('JOURNAL_ROTATION_PARENT_FORCED',c.p.OWNER_POINTS)
        self.assertNotIn('JOURNAL_ROTATION_UNKNOWN',c.p.OWNER_POINTS)

    def test_invalid_original_never_counts_as_negative_evidence(self):
        with patch.object(c,'validate',side_effect=ValueError('original')),patch.object(c,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):c.qualify('/invalid')
            mutate.assert_not_called()

    def test_unrelated_or_accepted_mutations_are_refused(self):
        for next_result,reason in ((ValueError('unrelated'),'unrelated negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(c,'validate',side_effect=[dict(competingBallots=2,distinctSelections=2),next_result]), \
                 patch.object(c.collection.h,'inventory',return_value={}),patch.object(c.g,'json_file',return_value=(b'', [dict(node='node-1')])), \
                 patch.object(c.shutil,'copytree'),patch.object(c,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):c.qualify('/original')


if __name__=='__main__':unittest.main()
