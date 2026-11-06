"""Conditional reader guards; these fixtures are not native acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_application_refusal as m
from . import test_native_application_overlap as fixture


def case():
    files,state,ordinals=fixture.fixture();packet=b'packet'
    path=next(k for k in sorted(files) if k.startswith('sources/') and k.endswith('/source.gscp'))
    files[path]=dict(bytes=len(packet),sha256=m.h.digest(packet))
    changes=[];current={}
    def change(event,removed=(),added=()):
        for v in removed:del current[m.t.key(v)]
        for v in added:current[m.t.key(v)]=v
        changes.append(dict(sequence=len(changes),event=event,removed=list(removed),added=list(added),usage=m.t.usage(current,fixture.LIMITS)))
    change('START')
    for v in sorted(state.values(),key=m.t.order_key):change('RESERVE',added=[v])
    first=len(changes)-1
    control=fixture.charge('CONTROL','received-records-11111111-2222-3333-4444-555555555555',4096)
    change('RESERVE',added=[control]);change('RELEASE',removed=[control]);last=len(changes)-1
    for v in sorted(state.values(),key=m.t.order_key):change('RELEASE',removed=[v])
    trace=dict(schema='gse-v53-resource-transitions-v1',metadataLimit=fixture.LIMITS[0],stagingLimit=fixture.LIMITS[1],queueLimit=fixture.LIMITS[2],
        changes=changes,transitions=len(changes),current=changes[-1]['usage'],truncated=False,failed=False)
    m.t.replay(trace)
    row=dict(life=2,node='node-1',eventIndex=0,point=m.POINT,files=files,ordinals=ordinals)
    boundary=dict(eventIndex=0,node='node-1',sequence=first,usage=m.t.usage(state,fixture.LIMITS))
    record=dict(schema=m.SCHEMA,status='PARTIAL',life=2,node='node-1',eventIndex=0,point=m.POINT,callbackSequence=first,
        beforeSequence=first,afterSequence=last,beforeUsage=copy.deepcopy(boundary['usage']),afterUsage=copy.deepcopy(boundary['usage']),
        authorityFiles=[dict(path=k,sha256=v['sha256']) for k,v in sorted(files.items()) if 'bytes' in v],sourcePath=path,packetFile='node-1.gscp',packetSha256=m.h.digest(packet),
        rejection='resource ownership/count',scratchRemoved=True,originalPool=True,wireAdmissionQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
    return record,row,trace,boundary,last,packet


class NativeApplicationRefusalTest(unittest.TestCase):
    def test_complete_original_checkpoints_prove_temporary_control_return(self):
        value=m.check_record(*case())
        self.assertEqual({'GENERATION':2,'SOURCE':6,'APPLICATION':7},value['nonemptyPhysicalOwnerCounts'])
        self.assertEqual(value['beforeSequence']+2,value['afterSequence'])
        self.assertTrue(value['temporaryControlReturned']);self.assertTrue(value['originalChargesPreserved'])

    def test_all_probe_record_negatives_have_exact_reasons(self):
        for name,reason in m.NEGATIVES.items():
            args=case();m.mutate(args[0],name)
            with self.subTest(name=name),self.assertRaises(ValueError) as caught:m.check_record(*args)
            self.assertEqual(reason,str(caught.exception))

    def test_released_foreign_charge_does_not_prove_temporary_control_cleanup(self):
        args=case();record,row,trace,boundary,next_sequence,packet=args
        # A valid release of a different live CONTROL owner leaves the new one
        # outstanding. Totals alone would hide this substitution.
        last=record['afterSequence']
        waiting=next(v for c in trace['changes'][:last-1] for v in c['added'] if v['unit']=='CONTROL')
        trace['changes'][last]['removed']=[waiting]
        record['afterUsage']=m.t.usage(m.state_at(trace,last),fixture.LIMITS)
        with self.assertRaisesRegex(ValueError,'original charges preserved'):m.check_record(*args)

    def test_an_unrelated_zero_net_allocation_is_not_source_receiver_rejection(self):
        for key,value in (('owner','unrelated'),('bytes',1)):
            args=case();record,row,trace,*_=args
            for change in trace['changes'][record['beforeSequence']+1:record['afterSequence']+1]:
                for v in change['added']+change['removed']:v[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'temporary control only'):m.check_record(*args)

    def test_charge_count_without_nonempty_file_is_insufficient(self):
        args=case();record,row,*_=args
        row['files']['retirement/images.json']=fixture.file(0)
        next(v for v in record['authorityFiles'] if v['path']=='retirement/images.json')['sha256']=row['files']['retirement/images.json']['sha256']
        with self.assertRaisesRegex(ValueError,'simultaneous nonempty owners'):m.check_record(*args)

    def test_original_packet_contents_and_size_are_checked(self):
        args=case()
        for packet in (b'changed',b'packeT'):
            with self.subTest(packet=packet),self.assertRaisesRegex(ValueError,'original source packet'):
                m.check_record(*args[:-1],packet)

    def test_no_checkpoint_from_outside_this_callback_interval(self):
        args=case();record=args[0]
        with self.assertRaisesRegex(ValueError,'exact checkpoints'):m.check_record(*args[:4],record['afterSequence']-1,args[-1])
        record['beforeSequence']=True
        with self.assertRaisesRegex(ValueError,'exact checkpoints'):m.check_record(*args)

    def test_process_index_matches_exact_owner_lifetime(self):
        for life,terminal in ((1,'CUT_PREFIX'),(2,'CLOSED')):
            index=dict(schema='gse-v53-native-count-refusals-v1',life=life,pid=123,terminal=terminal,nodes=['node-1'],phase3Complete=False)
            self.assertEqual(['node-1'],m.index_nodes(index,dict(pid=123,terminal=terminal),life))

    def test_foreign_process_early_close_and_missing_or_duplicate_owners_reject(self):
        original=dict(schema='gse-v53-native-count-refusals-v1',life=1,pid=123,terminal='CUT_PREFIX',nodes=['node-1'],phase3Complete=False)
        for key,value in (('pid',124),('pid',True),('life',True),('terminal','CLOSED'),('phase3Complete',True),
                          ('nodes',[]),('nodes',['node-1','node-1']),('nodes',['node-9'])):
            index=dict(original);index[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                m.index_nodes(index,dict(pid=123,terminal='CUT_PREFIX'),1)

    def test_invalid_original_prevents_probe_and_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'original').mkdir();(root/'refusals').mkdir()
            with patch.object(m.admission.transients,'validate',side_effect=ValueError('failed original')),patch.object(m,'contexts') as later:
                with self.assertRaisesRegex(ValueError,'failed original'):m.qualify(root,'final-application-kill')
            later.assert_not_called()


if __name__=='__main__':unittest.main()
