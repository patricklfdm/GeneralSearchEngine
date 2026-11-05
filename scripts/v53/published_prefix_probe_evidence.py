"""The required-four local published-prefix probe and its original permission.

Observation markers identify actual calls; generation bytes and retained learner
authority come from the independently admitted original history, not markers.
"""
import base64
from . import joining_control_evidence as control
from . import probe_export_evidence as probe
from . import connection_transcript as transcript

need=control.need;f=control.f;sha=control.sha
EVENTS=('PUBLISHED_PREFIX_PROBE_BEGIN','PUBLISHED_PREFIX_PROBE_REFERENCES','PUBLISHED_PREFIX_PROBE_RETURNED')


def references(own,alias):
    files=own['members'];packet=files['source.gscp'];result={}
    for name,raw in files.items():
        if name!='source.gscp' and not name.endswith('.image'):continue
        digest=sha(raw);need(digest not in result,'published probe distinct original contents')
        result[digest]=dict(reference=digest,digest=digest,bytes=len(raw),kind='CAPSULE' if name=='source.gscp' else 'APPLICATION')
    need(alias not in result,'published probe original alias collision')
    result[alias]=dict(reference=alias,digest=sha(packet),bytes=len(packet),kind='CAPSULE')
    return [result[key] for key in sorted(result)]


def derive(reader,boundaries):
    events=reader.events
    marked=[(i,v) for i,v in enumerate(events) if type(v.get('event')) is str and v['event'].startswith('PUBLISHED_PREFIX_PROBE_')]
    need(len(marked)==3 and [v['event'] for _,v in marked]==list(EVENTS),'published probe complete original observations')
    need(len(boundaries)==len(events),'published probe complete original boundaries')
    (begin,first),(body,middle),(end,last)=marked
    fields=({'node','event','request','bytes'},{'node','event','request','contents'},{'node','event','request'})
    need(all(set(row)==keys for (_,row),keys in zip(marked,fields)),'published probe exact observation shape')
    node=first['node'];kind,q=transcript.wire(first['bytes'])
    raw=base64.b64decode(first['bytes'],validate=True);binding=sha(raw)
    need(all(v['node']==node and v['request']==binding for _,v in marked),'published probe exact original call')
    need(kind=='CHUNK' and q['sequence']==1 and q['payload']['action']=='REQUEST' and q['payload']['offset']==0 and q['payload']['bytes']=='',
         'published probe original initial request')
    own=control.e.current(reader.windows,node,begin,end);cap=own['packet']['capsule']
    selected=f.decode(reader.model.phases[8]['SELECTED'],'records','SELECTED')
    identities=control.n.s.catalog.identities(reader.model.states[9]['identities'])
    need(node==selected['ballot']['proposer'] and cap['cut']==reader.model.states[9]['cut'] and q['root']==reader.model.root and
         q['recipient']==own['identity'] and q['sender']==identities.get(reader.model.joining),
         'published probe original joint owner and learner')
    need(control.e.learner_alias(own,q)=='prefix','published probe exact progress prefix alias')
    need(reader.learner_permission(own,q,begin,body,end)=='published','published probe original published permission')
    need(type(middle['contents']) is list and f.canonical(middle['contents'])==f.canonical(references(own,q['payload']['digest'])),
         'published probe exact original reference inventory')
    points=[]
    for at,_ in marked:
        point=boundaries[at]
        need(type(point) is dict and set(point)=={'eventIndex','node','sequence','usage'} and type(point['eventIndex']) is int and point['eventIndex']==at and
             point['node']==node and type(point['sequence']) is int and point['sequence']>=0,'published probe exact resource boundary')
        points.append(point['sequence'])
    need(points[0]<points[1]<points[2],'published probe ordered resource interval')
    manifest=f.decode(own['manifest'],'records','GENERATION')
    need(manifest['node']==node and manifest['root']==reader.model.root,'published probe original generation identity')
    return [dict(node=node,role='prefix-export',binding=sha(own['manifest']),bytes=4096,children=[],
                 before=points[0],through=points[1],after=points[2])]


def replay(traces,closes,reader,boundaries):
    result=probe.replay(traces,closes,derive(reader,boundaries))
    return dict(result,scope='required-four-original-published-prefix-probe',originalReferenceInventoryQualified=True,
                originalPermissionWindowQualified=True,fullBodyReadsQualified=False)
