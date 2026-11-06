"""Projection regressions; full physical replay remains the caller prerequisite."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import slot_control_resources as r


def fixture():
    f=r.publication.f;schema=f.catalog();phases=[];images={};identities={}
    for index in (1,2):
        selected=f.sample(schema['records']['SELECTED']['schema'],schema['types'])
        certificate=f.sample(schema['records']['CERTIFICATE']['schema'],schema['types'])
        selected['ballot']['counter']=index;selected['view']=f'{index:064x}'
        certificate.update(index=index,ballot=copy.deepcopy(selected['ballot']),authority=selected['view'],entry=f'{index+10:064x}')
        phases.append({k:f.encode('records',k,v) for k,v in [('SELECTED',selected),('CERTIFICATE',certificate)]})
        for proof in certificate['proofs']:
            node=proof['voter'];identities[node]=dict(node=node,storage=proof['incarnation'],host='127.0.0.1',port=10000+int(node[-1]))
            images[index,node]={'generations/current/generation.gsr':f'{index}/{node}'.encode(),
                'capsule':dict(cut=dict(index=index,entry=certificate['entry'],view=dict(generation=index)),catalog=f'{index+20:064x}',application=f'{index+30:064x}')}
    def owner(phase,index,node):
        if phase!='published':raise AssertionError(phase)
        return images[index,node]
    model=SimpleNamespace(root=selected['root'],phases=phases,entries=[{},{}],owner=owner)
    return model,identities,images


class MembershipControlPublicationsTest(unittest.TestCase):
    def replay(self,model,identities):
        with patch.object(r.publication.disk,'current',side_effect=lambda files:('generations/current/',{},dict(capsule=files['capsule']))):
            return r.required_four_publications(model,identities)

    def test_every_slot_uses_original_selection_anchor_and_per_voter_generation(self):
        model,ids,images=fixture();before=copy.deepcopy((model.phases,ids,images));values=self.replay(model,ids)
        self.assertEqual(4,len(values))
        for index,parts in enumerate(model.phases,1):
            for node in ids:
                value=values[node,r.publication.sha(parts['CERTIFICATE'])]
                self.assertEqual(index,value['ballot']['counter']);self.assertEqual(f'{index:064x}',value['view'])
                self.assertEqual(r.publication.sha(parts['SELECTED']),value['payload']['selection'])
                self.assertEqual(images[index,node]['capsule'],value['payload']['published'])
                self.assertEqual(r.publication.sha(images[index,node]['generations/current/generation.gsr']),value['payload']['generation'])
                self.assertEqual(ids[node],value['identity'])
        self.assertEqual(before,(model.phases,ids,images))

    def test_final_selection_cannot_replace_earlier_original_authority(self):
        for field in ('view','ballot','root'):
            model,ids,_=fixture();f=r.publication.f
            value=f.decode(model.phases[0]['SELECTED'],'records','SELECTED')
            value[field]=f.decode(model.phases[1]['SELECTED'],'records','SELECTED')[field] if field!='root' else 'f'*64
            model.phases[0]['SELECTED']=f.encode('records','SELECTED',value)
            with self.subTest(field=field),self.assertRaises(ValueError):self.replay(model,ids)

    def test_missing_phase_or_wrong_published_image_cannot_bind(self):
        for mutation in ('empty','missing','index','entry','identity','voter'):
            model,ids,images=fixture()
            if mutation=='empty':model.phases=[]
            elif mutation=='missing':model.entries.pop()
            elif mutation in ('index','entry'):images[1,'node-2']['capsule']['cut'][mutation]=99 if mutation=='index' else 'f'*64
            elif mutation=='identity':ids['node-2']['storage']='00000000-0000-0000-0000-000000000099'
            else:ids.pop('node-2')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.replay(model,ids)

    def test_missing_generation_fails_instead_of_using_another_voter(self):
        model,ids,images=fixture();del images[1,'node-2']['generations/current/generation.gsr']
        with self.assertRaises(KeyError):self.replay(model,ids)


if __name__=='__main__':unittest.main()
