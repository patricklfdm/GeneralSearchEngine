import unittest
from unittest.mock import patch
from . import native_replay_files as m


class NativeReplayFilesTest(unittest.TestCase):
    def project(self,kind='FINAL',initial=None,applied=None):
        self.initial={'node.gsr':b'node','selector.gsr':b'selector','pending.accept':b'vote','other':b'keep'} if initial is None else initial
        self.applied=dict(self.initial,**({'applied-end/application.image':b'image'} if applied is None else applied))
        frames={'SELECTOR':b'selector','ENTRY':b'entry','CERTIFICATE':b'certificate'}
        decoded={'NODE':{'identity':dict(node='node-1',storage='storage')},'SELECTOR':dict(node='node-1',root='root'),
                 'CERTIFICATE':dict(root='root'),'ENTRY':dict(kind=kind)}
        with patch.object(m.p.data,'pending',return_value=(frames,None)),patch.object(m.f,'decode',side_effect=lambda raw,family,tag:decoded[tag]),\
             patch.object(m.p.c,'current',return_value=('',{'hash.image':b'image'},{'capsule':{'application':'hash'}})),\
             patch.object(m,'image_members',return_value={'gse-backup-'+n:n.encode() for n in ('checkpoint','manifest','metadata')}):
            return m.transaction(self.initial,self.applied)

    def test_exact_claim_prefix_and_input_appears_only_after_typed_replay(self):
        steps=self.project();states={point:state for _,point,state in steps};prefix=m.DIRECTORY
        claim=m.f.canonical(dict(schema='gse-v53-application-replay/1.3',root='root',node='node-1',storage='storage',
                               selector=m.p.e.digest(b'selector'),certificate=m.p.e.digest(b'certificate')))
        for point,raw in [('CREATED',b''),('PREFIX_WRITTEN',claim[:len(claim)//2]),('WRITTEN',claim),('FORCED',claim)]:
            self.assertEqual(m.physical({'x':raw})['x'],states['REPLAY_CLAIM_'+point][prefix+'/claim.json'])
        self.assertNotIn(prefix+'/work',states['REPLAY_BEFORE_APPLICATION'])
        self.assertEqual(3,len([k for k in states['REPLAY_APPLICATION_FINISHED'] if k.startswith(prefix+'/work/input/')]))
        self.assertNotIn(prefix+'/work/output',states['REPLAY_APPLICATION_FINISHED'])
        self.assertEqual(m.physical(self.initial),states['REPLAY_BEFORE_RETURN']);self.assertEqual(23,len(steps))

    def test_exact_children_first_deletion_claim_last_then_root(self):
        steps=self.project();pairs=[(steps[i][2],steps[i+1][2]) for i,(_,point,_) in enumerate(steps) if point=='REPLAY_BEFORE_DELETE']
        removed=[next(iter(before.keys()-after.keys())) for before,after in pairs]
        self.assertEqual([m.DIRECTORY+'/'+p for p in ('work/input/gse-backup-checkpoint','work/input/gse-backup-manifest',
            'work/input/gse-backup-metadata','work/input','work','claim.json','')][:-1]+[m.DIRECTORY],removed)
        for _,_,state in steps:
            for name,identity in m.physical(self.initial).items():self.assertEqual(identity,state[name])

    def test_all_three_control_kinds_same_files_but_data_is_not_relabelled(self):
        for kind in ('INTENT','FINAL','BARRIER'):self.assertEqual(23,len(self.project(kind)))
        with self.assertRaisesRegex(ValueError,'^replay prefix control record only$'):self.project('DATA')

    def test_unrelated_application_snapshot_change_rejects(self):
        with self.assertRaisesRegex(ValueError,'^replay prefix outside application end$'):
            self.project(applied={'applied-end/application.image':b'image','other':b'changed'})

    def test_existing_scratch_and_changed_control_image_reject(self):
        for name in (m.DIRECTORY,m.DIRECTORY+'/claim.json'):
            with self.assertRaisesRegex(ValueError,'^replay prefix fresh scratch$'):self.project(initial={name:b'old'})
        with self.assertRaisesRegex(ValueError,'^replay prefix unchanged control image$'):
            self.project(applied={'applied-end/application.image':b'changed'})

    def retained(self,change=None):
        from . import native_carried_application_evidence as application
        from .test_native_carried_transition_physical import sample
        manifest=sample('GENERATION');manifest.update(node='node-1',generation='a')
        raw=m.f.encode('records','GENERATION',manifest)
        selector=m.f.encode('records','SELECTOR',dict(root=manifest['root'],node='node-1',generation='a',digest=m.p.e.digest(raw)))
        node=sample('NODE');node.update(root=manifest['root']);node['identity']['node']='node-1'
        certificate=sample('CERTIFICATE');certificate['root']=manifest['root']
        entry=sample('ENTRY');entry['kind']='FINAL'
        frames=dict(SELECTOR=selector,ENTRY=m.f.encode('records','ENTRY',entry),PAYLOAD=b'payload',
                    CERTIFICATE=m.f.encode('records','CERTIFICATE',certificate))
        initial={'selector.gsr':b'new selector retained','node.gsr':m.f.encode('records','NODE',node),
                 'generations/a/generation.gsr':raw,'generations/a/'+manifest['application']+'.image':b'old image',
                 'applied-end/application.image':b'old image','applied-end/ack.gsr':b'old ACK'}
        if change=='manifest':initial['generations/a/generation.gsr']=m.f.encode('records','GENERATION',dict(manifest,node='node-2'))
        elif change=='image':initial['applied-end/application.image']=b'changed'
        elif change=='data':frames['ENTRY']=m.f.encode('records','ENTRY',dict(entry,kind='DATA'))
        before=dict(initial)
        with patch.object(m.p.data,'pending',return_value=(frames,('PROOF','CERTIFICATE'))),patch.object(application,'retire') as admit,\
             patch.object(m,'image_members',return_value={'gse-backup-manifest':b'input'}):
            steps=m.retirement(initial)
            admit.assert_called_once_with(initial,frames['ENTRY'],frames['PAYLOAD'])
        self.assertEqual(before,initial)
        return initial,frames,steps

    def test_retirement_replays_old_input_without_replacing_new_selector(self):
        initial,frames,steps=self.retained()
        expected=m.physical(initial)
        for _,_,state in steps:
            self.assertTrue(all(state[k]==v for k,v in expected.items()))
        self.assertEqual(expected,steps[-1][2])
        claim=m.f.canonical(dict(schema='gse-v53-application-replay/1.3',root=m.f.decode(frames['SELECTOR'],'records','SELECTOR')['root'],
            node='node-1',storage=m.f.decode(initial['node.gsr'],'records','NODE')['identity']['storage'],
            selector=m.p.e.digest(frames['SELECTOR']),certificate=m.p.e.digest(frames['CERTIFICATE'])))
        forced=next(state for _,point,state in steps if point=='REPLAY_CLAIM_FORCED')
        self.assertEqual(m.physical({'x':claim})['x'],forced[m.DIRECTORY+'/claim.json'])

    def test_retirement_cannot_borrow_different_image_generation_or_data_semantics(self):
        for changed,reason in (('manifest','retained generation'),('image','unchanged control image'),('data','control record only')):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'replay retirement '+reason):self.retained(changed)


if __name__=='__main__':unittest.main()
