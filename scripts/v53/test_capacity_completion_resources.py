"""Synthetic accounting boundary tests; no physical acceptance from mocks."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from . import capacity_completion_resources as m
from . import capacity_completion_run as admission
from .test_capacity_completion_run import replay,resource_summary


class CapacityCompletionResourcesTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)/'raw';self.root.mkdir()
        self.directory=self.root/m.DIRECTORY;self.directory.mkdir();self.calls=[]
        charges=[dict(unit=unit,owner=owner,bytes=size,claimSource='') for unit,owner,size in
                 [('JOURNAL','journal',32*m.r.MIB),('MISC','current-authority',2*m.r.MIB),('GENERATION','a',100)]]
        changes=[dict(sequence=0,event='START',removed=[],added=[],usage=m.r.EMPTY)];state={}
        for charge in charges:
            state[m.r.key(charge)]=charge
            changes.append(dict(sequence=len(changes),event='RESERVE',removed=[],added=[charge],usage=m.r.usage(state,(384*m.r.MIB,512*m.r.MIB,64*m.r.MIB))))
        for charge in charges[::-1]:
            state.pop(m.r.key(charge));changes.append(dict(sequence=len(changes),event='RELEASE',removed=[charge],added=[],usage=m.r.usage(state,(384*m.r.MIB,512*m.r.MIB,64*m.r.MIB))))
        trace=dict(schema='gse-v53-resource-transitions-v1',metadataLimit=384*m.r.MIB,stagingLimit=512*m.r.MIB,queueLimit=64*m.r.MIB,
                   transitions=len(changes),truncated=False,failed=False,changes=changes,current=m.r.EMPTY)
        owners=[];events=[];points=[]
        for i,(node,operation) in enumerate(m.schedule('replay-smoke-1')):
            scope=f'open-{i:04d}';name=scope+'.json';sha=self.write(self.directory/name,trace)
            owners.append(dict(scope=scope,node=node,operation=operation,path=name,sha256=sha))
            for event,sequence in [('OWNER_OPEN_BEGIN',0),('OWNER_OPEN_RETURNED',3),('WRITER_CALLBACK',3)]:
                points.append(dict(eventIndex=len(events),sequence=sequence,usage=changes[sequence]['usage']))
                events.append(dict(node=node,event=event,scope=scope))
            if operation:self.calls.append(dict(operation=operation,node=node,events=['WRITER_CALLBACK']))
        self.write(self.directory/'index.json',dict(schema='gse-v53-completion-resources-v1',root='a'*64,owners=owners,
            eventsSha256=self.write(self.directory/'events.json',events),boundariesSha256=self.write(self.directory/'boundaries.json',points)))
        for target,value in [('p.collect',[[dict(eventIndex=0,usageBefore=m.r.EMPTY,usageAfter=m.r.EMPTY)]*11 for _ in range(15)]),('c.inventory',{}),
                             ('p.compare',dict(maximumObservedStorage=dict(metadata=34*m.r.MIB,staging=0,applications=0,sources=0)))]:
            owner,method=target.split('.');mock=patch.object(getattr(m,owner),method,return_value=value);mock.start();self.addCleanup(mock.stop)

    @staticmethod
    def write(path,value):
        raw=m.p.f.canonical(value);path.write_bytes(raw);return m.p.sha(raw)

    def validate(self,path=None):return m.validate(path or self.root,'replay-smoke-1','a'*64,self.calls)

    def test_full_and_smoke_have_exact_opens_and_cannot_substitute(self):
        value=self.validate();m.check_summary(value,'replay-smoke-1')
        self.assertEqual(157,value['ownerLifetimes']);self.assertEqual(93,len(self.calls));self.assertEqual(165,value['publicationBoundaries'])
        self.assertFalse(value['wholeRuntimeResourcesQualified']);self.assertFalse(value['closeIntervalsQualified'])
        self.assertEqual(163,len(m.schedule('capacity-231')))
        with self.assertRaisesRegex(ValueError,'original owner schedule'):m.validate(self.root,'capacity-231','a'*64,self.calls)
        with self.assertRaisesRegex(ValueError,'explicit profile'):m.schedule('auto')

    def test_six_coherent_accounting_mutations_fail_for_their_own_reasons(self):
        self.validate()
        for name,reason in list(m.VARIANTS.items())[:6]:
            root=self.root.parent/name;shutil.copytree(self.root,root);m.mutate(root,name)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,reason):self.validate(root)

    def test_call_omission_unobserved_files_and_failed_observation_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'call correspondence'):m.validate(self.root,'replay-smoke-1','a'*64,self.calls[1:])
        (self.directory/'extra.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'exact inventory'):self.validate()
        (self.directory/'extra.json').unlink()
        index=m.read(self.directory,'index.json',m.r.MIB);owner=index['owners'][0];_,value=m.r.read(self.directory/owner['path'])
        value['truncated']=True;owner['sha256']=self.write(self.directory/owner['path'],value);self.write(self.directory/'index.json',index)
        with self.assertRaisesRegex(ValueError,'incomplete observation'):self.validate()

    def test_summary_and_admission_refuse_missing_resource_negatives_and_invented_scope(self):
        admission.check_result(replay('replay-smoke-1'),'replay-smoke-1')
        for change in [lambda v:v.pop('resources'),lambda v:v['resourceNegatives'].pop(),lambda v:v['resourceNegatives'][0].update(reason='unrelated'),
                       lambda v:v['resources'].update(wholeRuntimeResourcesQualified=True),lambda v:v['resources'].update(ownerLifetimes=163),
                       lambda v:v['resources']['maximumObservedCounts'].update(APPLICATION=8)]:
            value=replay('replay-smoke-1');change(value)
            with self.assertRaises(ValueError):admission.check_result(value,'replay-smoke-1')
        for field,value in [('ownerLifetimes',True),('mutations',0),('publicationBoundaries',164),('closeIntervalsQualified',True)]:
            summary=resource_summary('replay-smoke-1');summary[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'scope'):m.check_summary(summary,'replay-smoke-1')
