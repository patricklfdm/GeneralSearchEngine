"""Selection journal coverage is exercised through its actual network consumers."""
import unittest
from . import test_joining_same_view_network as joining
from . import test_remove_activation_writes as remove


def fixture(role):
    if role.startswith('remove'):
        return remove.fixture(), ('node-1' if role=='remove-proposer' else 'node-2'), remove.RemoveActivationWritesTest().check
    data=joining.fixture()
    if role=='proposer':
        # Same explicit writer sequence, but an ordinary joining-owner campaign
        # at cut 9 rather than the separately admitted final recovery at cut 11.
        events,rows,replay,bases,raw,members=data;value=joining.n.f.decode(raw,'records','SELECTED')
        value['cut']['index']=9;raw=joining.n.f.encode('records','SELECTED',value);digest=joining.n.sha(raw)
        members['selected.gsr']=raw;replay.phases=[dict(SELECTED=raw)]
        rows[-1]['request']['payload']=dict(selection=digest);rows[-1]['response']['payload']=dict(selection=digest,cut=value['cut'])
        events.append(dict(node='node-4',scope='continuation-owner',event='ACCEPT_VALIDATED'))
        # Cold reopen is not an ordinary next-slot boundary.
        events[-2]['event']='ORDINARY_BOUNDARY'
        return data,'node-4',lambda value:joining.JoiningSameViewNetworkTest().check(value,explicit=False)
    return data, ('node-1' if role=='remote' else 'node-4'), joining.JoiningSameViewNetworkTest().check


def reindex(data, before):
    events,rows=data[:2]
    positions={id(row):i for i,row in enumerate(events)}
    for row in rows:
        for field in ('sent','received','offered','delivered'):
            if type(row.get(field)) is int:row[field]=positions[id(before[row[field]])]


ROLES=('proposer','remote','recovery','remove-proposer','remove-remote')


class SelectionJournalBindingTest(unittest.TestCase):
    def test_complete_transactions_retain_all_consumers(self):
        for role in ROLES:
            data,_,check=fixture(role)
            with self.subTest(role=role):check(data)

    def test_each_missing_write_boundary_is_rejected(self):
        for role in ROLES:
            for point in ('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN'):
                data,node,check=fixture(role)
                next(v for v in data[0] if v.get('node')==node and v['event']==point)['event']='OMITTED'
                with self.subTest(role=role,point=point),self.assertRaisesRegex(ValueError,'^selection journal complete write order$'):check(data)

    def test_duplicated_reordered_or_foreign_writes_cannot_borrow_a_force(self):
        for role in ROLES:
            for change in ('duplicate','reorder','scope','shape'):
                data,node,check=fixture(role);events=data[0];before=list(events)
                at=next(i for i,v in enumerate(events) if v.get('node')==node and v['event']=='SELECTED_WRITTEN')
                if change=='duplicate':events.insert(at,dict(events[at]));reindex(data,before)
                elif change=='reorder':events[at],events[at+1]=events[at+1],events[at]
                elif change=='scope':events[at]['scope']='other-owner'
                else:events[at]['claimedWrite']=True
                reason='callback shape' if change=='shape' else 'complete write order'
                with self.subTest(role=role,change=change),self.assertRaisesRegex(ValueError,'^selection journal '+reason+'$'):check(data)

    def test_writes_cannot_precede_original_promise_delivery_or_request(self):
        for role in ROLES:
            data,node,check=fixture(role);events,rows=data[:2];before=list(events)
            remote=role in ('remote','remove-remote')
            lower=rows[-1]['received'] if remote else rows[0]['delivered']
            boundary=events[lower]
            writes=[v for v in events if v.get('node')==node and v['event'] in ('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN')]
            for v in writes:events.remove(v)
            at=next(i for i,v in enumerate(events) if v is boundary);events[at:at]=writes;reindex(data,before)
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'^selection journal original authority interval$'):check(data)

    def test_unbound_and_unknown_callbacks_cannot_disappear(self):
        for role in ROLES:
            for point,reason in (('SELECTED_WRITTEN','complete write order'),('SELECTED_UNKNOWN','unsupported callback')):
                data,node,check=fixture(role);data[0].append(dict(node=node,event=point))
                with self.subTest(role=role,point=point),self.assertRaisesRegex(ValueError,'^selection journal '+reason+'$'):check(data)


if __name__=='__main__':unittest.main()
