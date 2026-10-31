import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_transition_evidence as j
from . import test_joining_catalog_evidence as fixture


class JoiningTransitionEvidenceTest(unittest.TestCase):
    def owners(self):
        parts, parent, identities, root = fixture.JoiningCatalogEvidenceTest().phase()
        active = j.f.decode(parts['PROMISE'], 'records', 'PROMISE')['basisId']; members = {}; group = {}
        point = dict(cut=parent['cut'], catalog='d'*64, application='e'*64)
        older = dict(point, cut=dict(parent['cut'], index=4))
        for node in ('node-1','node-2','node-3'):
            value = j.f.decode(parts['PROMISE'], 'records', 'PROMISE')
            basis = j.f.encode('records','BASIS',dict(value,voter=node,cut=parent['cut'],capsule='a'*64,inventory='b'*64,accepted=None))
            members[node] = {'basis.gsr':basis,'selected.gsr':parts['SELECTED']}
            files = {'node.gsr':j.f.encode('records','NODE',dict(root=root,identity=identities[node])),
                'selector.gsr':j.f.encode('records','SELECTOR',dict(root=root,node=node,generation='b',digest='0'*64)),
                'pending.accept':j.disk.EMPTY,'grants.gsr':b'all original grants',j.PEERS:b'original ledger',
                'generations':None,'generations/a':None,'generations/a/original':b'old',
                'generations/b':None,'generations/b/current':b'current','sources':None,
                'sources/obsolete':None,'sources/obsolete/source.gscp':b'old source',
                'sources/'+active:None,'sources/'+active+'/source.gscp':b'active source'}
            files[j.future.FILE] = j.future.frame(j.future.initial(files),{})
            group[node] = files
        rows = [('PROMISE',b'old promise',{}),('PROMISE',parts['PROMISE'],dict(basisId=active)),
                ('BASIS',b'original basis',dict(basisId=active)),('SELECTED',parts['SELECTED'],{})]
        def current(files):
            node=j.f.decode(files['node.gsr'],'records','NODE')['identity']['node']
            return 'generations/b/',members[node],dict(capsule=point)
        return group,current,older,rows

    def project(self,group,current,older,rows):
        with patch.object(j.disk,'current',side_effect=current), \
             patch.object(j.observation,'observe_same_cut',side_effect=lambda raw,*args,**kwargs:raw), \
             patch.object(j,'require_coverage',return_value={4:older}), \
             patch.object(j.disk.p,'decode',return_value=dict(capsule=older)), \
             patch.object(j.disk,'journal',return_value=rows):
            return j.maintenance(group)

    def test_maintenance_keeps_current_source_and_offline_owner(self):
        group,current,older,rows=self.owners(); original=copy.deepcopy(group)
        result=self.project(group,current,older,rows)
        self.assertEqual(original,group)
        self.assertEqual(original['node-3'],result['node-3'])
        for node in j.VOTERS:
            self.assertNotIn('generations/a',result[node])
            self.assertNotIn('sources/obsolete',result[node])
            self.assertEqual(b'current',result[node]['generations/b/current'])
            self.assertIn(b'active source',result[node].values())
            self.assertEqual(b''.join(raw for _,raw,_ in rows[-3:]),result[node]['grants.gsr'])
            self.assertEqual(original[node][j.PEERS],result[node][j.PEERS])

    def test_unfinished_application_or_vote_forbids_retirement(self):
        for field,value in [('pending.accept',b'unfinished'),('applied-end',None),('applied-end/plan.json',b'original')]:
            group,current,older,rows=self.owners();group['node-1'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining transition maintenance requires completed publication$'):
                self.project(group,current,older,rows)

    def test_future_obligation_cannot_be_erased_by_maintenance(self):
        group,current,older,rows=self.owners()
        meta=j.future.initial(group['node-1']);meta.update(parent=older,peers=[dict(identity=meta['owner'],lower=older)])
        group['node-1'][j.future.FILE]=j.future.frame(meta,{})
        with self.assertRaisesRegex(ValueError,'^joining original empty future ledger$'):
            self.project(group,current,older,rows)

    def test_missing_coverage_cannot_authorize_source_removal(self):
        group,current,older,rows=self.owners()
        with patch.object(j.disk,'current',side_effect=current), \
             patch.object(j.observation,'observe_same_cut',side_effect=lambda raw,*args,**kwargs:raw), \
             patch.object(j,'require_coverage',return_value={}),patch.object(j.disk.p,'decode',return_value=dict(capsule=older)):
            with self.assertRaisesRegex(ValueError,'^joining transition source retirement coverage$'):
                j.maintenance(group)

    def test_grant_pruning_must_keep_the_actual_current_selection(self):
        group,current,older,rows=self.owners();rows[-1]=('SELECTED',b'different decision',{})
        with self.assertRaisesRegex(ValueError,'^joining transition retained grant suffix$'):
            self.project(group,current,older,rows)

    def test_unchanged_source_set_does_not_rewrite_grant_history(self):
        group,current,older,rows=self.owners()
        for files in group.values():
            for key in list(files):
                if key.startswith('sources/obsolete'):files.pop(key)
        result=self.project(group,current,older,rows)
        self.assertEqual(group['node-1']['grants.gsr'],result['node-1']['grants.gsr'])

    def test_applied_end_derives_each_required_statement_and_owned_ack(self):
        parts,parent,identities,root=fixture.JoiningCatalogEvidenceTest().phase()
        states=[dict(cut=dict(parent['cut'],index=i),application='c'*64,identities=list(identities.values())) for i in range(10)]
        replay=SimpleNamespace(root=root,states=states,phases=[{}]*8+[parts],entries=[],catalogs=[b'catalog']*10,image=b'image')
        def checkpoint(start,end,kind):
            return dict(root=root,scope=kind,start=states[start]['cut'],end=states[end]['cut'],
                catalogBefore='d'*64,catalogAfter='e'*64,applicationBefore='c'*64,applicationAfter='c'*64)
        replay.checkpoint=checkpoint;files={'selector.gsr':parts['SELECTOR']}
        with patch.object(j.s.capsules,'spans',return_value=[(0,9,'RANGE')]), \
             patch.object(j.publication,'required_points',return_value={4:{},6:{},8:{}}):
            end=j.applied_end(replay,files,9,'node-2')
        for label,start in [('ancestor-0',4),('ancestor-1',6),('parent',8)]:
            statement=end['applied-end/'+label+'-statement.gsr'];ack=j.f.decode(end['applied-end/'+label+'-ack.gsr'],'records','CHECKPOINT_ACK')
            self.assertEqual(checkpoint(start,9,'RANGE'),j.f.decode(statement,'records','CHECKPOINT'))
            self.assertEqual(identities['node-2']['storage'],ack['incarnation'])
            self.assertEqual(j.sha(statement),ack['statement'])
        plan=j.s.catalog.parse(end['applied-end/plan.json'])
        self.assertEqual('node-2',plan['node'])
        self.assertEqual(set(v['path'] for v in plan['files']),{k.removeprefix('applied-end/') for k in end if k.startswith('applied-end/') and k!='applied-end/plan.json'})

    def test_invalid_original_cannot_count_as_qualification(self):
        with patch.object(j,'validate',side_effect=ValueError('original failed')),patch.object(j.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original failed$'):j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_old_gate_must_still_accept_the_history_mutation(self):
        with patch.object(j,'validate',return_value={}) as checked,patch.object(j.shutil,'copytree'),patch.object(j,'mutate'), \
             patch.object(j.publication,'validate',side_effect=ValueError('earlier failure')):
            with self.assertRaisesRegex(ValueError,'^earlier failure$'):j.qualify(Path('/original'))
            self.assertEqual(1,checked.call_count)

    def test_wrong_negative_reason_is_not_evidence(self):
        with patch.object(j,'validate',side_effect=[{},ValueError('wrong failure')]),patch.object(j.shutil,'copytree'), \
             patch.object(j,'mutate'),patch.object(j.publication,'validate'):
            with self.assertRaisesRegex(ValueError,'^joining unrelated transition negative:'):j.qualify(Path('/original'))

    def test_each_negative_must_reject(self):
        with patch.object(j,'validate',return_value={}),patch.object(j.shutil,'copytree'),patch.object(j,'mutate'),patch.object(j.publication,'validate'):
            with self.assertRaisesRegex(ValueError,'^joining transition mutation accepted:'):j.qualify(Path('/original'))


if __name__=='__main__':unittest.main()
