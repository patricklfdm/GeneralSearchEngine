"""Exact portable states for one original six-revision learner history.

Native voter generations and receipts must be independently derived by the
history reader before entering this model. This module never opens recorded
paths, confers authority, or returns a stand-alone acceptance receipt.
"""
import base64
from . import learner_slot_snapshot as snap
from . import learner_vacancy_evidence as vacancy
from . import learner_typed_evidence as typed
from . import source_packet
s,e,f,need=snap,snap.e,snap.f,snap.need


def record(raw,maximum=16384):
    need(type(raw) is bytes and 0<len(raw)<=maximum,'learner cycles bounded record')
    value=e.parse(raw)
    need(type(value) is dict and f.canonical(value)==raw,'learner cycles canonical record')
    return value


def fingerprint(snapshot,root,prefix='',names=None):
    """Rebuild original identity fingerprints with paths relative to the owner."""
    members=snapshot.identities[root]['members']
    rows={('.' if k==prefix else k[len(prefix)+1:]):v for k,v in members.items()
          if prefix and (k==prefix or k.startswith(prefix+'/'))} if prefix else members
    names=set(rows) if names is None else set(names)
    need(names<=set(rows),'learner cycles fingerprint inventory')
    return [dict(path=k,sha256=s.digest(f.canonical(rows[k]))) for k in sorted(names)]


def source_tree(original,prefix):
    return {prefix:None,**{prefix+'/'+k:v for k,v in original.items()}}


def terminal(original):
    packet=source_packet.decode(original['source.gscp'])['capsule']
    return dict(source=s.digest(original['source.gscp']),**{k:packet[k] for k in ('cut','catalog','application')})


class States:
    def __init__(self,originals,receipts,request,learner,root_bytes,descriptor):
        self.originals,self.receipts=originals,receipts
        self.request,self.learner,self.root_bytes,self.descriptor=request,learner,root_bytes,descriptor
        self.expected=None;self.previous=None;self.paths=None;self.core=None;self.summary=None;self.sequence=0

    def check(self,observed,expected,generations,applications):
        need(observed.files==expected,'learner cycles exact snapshot bytes')
        paths={k:v['path'] for k,v in observed.identities.items()}
        if self.paths is not None:need(paths==self.paths,'learner cycles fixed root paths')
        self.paths=paths
        if self.previous is not None:
            for root,files in expected.items():
                for name,value in files.items():
                    old=self.previous.files[root]
                    if name in old and old[name]==value:
                        need(observed.identities[root]['members'][name]==self.previous.identities[root]['members'][name],
                             'learner cycles unchanged original identity')
        counts=observed.resources['counts']
        need(counts.get('GENERATION')==generations and counts.get('APPLICATION')==applications
             and 'LEARNER' not in counts,'learner cycles retained resource counts')
        self.expected={k:dict(v) for k,v in expected.items()};self.previous=observed

    def changed(self,**roots):return dict(self.expected,**roots)

    def key(self,observed,root,name='.'):
        return observed.identities[root]['members'][name]['key']

    def path(self,observed,root):return s.original_path(observed.identities[root]['path'])

    def materialized(self,observed,root,revision,initial=False):
        data=observed.files[root];value=record(data.get('preparation.json'),256*1024 if initial else 16384)
        path=typed.binding(value.get('path'));core=typed.binding(value.get('materialization'))
        need(path==self.path(observed,root),'learner cycles typed path')
        if self.core is None:self.core=value['materialization']
        need(value['materialization']==self.core,'learner cycles original core binding')
        all_paths=[self.path(observed,k) for k in s.ROOTS]+[core]
        need(all(p!=q and p not in q.parents and q not in p.parents for i,p in enumerate(all_paths) for q in all_paths[i+1:]),
             'learner cycles disjoint typed core')
        receipt=self.receipts[revision];original=self.originals[revision]
        expected=dict(schema='gse-v53-learner-typed/1.3' if initial else 'gse-v53-successor-typed/1.3',plan=self.summary,
                      source=s.digest(original['source.gscp']),receipt=base64.b64encode(receipt).decode() if initial else s.digest(receipt),
                      configuration=self.descriptor if initial else s.digest(f.canonical(self.descriptor)),path=value['path'],
                      materialization=self.core,directoryKey=self.key(observed,root))
        need(data['preparation.json']==f.canonical(expected),'learner cycles exact typed plan')
        result={'.':None,'preparation.lock':b'','preparation.json':f.canonical(expected),'learner.gsr':receipt,'backup':None}
        digest=f.decode(receipt,'records','LEARNER')['receipt']['image']
        result.update({'backup/'+k:v for k,v in typed.images.image_members(original[digest+'.image']).items()})
        if initial:
            result['prepared.json']=f.canonical(dict(schema='gse-v53-learner-prepared/1.3',root=self.request['root'],identity=self.learner,
                plan=self.summary,typedPlan=s.digest(result['preparation.json']),source=expected['source'],receipt=s.digest(receipt),
                location=str(self.path(observed,'replica')/'learner')))
        need(data==result,'learner cycles original typed image and receipt')
        return result

    def installed_plan(self,observed,root,name,revision,anchor=None,sequence=0):
        raw=observed.files[root].get(name);value=record(raw,256*1024);original=self.originals[revision]
        prefix='source' if root=='seed' or sequence%2==0 else 'source-b'
        path=typed.binding(value.get('path'));staging=typed.binding(value.get('staging'))
        need(path==self.path(observed,root),'learner cycles deterministic source path')
        paths=[self.path(observed,k) for k in s.ROOTS]+[typed.binding(self.core)]
        need(all(staging!=p and staging not in p.parents and p not in staging.parents for p in paths),'learner cycles disjoint staging')
        files=[dict(path=k,size=len(v),sha256=s.digest(v),key=self.key(observed,'seed' if sequence and sequence%2==0 else root,prefix+'/'+k)) for k,v in sorted(original.items())]
        source_root='seed' if sequence and sequence%2==0 else root
        common=dict(plan=self.summary,path=value['path'],directoryKey=self.key(observed,root),staging=value['staging'],
                    sourceKey=self.key(observed,source_root,prefix),source=next(v for v in self.request['target'] if v['node']=='node-1'),
                    generation=base64.b64encode(original['generation.gsr']).decode(),files=files)
        if sequence==0:
            expected=dict(schema='gse-v53-learner-successor/1.3',previous=terminal(self.originals[1]),receipt=s.digest(self.receipts[1]),**common)
        else:
            expected=dict(schema='gse-v53-learner-slot/1.3' if sequence==1 else 'gse-v53-learner-slot-reuse/1.3' if sequence==2 else 'gse-v53-learner-slot-rolling/1.3',
                          slot='a' if sequence%2==0 else 'b',sequence=sequence,anchor=anchor,**common)
            if sequence>1:
                expected.update(vacancy=self.vacancy(),planKey=self.key(observed,root,name))
            if sequence>2:expected['replaces']=self.head()['previousPlan']
        need(raw==f.canonical(expected),'learner cycles original installed plan')
        return raw

    def initial(self,observed):
        operation=observed.files['operation'];raw=operation.get('learner.gslp');original=self.originals[1]
        peer=next(v for v in self.request['target'] if v['node']=='node-1')
        plan=typed.s.p.plan(raw,self.root_bytes,original,self.request,self.learner,peer);self.summary=s.digest(raw)
        paths=[typed.binding(v) for v in plan['paths']]
        need(set(paths)=={self.path(observed,'operation'),self.path(observed,'replica')},'learner cycles admission paths')
        parent=self.path(observed,'operation').parent
        for root,prefix in [('initial-typed','.gse-v53-learner-'),('seed','.gse-v53-learner-successor-'),('seed-typed','.gse-v53-learner-ready-'),
                            ('slots','.gse-v53-learner-slots-'),('slot-typed','.gse-v53-learner-slot-b-')]:
            need(self.path(observed,root)==parent/(prefix+self.summary),'learner cycles deterministic roots')
        retention=operation.get(typed.s.RETAIN);decision=typed.s.retention(retention,raw,plan)
        need(decision['directoryKey']==self.key(observed,'replica','learner') and
             decision['files']==[dict(v,key=self.key(observed,'replica','learner/'+v['path'])) for v in plan['files']],
             'learner cycles retained original identities')
        need(all(typed.binding(decision['staging'])!=p and p not in typed.binding(decision['staging']).parents and typed.binding(decision['staging']) not in p.parents for p in paths),'learner cycles original staging')
        expected={k:{} for k in s.ROOTS}
        expected['operation']={'.':None,'operation.lock':b'','learner.gslp':raw,typed.s.RETAIN:retention}
        expected['replica']={'.':None,'replica.lock':b'','root.gsr':self.root_bytes,'node.gsr':f.encode('records','NODE',dict(root=self.request['root'],identity=self.learner)),typed.s.ADMISSION:retention,**source_tree(original,'learner')}
        expected['initial-typed']=self.materialized(observed,'initial-typed',1,True)
        expected['seed-typed']=self.materialized(observed,'seed-typed',2)
        install=self.installed_plan(observed,'seed','install.json',2)
        selected=f.canonical(dict(schema='gse-v53-learner-successor-selected/1.3',plan=s.digest(install),root=self.request['root'],identity=self.learner,
                                  generation=s.digest(self.originals[2]['generation.gsr']),location=str(self.path(observed,'seed')/'source')))
        expected['seed']={'.':None,'successor.lock':b'','install.json':install,'selected.json':selected,**source_tree(self.originals[2],'source')}
        self.check(observed,expected,2,4)

    def seed_selected(self,observed):
        head=dict(schema='gse-v53-learner-head/1.3',plan=self.summary,installed=s.digest(self.expected['seed']['install.json']),
                  source=s.digest(self.originals[2]['source.gscp']),generation=s.digest(self.originals[2]['generation.gsr']),receipt=s.digest(self.receipts[2]),
                  previousFiles=fingerprint(self.previous,'initial-typed'),currentFiles=fingerprint(self.previous,'seed-typed'))
        self.check(observed,self.changed(seed=dict(self.expected['seed'],**{'head.json':f.canonical(head)})),2,4)

    def seed_retired(self,observed):
        seed=dict(self.expected['seed']);seed['retire.json']=f.canonical(dict(schema='gse-v53-learner-retirement/1.3',plan=self.summary,
            retention=s.digest(self.expected['operation'][typed.s.RETAIN]),head=s.digest(seed['head.json']),headKey=self.key(self.previous,'seed','head.json')))
        replica={k:v for k,v in self.expected['replica'].items() if k!='learner' and not k.startswith('learner/')}
        self.check(observed,self.changed(seed=seed,replica=replica,**{'initial-typed':{}}),1,2)

    def head(self):return record(self.expected['slots']['head.json'])

    def anchor(self):
        head=record(self.expected['seed']['head.json']) if self.sequence==0 else self.head()
        return dict(head=s.digest(self.expected['seed' if self.sequence==0 else 'slots']['head.json']),receipt=head['receipt'],
                    core=self.core,previous=terminal(self.originals[self.sequence+2]))

    def vacancy(self):
        head=self.head();clear=record(self.expected['slots']['cleared.json'])
        return dict(head=s.digest(self.expected['slots']['head.json']),headKey=head['headKey'],cleared=s.digest(self.expected['slots']['cleared.json']),clearKey=clear['clearKey'])

    def installed(self,observed,sequence,already_typed=False):
        need(type(sequence) is int and sequence==self.sequence+1,'learner cycles sequence order');slot='a' if sequence%2==0 else 'b';revision=sequence+2
        plan=self.installed_plan(observed,'slots',slot+'.json',revision,self.anchor(),sequence)
        location=self.path(observed,'seed')/'source' if slot=='a' else self.path(observed,'slots')/'source-b'
        marker=f.canonical(dict(schema='gse-v53-learner-slot-installed/1.3',plan=s.digest(plan),generation=s.digest(self.originals[revision]['generation.gsr']),location=str(location)))
        slots=dict(self.expected['slots'] or {'.':None,'slots.lock':b''});slots.update({slot+'.json':plan,slot+'.installed.json':marker})
        roots=self.changed(slots=slots)
        root,prefix=('seed','source') if slot=='a' else ('slots','source-b')
        roots[root]=dict(roots[root],**source_tree(self.originals[revision],prefix))
        if already_typed:roots['seed-typed' if slot=='a' else 'slot-typed']=self.materialized(observed,'seed-typed' if slot=='a' else 'slot-typed',revision)
        self.check(observed,roots,2,4 if already_typed else 3)

    def prepared(self,observed,sequence):
        root='seed-typed' if sequence%2==0 else 'slot-typed'
        self.check(observed,self.changed(**{root:self.materialized(observed,root,sequence+2)}),2,4)

    def selected(self,observed,sequence):
        need(sequence==self.sequence+1,'learner cycles sequence order');slot='a' if sequence%2==0 else 'b';revision=sequence+2
        old_root,old_prefix=('seed','source') if slot=='b' else ('slots','source-b')
        old_typed='seed-typed' if slot=='b' else 'slot-typed';current_typed='slot-typed' if slot=='b' else 'seed-typed'
        head=dict(schema='gse-v53-learner-slot-head/1.3' if sequence==1 else 'gse-v53-learner-rolling-head/1.3',
                  plan=s.digest(self.expected['slots'][slot+'.json']),source=s.digest(self.originals[revision]['source.gscp']),
                  generation=s.digest(self.originals[revision]['generation.gsr']),receipt=s.digest(self.receipts[revision]),headKey=self.key(observed,'slots','head.json'),
                  seedFiles=fingerprint(self.previous,'seed',names=vacancy.SEED),previousFiles=fingerprint(self.previous,old_root,old_prefix),
                  previousTyped=fingerprint(self.previous,old_typed),currentFiles=fingerprint(self.previous,current_typed))
        if sequence>1:
            old='b' if slot=='a' else 'a'
            head.update(slot=slot,sequence=sequence,previousAnchor=self.anchor(),previousPlan=fingerprint(self.previous,'slots',names={'.',old+'.json',old+'.installed.json'}),priorVacancy=self.vacancy())
            need(head['headKey']!=self.key(self.previous,'slots','head.json'),'learner cycles replaced original head inode')
        self.check(observed,self.changed(slots=dict(self.expected['slots'],**{'head.json':f.canonical(head)})),2,4);self.sequence=sequence

    def retired(self,observed):
        old_root,prefix=('seed','source') if self.sequence%2 else ('slots','source-b')
        old_typed='seed-typed' if self.sequence%2 else 'slot-typed'
        roots=self.changed(**{old_root:{k:v for k,v in self.expected[old_root].items() if k!=prefix and not k.startswith(prefix+'/')},old_typed:{}})
        head=self.head();clear=dict(schema='gse-v53-learner-slot-cleared/1.3',plan=head['plan'],head=s.digest(self.expected['slots']['head.json']),headKey=head['headKey'],clearKey=self.key(observed,'slots','cleared.json'))
        clear.update({k:s.digest(f.canonical(head[k])) for k in ('previousFiles','previousTyped','seedFiles')})
        if self.sequence>1:need(clear['clearKey']!=self.key(self.previous,'slots','cleared.json'),'learner cycles replaced original clear inode')
        roots['slots']=dict(roots['slots'],**{'cleared.json':f.canonical(clear)});self.check(observed,roots,1,2)

    def reopened(self,observed):self.check(observed,self.expected,1,2)
