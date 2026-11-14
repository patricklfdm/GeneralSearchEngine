"""Replay a cancelled, unselected grant's observed source prefix without a vote.

The original reader still derives the grant and its lifetime. An offered last
chunk has no client delivery or COMMIT and never enters the completed sources.
"""
import base64
from . import joining_export_evidence as exports


def partition(history, events, rows):
    from . import native_carried_transition_network as n
    need, c, f, sha = n.need, n.c, n.f, n.e.digest
    traces = {v['request']['trace'] for v in rows if v['kind'] == 'CHUNK' and v['delivered'] is None}
    removed = set(); partials = []
    activation = history.activations() if traces else None
    for trace in sorted(traces):
        own = sorted([v for v in rows if v['request']['trace'] == trace], key=lambda v:v['sent'])
        need(len(own) == 8, 'transition cancelled source exact prefix')
        first, last = own[0], own[-1]; q = first['request']; node = q['recipient']['node']
        stages = [(i,s) for i,s in enumerate((v for v in history.ranges if v['kind']=='campaign'),1)
                  if s['start'] < first['sent'] < last['offered'] < s['stop']]
        need(len(stages)==1, 'transition cancelled source campaign')
        ordinal, stage = stages[0]; files = activation.unselected.get((ordinal,node))
        need(files is not None, 'transition cancelled source must be unselected')
        selected = f.decode(activation.phases[ordinal-1]['SELECTED'],'records','SELECTED')
        need(q['sender']['node']==selected['ballot']['proposer'] and q['ballot']==selected['ballot'] and
             q['view']==selected['view'], 'transition cancelled source authority')
        journal = [(raw,v) for kind,raw,v in c.journal(files['grants.gsr'],selected['root'],node)
                   if v['ballot']==selected['ballot'] and kind in ('PROMISE','BASIS')]
        need(len(journal)==2, 'transition cancelled source original grant')
        promise,basis = journal[0][0],journal[1][0]; value=journal[1][1]
        raw = files['sources/'+value['basisId']+'/source.gscp']; packet=c.p.decode(raw)
        need(all(v['delivered'] is not None for v in own[:-1]) and last['delivered'] is None and
             all(v['sent'] < v['received'] < v['offered'] and
                 (v['delivered'] is None or v['offered'] < v['delivered']) for v in own) and
             all(a['delivered'] < b['sent'] for a,b in zip(own,own[1:])),
             'transition cancelled source original delivery')
        complete=[];n.network.transcript.transfers(own[:6],contents=complete)
        exports.exact(complete,[(sha(basis),basis,'RECORD'),(sha(promise),promise,'RECORD')],
                      'transition cancelled source original records')
        offer,chunk=own[-2:];oq=offer['request'];ap=offer['response']['payload'];identifier=oq['payload']['id']
        header={k:v for k,v in q.items() if k not in ('payload','sequence')}
        need(all({k:v for k,v in z['request'].items() if k not in ('payload','sequence')}==header and
                 z['request']['sequence']==i for i,z in enumerate(own,1)),
             'transition cancelled source sequence')
        need(0<len(raw)<=4*n.e.MIB and len({own[i]['request']['payload']['id'] for i in (0,3,6)})==3 and
             offer['kind']=='CHUNK' and offer['answer']=='SOURCE_OFFER' and
             oq['payload']==dict(id=identifier,action='REQUEST',offset=0,digest=sha(packet['capsuleBytes']),bytes='') and
             ap==dict(id=identifier,kind='CAPSULE',digest=sha(raw),bytes=len(raw)) and
             chunk['kind']==chunk['answer']=='CHUNK' and
             chunk['request']['payload']==dict(id=identifier,action='REQUEST',offset=0,digest=sha(raw),bytes='') and
             chunk['response']['payload']==dict(id=identifier,action='DATA',offset=0,digest=sha(raw),bytes=base64.b64encode(raw).decode()),
             'transition cancelled source exact offered capsule')
        grants=[i for i,v in enumerate(events) if stage['start']<i<first['sent'] and v.get('node')==node and v['event']=='GRANT_BEFORE_RETURN']
        need(len(grants)==1 and not any(v.get('node')==node and v['event']=='SOURCE_RETIREMENT_CREATED'
             for v in events[grants[0]+1:last['offered']+1]), 'transition cancelled source live original')
        removed.update(v['offered'] for v in own)
        partials.append(dict(first=first,last=last,basis=basis,promise=promise,raw=raw,offer=offer))
    return [v for v in rows if v['offered'] not in removed], partials


def authority(partials, windows, sources):
    for part in partials:
        first,last=part['first'],part['last'];q=first['request']
        matches=[v for v in sources if v['node']==q['recipient']['node'] and v['basis']==part['basis']]
        exports.need(len(matches)==1,'transition cancelled source lifetime identity')
        source=matches[0]
        exports.need(source['start']<first['received']<last['offered']<source['end'] and
                     source['promise']==part['promise'] and source['members']['source.gscp']==part['raw'],
                     'transition cancelled source lifetime bytes')
        exports.source_authority(windows,q,first['received'],first['offered'])
        exports.need(q['view']==source['value']['view'] and q['ballot']==source['value']['ballot'],
                     'transition cancelled source lifetime authority')
    return len(partials)
