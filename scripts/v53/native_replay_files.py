"""Fresh control-record core scratch from independently replayed authority.

Only INTENT/FINAL/BARRIER are supported. They materialize the exact input image
and create no output backup. This is not a model of interrupted core DATA writes.
"""
from . import native_carried_transition_physical as p
from .native_campaign_files import physical
from .offline_fixture_image import image_members

f=p.f;need=p.need
DIRECTORY='application-replay'
KINDS={'replay':('REPLAY_',)}
POINTS=('REPLAY_RESERVED','REPLAY_DIRECTORY_CREATED','REPLAY_CLAIM_CREATED',
        'REPLAY_CLAIM_PREFIX_WRITTEN','REPLAY_CLAIM_WRITTEN','REPLAY_CLAIM_FORCED',
        'REPLAY_BEFORE_APPLICATION','REPLAY_APPLICATION_FINISHED','REPLAY_BEFORE_DELETE',
        'REPLAY_DELETED','REPLAY_BEFORE_RETURN')


def transaction(initial,applied):
    need(not any(k==DIRECTORY or k.startswith(DIRECTORY+'/') for k in initial),'replay prefix fresh scratch')
    need({k:v for k,v in applied.items() if k!='applied-end' and not k.startswith('applied-end/')}==initial,
         'replay prefix outside application end')
    frames,_=p.data.pending(initial)
    need('CERTIFICATE' in frames and frames['SELECTOR']==initial['selector.gsr'],'replay prefix original certificate')
    entry=f.decode(frames['ENTRY'],'records','ENTRY')
    need(entry['kind'] in ('INTENT','FINAL','BARRIER'),'replay prefix control record only')
    identity=f.decode(initial['node.gsr'],'records','NODE')['identity']
    selector=f.decode(frames['SELECTOR'],'records','SELECTOR')
    certificate=f.decode(frames['CERTIFICATE'],'records','CERTIFICATE')
    need(selector['node']==identity['node'] and selector['root']==certificate['root'],'replay prefix original binding')
    _,members,packet=p.c.current(initial);image=members[packet['capsule']['application']+'.image']
    need(applied.get('applied-end/application.image')==image,'replay prefix unchanged control image')
    claim=f.canonical(dict(schema='gse-v53-application-replay/1.3',root=selector['root'],node=identity['node'],
                           storage=identity['storage'],selector=p.e.digest(frames['SELECTOR']),
                           certificate=p.e.digest(frames['CERTIFICATE'])))
    state=dict(initial);steps=[];key=DIRECTORY+'/claim.json'
    def event(point):steps.append(('replay',point,physical(state)))
    event('REPLAY_RESERVED');state[DIRECTORY]=None;event('REPLAY_DIRECTORY_CREATED')
    state[key]=b'';event('REPLAY_CLAIM_CREATED');state[key]=claim[:len(claim)//2];event('REPLAY_CLAIM_PREFIX_WRITTEN')
    state[key]=claim;event('REPLAY_CLAIM_WRITTEN');event('REPLAY_CLAIM_FORCED');event('REPLAY_BEFORE_APPLICATION')
    state[DIRECTORY+'/work']=None;state[DIRECTORY+'/work/input']=None
    state.update({DIRECTORY+'/work/input/'+k:v for k,v in image_members(image).items()})
    event('REPLAY_APPLICATION_FINISHED')
    names=sorted((k for k in state if k.startswith(DIRECTORY+'/work/')),key=lambda k:(-len(k.split('/')),k))
    names += [DIRECTORY+'/work',key,DIRECTORY]
    for name in names:
        event('REPLAY_BEFORE_DELETE');del state[name];event('REPLAY_DELETED')
    need(state==initial,'replay prefix original cleanup');event('REPLAY_BEFORE_RETURN')
    return steps
