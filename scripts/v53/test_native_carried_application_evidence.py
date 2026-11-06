import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_carried_application_evidence as m
from . import test_native_carried_transition_physical as fixture


class NativeCarriedApplicationEvidenceTest(unittest.TestCase):
    def originals(self):
        files,members,packet,entry,payload,selected=fixture.NativeCarriedTransitionPhysicalTest().command('FINAL')
        original=dict(selected,ballot=dict(selected['ballot'],counter=8))
        frames=dict(SELECTOR=b'old selector',ENTRY=entry,PAYLOAD=payload,ACCEPT=b'old accept',PROOF=b'old proof',
                    CERTIFICATE=b'old certificate',SELECTED=m.f.encode('records','SELECTED',original))
        files.update({'applied-end':None,'applied-end/selector.gsr':frames['SELECTOR'],
                      'applied-end/certificate.gsr':frames['CERTIFICATE'],'applied-end/ack.gsr':b'old ACK'})
        basis=fixture.sample('BASIS');members['basis.gsr']=m.f.encode('records','BASIS',basis)
        files['sources/'+basis['basisId']+'/source.gscp']=b'original source packet'
        source=dict(objects={m.e.digest(frames[k]):frames[k] for k in ('ENTRY','ACCEPT','PROOF','CERTIFICATE','PAYLOAD')})
        return files,members,packet,entry,payload,frames,source

    def test_old_cut_entrypoints_and_application_axis_remain_disjoint(self):
        with patch.object(m.p.process,'_validate',return_value={}) as validate:
            m.p.process.validate('/original');validate.assert_called_with('/original',('ACCEPT_RENAMED','PROOF_RENAMED'))
            m.p.process.validate_application('/original');validate.assert_called_with('/original',(m.CUT,))

    def test_current_selector_cold_open_preserves_ack_and_cannot_transfer_it(self):
        files,_,_,entry,payload,frames,_=self.originals()
        files['selector.gsr']=frames['SELECTOR'];before=copy.deepcopy(files)
        with patch.object(m.p.data,'pending',return_value=(frames,('PROOF','CERTIFICATE'))):
            self.assertEqual({'node-1':files},m.cold({'node-1':files},entry,payload))
            changed=dict(files,**{'selector.gsr':b'new selection'})
            with self.assertRaisesRegex(ValueError,'cold original end'):m.cold({'node-1':changed},entry,payload)
        self.assertEqual(before,files)

    def test_retirement_requires_original_certificate_in_new_frozen_source(self):
        files,members,packet,entry,payload,frames,source=self.originals();before=copy.deepcopy(files)
        with patch.object(m.p.data,'pending',return_value=(frames,('PROOF','CERTIFICATE'))),\
             patch.object(m.c,'current',return_value=(None,members,packet)),patch.object(m.e.p,'decode',return_value=source),\
             patch.object(m.e.p,'bind'):
            result=m.retire(files,entry,payload)
            self.assertNotIn('applied-end/ack.gsr',result)
            self.assertEqual({k:v for k,v in files.items() if not k.startswith('applied-end')},result)
            for key in ('ENTRY','ACCEPT','PROOF','CERTIFICATE','PAYLOAD'):
                changed=copy.deepcopy(source);changed['objects'].pop(m.e.digest(frames[key]))
                with patch.object(m.e.p,'decode',return_value=changed),self.assertRaisesRegex(ValueError,'original certified source'):
                    m.retire(files,entry,payload)
            for changed in (dict(files,**{'applied-end/certificate.gsr':b'new certificate'}),
                            dict(files,**{'selector.gsr':frames['SELECTOR']})):
                with self.assertRaisesRegex(ValueError,'exact retained retirement'):m.retire(changed,entry,payload)
        self.assertEqual(before,files)

    def test_staged_owner_cannot_borrow_floor_maintenance(self):
        group={'node-1':{'applied-end':None},'node-2':{}}
        with patch.object(m.p,'maintain',return_value=group) as maintain:
            self.assertEqual(group,m.maintain(group,tuple(group),campaign=True))
            maintain.assert_called_once_with(group,['node-2'],campaign=True)

    def test_bad_original_cannot_supply_negative_credit(self):
        with patch.object(m.p.process.collection,'inventory',return_value={}),\
             patch.object(m,'validate',side_effect=ValueError('bad original')),patch.object(m.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'bad original'):m.qualify('/original')
            copytree.assert_not_called()

    def test_original_change_during_physical_replay_is_rejected(self):
        with patch.object(m.p.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
             patch.object(m.p.process,'validate_application',return_value=dict(kind='FINAL')),patch.object(m,'physical',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_new_producer_declares_both_commands_and_both_real_death_modes(self):
        root=Path(__file__).resolve().parents[2]
        source=(root/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedApplicationProcessTest.java').read_text()
        self.assertEqual(4,source.count('@Test'))
        for kind in ('INTENT','FINAL'):
            for mode in ('halt','kill'):self.assertIn(f'run("{kind}","{mode}")',source)
        self.assertIn('APPLY_ACK_DIRECTORY_FORCED',source)


if __name__=='__main__':unittest.main()
