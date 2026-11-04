"""Carried retirement admission and exact mutation boundaries."""
import copy
import unittest
from unittest.mock import patch
from . import carried_transition_retirement as r


def sample(kind):
    catalog=r.f.catalog();return r.f.sample(catalog['records'][kind]['schema'],catalog['types'])


class CarriedRetirementTest(unittest.TestCase):
    def test_covered_source_tail_requires_the_actual_published_floor(self):
        source=r.s.sources
        accept=sample('ACCEPT');accept.update(root='a'*64,index=5)
        floor=sample('FLOOR');floor.update(root='a'*64,node='node-1');floor['cut']['index']=5
        cap=dict(root=floor['root'],cut=copy.deepcopy(floor['cut']))
        raw=r.f.encode('records','ACCEPT',accept);packet=dict(objects={r.sha(raw):raw})
        for change in ('none','older','above','foreign-node','foreign-root','foreign-cut','foreign-accept'):
            vote=copy.deepcopy(accept);cut=copy.deepcopy(floor)
            if change=='older':vote['index']=4
            elif change=='above':vote['index']=6
            elif change=='foreign-node':cut['node']='node-2'
            elif change=='foreign-root':cut['root']='b'*64
            elif change=='foreign-cut':cut['cut']['index']=6
            elif change=='foreign-accept':vote['root']='b'*64
            raw=r.f.encode('records','ACCEPT',vote);packet=dict(objects={r.sha(raw):raw})
            files={'floor-copies/floor.gsr':r.f.encode('records','FLOOR',cut)}
            with self.subTest(change=change):
                if change in ('none','older'):source.published_tail(packet,r.sha(raw),files,'node-1',cap)
                else:
                    with self.assertRaisesRegex(ValueError,'uncovered source tail'):source.published_tail(packet,r.sha(raw),files,'node-1',cap)

    def successor(self,change=None):
        chosen=sample('SELECTED');chosen['ballot']['counter']=5
        payload=b'original carried command';entry=sample('ENTRY')
        entry.update(root=chosen['root'],authority=chosen['view'],index=chosen['cut']['index']+1,payload=r.sha(payload))
        raw_entry=r.f.encode('records','ENTRY',entry);chosen['nextEntry']=r.sha(raw_entry)
        vote=dict(root=chosen['root'],authority=chosen['view'],ballot=chosen['ballot'],entry=r.sha(raw_entry),index=entry['index'])
        tail=dict(vote,ballot=dict(vote['ballot'],counter=4));selected=r.f.encode('records','SELECTED',chosen)
        parts=dict(SELECTED=selected,ENTRY=raw_entry,ACCEPT=r.f.encode('records','ACCEPT',vote))
        members={'selected.gsr':selected,'promise.gsr':b'promise','owned-tail.gsr':r.f.encode('records','ACCEPT',tail)}
        packet=dict(capsule=dict(cut=chosen['cut']),objects={r.sha(raw_entry):raw_entry,r.sha(payload):payload})
        if change=='entry':parts['ENTRY']=r.f.encode('records','ENTRY',dict(entry,origin=dict(entry['origin'],counter=99)))
        elif change=='payload':payload=b'changed'
        elif change=='vote-ballot':parts['ACCEPT']=r.f.encode('records','ACCEPT',dict(vote,ballot=dict(vote['ballot'],counter=3)))
        elif change=='tail-ballot':members['owned-tail.gsr']=r.f.encode('records','ACCEPT',dict(tail,ballot=dict(tail['ballot'],counter=6)))
        elif change=='tail-entry':members['owned-tail.gsr']=r.f.encode('records','ACCEPT',dict(tail,entry='f'*64))
        elif change=='missing-original':packet['objects'].pop(r.sha(raw_entry))
        with patch.object(r.c,'current',return_value=('generations/a/',members,packet)):
            return r.current_successor({'selector.gsr':b'selector'},parts,payload)

    def test_successor_is_exact_original_command_at_current_selection_and_new_ballot(self):
        self.assertIsInstance(self.successor(),bytes)
        for change in ('entry','payload','vote-ballot','tail-ballot','tail-entry','missing-original'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'carried retirement (exact current successor|unchanged owned tail)'):self.successor(change)

    def test_projection_keeps_pending_vote_in_every_transient_inventory(self):
        files={'pending.accept':b'vote','keep':b'original'};projected=dict(files,**{'pending.accept':r.c.EMPTY})
        state=r.s.physical(projected)
        with patch.object(r.s,'generation_plan',return_value=(projected,[('first',state),('last',state)],{})) as plan:
            after,steps,_=r.generation_plan(files,'node-1',{},b'vote')
        self.assertEqual(r.c.EMPTY,plan.call_args.args[0]['pending.accept'])
        self.assertEqual(files,after);self.assertTrue(all(s==r.s.physical(files) for _,s in steps))
        self.assertEqual(b'vote',files['pending.accept'])
        for pending in (b'foreign',r.c.EMPTY):
            with self.assertRaisesRegex(ValueError,'exact pending projection'):r.generation_plan(files,'node-1',{},pending)
        with self.assertRaisesRegex(ValueError,'before application'):r.generation_plan(dict(files,**{'applied-end':None}),'node-1',{},b'vote')

    def test_invalid_kind_original_or_changed_inventory_refuse(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'exact kind'):r.validate('/unused','DATA')
        inventory.assert_not_called()
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.r,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'bad original'):r.validate('/unused','FINAL')
        replay.assert_not_called()
        with patch.object(r.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.r,'validate'),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/unused','FINAL')

    def test_failed_original_and_invalid_worker_count_prevent_negative_credit(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/unused','FINAL')
        negative.assert_not_called()
        for workers in (True,0,5,1.2):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/unused','FINAL',workers=workers)
            validate.assert_not_called()

    def test_retirement_negative_requires_unchanged_other_events_and_successful_retention(self):
        before=dict(files={'state':'a','events.json':'e'},directories=[])
        for change in ('file','event','retention','unrelated','accepted','correct'):
            after=copy.deepcopy(before);events=[dict(event='CURRENT_VALIDATED')];changed=copy.deepcopy(events)
            if change=='file':after['files']['state']='changed'
            if change=='event':changed[0]['event']='FLOOR_RELEASE_BEFORE_RETURN'
            reason=r.NEGATIVES['duplicate-delete']
            with patch.object(r.shutil,'copytree'),patch.object(r.s,'mutate'),patch.object(r.n.collection,'inventory',return_value=after),\
                 patch.object(r.n.collection,'read_json',side_effect=[events,changed]),\
                 patch.object(r.r,'replay',side_effect=ValueError('broken retention') if change=='retention' else None),\
                 patch.object(r,'replay',side_effect=None if change=='accepted' else ValueError('wrong' if change=='unrelated' else reason)):
                if change=='correct':self.assertEqual('PASS',r.negative('/unused','FINAL',before,'duplicate-delete')['retentionReplay'])
                else:
                    expected={'file':'original files','event':'other observations','retention':'broken retention','unrelated':'unrelated','accepted':'mutation accepted'}[change]
                    with self.subTest(change=change),self.assertRaisesRegex(ValueError,expected):r.negative('/unused','FINAL',before,'duplicate-delete')


if __name__=='__main__':unittest.main()
