"""Local borrowed exports across the complete required-four history.

The admitted SELECTED set determines activation owners. Admitted floor inputs
determine network maintenance borrows; fixture-supplied direct floors do not
invent a runtime borrow. Repeated original generations require distinct calls.
"""
from . import direct_export_evidence as direct
from . import floor_resource_evidence as floors

need=direct.need;f=floors.maintenance.m.f;sha=floors.sha


def derive(reader,boundaries):
    events=reader.events
    need(type(boundaries) is list and len(boundaries)==len(events),'required-four direct complete boundaries')
    def sequence(at,node):
        point=boundaries[at]
        need(point['eventIndex']==at and type(point['eventIndex']) is int and point['node']==node and
             type(point['sequence']) is int and point['sequence']>=0,'required-four direct exact event boundary')
        return point['sequence']
    selections={sha(parts['SELECTED']):f.decode(parts['SELECTED'],'records','SELECTED') for parts in reader.model.phases}
    selected_nodes={v['voter'] for value in selections.values() for v in value['sources']}
    result=[];used_installs=set();used_forces=set()
    for node in sorted(selected_nodes):
        expected=[v for v in selections.values() if node in {s['voter'] for s in v['sources']}]
        forced=[i for i,v in enumerate(events) if v.get('node')==node and v['event']=='SELECTED_FORCED']
        need(len(forced)==len(expected),'required-four direct complete original selections')
        for ordinal,(at,selection) in enumerate(zip(forced,expected)):
            upper=forced[ordinal+1] if ordinal+1<len(forced) else len(events)
            installs=[i for i in range(at+1,upper) if events[i].get('node')==node and events[i]['event']=='INSTALL_BEFORE_RETURN']
            need(len(installs)==1,'required-four direct exact selected installation')
            end=installs[0];reference=next(s for s in selection['sources'] if s['voter']==node)
            candidates=[s for s in reader.sources if s['node']==node and sha(s['basis'])==reference['basisDigest'] and
                        s['value']['basisId']==reference['basisId'] and s['value']['ballot']==selection['ballot'] and s['start']<at<end<s['end']]
            need(len(candidates)==1,'required-four direct original local source')
            source=candidates[0];promise=f.decode(source['promise'],'records','PROMISE')
            need(promise['basisId']==reference['basisId'] and promise['ballot']==selection['ballot'],
                 'required-four direct original local promise')
            granted=source.get('returnEvent');captured=events[source['start']]
            need(type(granted) is int and 0<=granted<source['start'] and events[granted].get('node')==node and
                 events[granted]['event']=='GRANT_BEFORE_RETURN' and captured.get('node')==node and
                 captured['event']=='GRANT_CAPTURED' and captured.get('basis')==reference['basisDigest'],
                 'required-four direct original grant return')
            result.append(dict(node=node,phase='ACTIVATION' if node==selection['ballot']['proposer'] else 'SELECTED',
                               reference=reference['basisDigest'],bytes=len(source['basis'])+len(source['promise']),
                               after=sequence(granted,node),through=sequence(end,node)))
            used_installs.add(end);used_forces.add(at)
    need(used_installs=={i for i,v in enumerate(events) if v['event']=='INSTALL_BEFORE_RETURN'} and
         used_forces=={i for i,v in enumerate(events) if v['event']=='SELECTED_FORCED'},'required-four direct complete activation coverage')
    floor_plans=floors.plans(reader)
    by_start={(v['own']['node'],v['start']):v for v in reader.floor_inputs}
    need(len(by_start)==len(reader.floor_inputs),'required-four direct unique floor inputs')
    for floor in floor_plans:
        if not floor['network']:continue
        node=floor['node'];own=by_start[node,floor['start']]['own']
        manifest=f.decode(own['manifest'],'records','GENERATION')
        need(manifest['node']==node and manifest['root']==reader.model.root,'required-four direct original floor generation')
        result.append(dict(node=node,phase='MAINTENANCE',reference=sha(own['manifest']),bytes=4096,
                           before=sequence(floor['start'],node),through=sequence(floor['end'],node)))
    need(result,'required-four direct missing original intervals')
    return result


def replay(traces,closes,reader,boundaries):
    result=direct.replay(traces,closes,derive(reader,boundaries))
    return dict(result,scope='required-four-native-direct-export-ownership')
