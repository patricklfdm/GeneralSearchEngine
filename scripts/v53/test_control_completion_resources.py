"""One-slot membership replay cannot weaken DATA or original owner binding."""
import base64
import copy
import struct
import unittest
from . import publication_resource_evidence as p
from . import publication_generation_resources as g
from . import replay_resource_binding as r
from . import test_publication_generation_resources as publication_fixture
from . import test_replay_resource_binding as replay_fixture


def certified(files,kind):
    catalog=p.f.catalog()
    def record(name,**changes):
        value=p.f.sample(catalog['records'][name]['schema'],catalog['types']);value.update(changes)
        return p.f.encode('records',name,value)
    payload=b'original';entry=record('ENTRY',kind=kind,payload=p.sha(payload))
    certificate=record('CERTIFICATE',entry=p.sha(entry))
    body=b''.join([files['selector.gsr'],record('PROMISE'),record('SELECTED'),entry,record('ACCEPT'),
        struct.pack('>I',len(payload)),payload,record('PROOF'),certificate])
    files['pending.accept']=struct.pack('>4sHHI',b'GSPV',1,3,len(body)+12)+body
    files['applied-end/certificate.gsr']=certificate
    return entry


class ControlCompletionResourcesTest(unittest.TestCase):
    def publication(self,kind):
        test=publication_fixture.PublicationGenerationResourcesTest();test.setUp();self.addCleanup(test.doCleanups)
        certified(test.fixture.before,kind)
        retained=[i for i,row in enumerate(test.changes) if not any(g.t.key(v)==g.TEMPORARIES[-1] for v in row['added']+row['removed'])]
        test.changes=[row for i,row in enumerate(test.changes) if i in retained]
        test.positions=[sum(i<=pos for i in retained)-1 for pos in test.positions]
        for row,(point,files,charges) in zip(test.rows,p.derived(test.fixture.before,test.fixture.after,output=False)):
            row.update(files=files,storage=charges)
        return test

    def test_original_membership_bytes_admit_one_input_publication_and_custody(self):
        for kind in ('INTENT','FINAL'):
            with self.subTest(kind=kind):
                test=self.publication(kind);self.assertEqual('PASS',test.check()['status'])
                self.assertEqual(11,p.compare([test.rows],test.fixture.plans)['observedBoundaries'])
                test.rename(g.TEMPORARIES[1],('APPLICATION','unrelated-input'))
                with self.assertRaisesRegex(ValueError,'exact owner extents'):test.check()

    def test_data_barrier_or_changed_original_certificate_cannot_use_reduced_publication(self):
        for kind in ('DATA','BARRIER','INTENT'):
            test=self.publication('INTENT');certified(test.fixture.before,kind)
            if kind=='INTENT':test.fixture.before['applied-end/certificate.gsr']=b'substituted'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                p.output_reserved(test.fixture.before,test.fixture.after,test.rows[0]['storage'])

    def replay(self):
        trace,events,bounds=replay_fixture.ReplayResourceBindingTest().fixture()
        retained=[];positions={}
        for row in trace['changes']:
            if not any(v['owner']==r.OWNERS[1] for v in row['removed']+row['added']):retained.append(row)
            positions[row['sequence']]=len(retained)-1
        trace['changes']=retained;trace['transitions']=len(retained)
        state={};limits=(384*r.r.MIB,512*r.r.MIB,64*r.r.MIB)
        for seq,row in enumerate(trace['changes']):
            row['sequence']=seq
            for old in row['removed']:del state[r.r.key(old)]
            for new in row['added']:state[r.r.key(new)]=new
            row['usage']=r.r.usage(state,limits)
        trace['current']=trace['changes'][-1]['usage']
        for point in bounds:
            point['sequence']=positions[point['sequence']];point['usage']=trace['changes'][point['sequence']]['usage']
        return trace,events,bounds

    def test_single_replay_input_requires_original_membership_scope(self):
        values=self.replay()
        with self.assertRaises(ValueError):r.bind(*values,'node-1',closed=True)
        result=r.bind(*values,'node-1',closed=True,membership_starts={0})
        self.assertEqual([64*r.r.MIB],result['reservationBytesPerTransaction'])
        for starts in ({True},{1},{-1},{99}):
            with self.assertRaises(ValueError):r.bind(*values,'node-1',closed=True,membership_starts=starts)

    def test_membership_scope_does_not_allow_a_gap_or_partial_input(self):
        for variant in ('extent','owner','gap'):
            values=self.replay();trace=values[0]
            # A balanced complete accounting fixture still cannot omit its
            # actual replay input between callbacks.
            if variant=='gap':
                values=replay_fixture.ReplayResourceBindingTest().fixture(interruption=True)
            else:
                for row in trace['changes']:
                    for item in row['added']+row['removed']:
                        if variant=='extent':item['bytes']=1
                        else:item['owner']='unrelated'
            with self.subTest(variant=variant),self.assertRaises(ValueError):
                r.bind(*values,'node-1',closed=True,membership_starts={0})

    def test_original_round_bytes_control_exact_replay_intervals(self):
        files={'selector.gsr':b'placeholder'};events=[];wanted=set()
        for kind in ('INTENT','DATA','FINAL','BARRIER'):
            raw=certified(files,kind)
            events.append(dict(event='ROUND_SLOT_BEGIN',node='node-1',bytes=base64.b64encode(raw).decode(),record=p.sha(raw)))
            if kind in ('INTENT','FINAL'):wanted.add(len(events))
            events.extend([dict(event='REPLAY_RESERVED',node='node-2'),dict(event='ROUND_SLOT_COMPLETE',node='node-1'),
                           dict(event='REPLAY_RESERVED',node='node-1')])
        self.assertEqual(wanted,r.native_membership_starts(events))
        changed=copy.deepcopy(events);changed[0]['record']='0'*64
        with self.assertRaisesRegex(ValueError,'original round command'):r.native_membership_starts(changed)


if __name__=='__main__':unittest.main()
