"""Independent confirmation syntax/bounds; no manufactured receipt authority."""
import base64
import copy
import unittest
from . import learner_retention_evidence as e


def fixture():
    node=lambda n:str(n)+'a'*63
    host='.'.join(['a'*63]*3+['a'*61])
    identity=lambda n:dict(node=node(n),storage=f'ffffffff-ffff-ffff-ffff-{n:012x}',host=host,port=65535)
    view=dict(generation=256,old=[node(n) for n in range(1,6)],new=[node(n) for n in range(1,6)],operation=None)
    root='f'*64;expected=e.sha(e.f.canonical(dict(view,root=root)))
    request=dict(root=root,number=2**63-2,expected=expected,kind='REPLACE',target=[identity(n) for n in [1,2,3,4,6]])
    point=lambda i:dict(cut=dict(index=i,entry='f'*64,view=view),catalog='f'*64,application='f'*64)
    q=dict(root=root,view=expected,sender=identity(5),recipient=identity(6),
           ballot=dict(counter=1,proposer=node(6),incarnation=identity(6)['storage']),
           trace='ffffffff-ffff-ffff-ffff-ffffffffffff',sequence=1,payload=dict(request=request))
    a=dict(q,sender=identity(6),recipient=identity(5),payload=dict(request=e.sha(e.f.canonical(request)),endpoint=point(2**63-3)))
    encoded=dict(query=base64.b64encode(e.f.encode('wire','LEARNER_HEAD_QUERY',q)).decode(),
                 ack=base64.b64encode(e.f.encode('wire','LEARNER_HEAD_ACK',a)).decode())
    plan=dict(root=root,request=request,learner=identity(6),possible=[point(2**63-3),point(2**63-2)],confirmation=encoded)
    return dict(root=root,owner=identity(5),revision=1,previous='e'*64,plan=plan)


class LearnerConfirmationEvidenceTest(unittest.TestCase):
    def test_longest_identity_fields_and_two_points_fit_existing_limits(self):
        value=fixture();point=value['plan']['possible'][0]
        value['plan']['renewals']=[dict(point,cut=dict(point['cut'],index=2**63-i)) for i in (5,4)]
        raw=e.frame(value);self.assertEqual(value,e.decode(raw))
        self.assertLessEqual(len(e.f.canonical(value['plan']['confirmation'])),8192)
        self.assertLessEqual(len(e.f.canonical(value['plan'])),16384)
        self.assertLessEqual(len(raw),32768)

    def test_pending_renewals_are_bounded_older_distinct_endpoints(self):
        for case in ('empty','duplicate','future','too-many','extra-field'):
            value=fixture();point=copy.deepcopy(value['plan']['possible'][0]);point['cut']['index']-=1
            rows=[point]
            if case=='empty':rows=[]
            if case=='duplicate':rows=[point,point]
            if case=='future':rows=value['plan']['possible']
            if case=='too-many':rows=[point]*3
            if case=='extra-field':point['trusted']=True
            value['plan']['renewals']=rows
            with self.subTest(case=case),self.assertRaises(ValueError):e.frame(value)

    def test_recomputed_frames_cannot_hide_original_binding_drift(self):
        for field in ['trace','view','sender','request','endpoint','unknown']:
            value=fixture();proof=value['plan']['confirmation'];a=e.f.decode(base64.b64decode(proof['ack']),'wire','LEARNER_HEAD_ACK')
            if field=='trace':a['trace']='ffffffff-ffff-ffff-ffff-fffffffffff0'
            elif field=='view':a['view']='a'*64
            elif field=='sender':a['sender']['storage']='ffffffff-ffff-ffff-ffff-fffffffffff0'
            elif field=='request':a['payload']['request']='a'*64
            elif field=='endpoint':a['payload']['endpoint']['catalog']='a'*64
            elif field=='unknown':proof['trusted']=True
            proof['ack']=base64.b64encode(e.f.encode('wire','LEARNER_HEAD_ACK',a)).decode()
            with self.subTest(field=field),self.assertRaises(ValueError):e.frame(value)

    def test_bare_decoded_merge_cannot_claim_selected_provenance(self):
        value=fixture();before=e.frame(value);old=copy.deepcopy(value);old['plan'].pop('confirmation')
        old['plan']['possible']=old['plan']['possible'][:1]
        with self.assertRaisesRegex(ValueError,'selected provenance replay'):e.merged(before,[e.frame(old)])


if __name__=='__main__':unittest.main()
