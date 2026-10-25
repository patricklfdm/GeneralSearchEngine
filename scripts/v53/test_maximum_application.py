"""Maximum native image boundary and original-first resource evidence checks."""
import unittest
from unittest.mock import patch
from . import maximum_application_evidence as q
from .test_source_packet import fixture, frame
from .carried_publication_evidence import generation


def installed_group():
    capsule,index,objects=fixture();packet=frame(capsule,q.e.f.canonical(index),objects)
    cap=q.e.f.decode(capsule,'records','CAPSULE')
    members={'source.gscp':packet,cap['application']+'.image':b'independent image',
             'promise.gsr':b'promise','basis.gsr':b'basis','selected.gsr':b'selected'}
    result={}
    for node in ('node-1','node-2','node-3'):
        selector,files=generation(members,cap,node,'b',None)
        result[node]=dict(files,**{'selector.gsr':selector,'generations/a':None,
                                 'generations/a/generation.gsr':b'inactive manifest'})
    return result


class MaximumApplicationTest(unittest.TestCase):
    def test_peak_copies_selected_manifest_and_members_from_original_bytes(self):
        group=installed_group();state,events=q.peak_plan(group)
        floor=q.e.f.decode(state['floor-copies/floor.gsr'],'records','FLOOR')
        for row in floor['sources']:
            original=group[row['voter']];manifest=original['generations/b/generation.gsr']
            self.assertEqual(q.e.digest(manifest),row['generation'])
            prefix='floor-copies/'+row['generation']+'/'
            self.assertEqual(manifest,state[prefix+'generation.gsr'])
            for name,data in original.items():
                if name.startswith('generations/b/'):
                    self.assertEqual(data,state[prefix+name.removeprefix('generations/b/')])
        self.assertEqual(3,len(floor['sources']))
        self.assertEqual('FLOOR_BEFORE_RETURN',events[-1])
        self.assertEqual(b'inactive manifest',state['generations/a/generation.gsr'])

    def test_peak_rejects_stale_selected_manifest_before_constructing_floor(self):
        group=installed_group();path='generations/b/generation.gsr'
        value=q.e.f.decode(group['node-2'][path],'records','GENERATION');value['node']='node-1'
        group['node-2'][path]=q.e.f.encode('records','GENERATION',value)
        with patch.object(q.floor,'transaction') as transaction:
            with self.assertRaisesRegex(ValueError,'round original generation inventory'):q.peak_plan(group)
            transaction.assert_not_called()

    def test_original_failure_never_becomes_successful_negative(self):
        with patch.object(q,'validate',side_effect=ValueError('original failed')),patch.object(q.Path,'read_bytes') as read:
            with self.assertRaisesRegex(ValueError,'original failed'):q.qualify('absent')
            read.assert_not_called()

    def test_native_limit_preserves_original_request_id_budget(self):
        self.assertEqual(32,q.MAXIMUM-q.NATIVE_MAXIMUM)
        self.assertEqual(64*1024*1024,q.MAXIMUM)

    def test_generated_fixture_exact_document_bounds_and_order(self):
        docs=q.documents(19000)
        self.assertEqual(list(range(1024)),[n for n,_ in docs])
        self.assertTrue(all(len((str(n)+':'+v).encode())==65536 for n,v in docs[:-1]))
        self.assertEqual((1023,'y'*19000),docs[-1])
        for bad in (-1,65532,True,1.0):
            with self.assertRaisesRegex(ValueError,'maximum document extent'):q.documents(bad)

    def test_peak_reserves_seven_physical_images_even_for_one_hash(self):
        # References reuse Python memory; physical file identities still count seven times.
        image=b'\0'*q.NATIVE_MAXIMUM
        files={f'{n}/same.image':image for n in range(7)}
        files.update({'sources/first/source.gscp':b'x'*10,'sources/second/source.gscp':b'y'*20,
                      'floor-copies/one/generation.gsr':b'z'*30,'floor-copies/proposal.gsr':b'a'*100,
                      'generations/a/generation.gsr':b'g'*40})
        images,metadata,staging,leases=q.peak_usage(files)
        self.assertEqual(7,len(images));self.assertEqual(7*q.NATIVE_MAXIMUM+60,staging)
        self.assertEqual(34*q.e.MIB+100,metadata);self.assertEqual(16,leases)
        for mutated in ({k:v for k,v in files.items() if k!='0/same.image'},dict(files,**{'extra.image':image})):
            with self.assertRaisesRegex(ValueError,'maximum seven complete images'):q.peak_usage(mutated)

    def test_receipt_cannot_promote_native_maximum_to_container_or_runtime(self):
        original=dict(schema='gse-v53-maximum-application-v1',status='PASS',imageBytes=q.NATIVE_MAXIMUM,
                      administrationBytes=32,finalValueBytes=12,documents=1024,voters=5,slots=2,peakImages=7,publicRuntime=False)
        q.receipt(original,12)
        for field,value in [('imageBytes',q.MAXIMUM),('publicRuntime',True),('peakImages',6),('documents',1023),('slots',1)]:
            with self.assertRaisesRegex(ValueError,'maximum receipt'):q.receipt(dict(original,**{field:value}),12)


if __name__=='__main__':unittest.main()
