"""Authenticate a rejected cross-generation maintenance read, never a floor copy.

A nonselected PREPARE can force its grant, then read a complete old packet and
a complete new manifest on separate connections while a donor installs at the
same cut. The native receiver rejects that capsule mismatch. Preserve both
objects and the failed control; neither a PROMISE nor a generation copy exists.
"""
from collections import Counter
from . import joining_export_evidence as e

need=e.need
REASON='java.lang.IllegalArgumentException: ancestry manifest owner/capsule'


def context(q):
    return {k:q[k] for k in ('root','view','ballot','sender','recipient')}


def bind(events,rows,failed,contents,windows,sources,diagnostics):
    groups=e.sessions(contents)
    rejected=Counter(d['request'] for d in diagnostics if d.get('kind')=='PREPARE' and d.get('failure')==REASON)
    for digest,count in rejected.items():
        terminals=[v for v in failed if v['kind']=='PREPARE' and v['requestHash']==digest and
                   not v.get('responseOffered',True)]
        need(1<=len(terminals)==count<=3 and all(type(v['received']) is int and type(v['serverFailed']) is int
             for v in terminals),'joining interrupted preparation original terminal')
        terminal=min(terminals,key=lambda v:v['received']);kind,q=e.n.wire(events[terminal['sent']]['bytes']);node=q['recipient']['node']
        end=min(v['serverFailed'] for v in terminals)
        need(kind=='PREPARE' and all(v['clientReason']=='IO' and v['serverReason']=='PROTOCOL' and
             e.n.wire(events[v['sent']]['bytes'])==(kind,q) for v in terminals) and
             not any(r['kind']=='PREPARE' and r['request']==q for r in rows),
             'joining interrupted preparation response-less control')
        grants=[v for v in sources if v['node']==node and v['value']['ballot']==q['ballot'] and
                v['value']['view']==q['view'] and terminal['received']<v['start']<end]
        need(len(grants)==1 and not any(r['kind']=='SELECTED' and r['request']['recipient']==q['recipient'] and
             r['request']['ballot']==q['ballot'] for r in rows),'joining interrupted preparation nonselected grant')
        candidates=[]
        for values in groups:
            first,last=values[0]['offer'],values[-1]['commit'];request=first['request']
            if not (len(values)==1 and values[0]['kind']=='RECORD' and e.record_kind(values[0]['raw'])=='GENERATION' and
                    request['sender']==q['recipient'] and request['root']==q['root'] and request['view']==q['view'] and
                    request['ballot']==q['ballot'] and grants[0]['start']<first['sent'] and
                    type(last['delivered']) is int and last['delivered']<end):continue
            after=e.current(windows,request['recipient']['node'],first['offered'],last['offered'])
            cap=after['packet']['capsule']
            if request['payload']['digest']!=e.native.current_reference(cap,'retained-current-generation-metadata'):continue
            packets=[v for v in groups if len(v)==1 and v[0]['kind']=='CAPSULE' and
                     context(v[0]['offer']['request'])==context(request) and
                     grants[0]['start']<v[0]['offer']['sent'] and v[-1]['commit']['delivered']<first['sent'] and
                     v[0]['offer']['request']['payload']['digest']==e.native.current_reference(cap,'retained-current-packet')]
            if len(packets)!=1:continue
            packet=packets[0][0]
            before=e.current(windows,request['recipient']['node'],packet['offer']['received'],packet['commit']['offered'])
            need(before['end']<after['start'] and after.get('sourcePredecessor')==(before['start'],before['end']) and
                 before['identity']==after['identity']==request['recipient'] and
                 before['packet']['capsule']['cut']==cap['cut'] and
                 events[before['end']].get('event')=='INSTALL_SELECTOR_RENAMED' and
                 events[before['end']].get('node')==after['node'] and
                 packet['commit']['offered']<before['end']<first['offered'] and
                 packet['raw']==before['members']['source.gscp'] and values[0]['raw']==after['manifest'] and
                 before['packet']['capsuleBytes']!=after['packet']['capsuleBytes'],
                 'joining interrupted preparation exact capsule switch')
            observed=[r for r in rows if r['request']['trace']==request['trace'] and
                      r['request']['sender']==request['sender'] and r['request']['recipient']==request['recipient']]
            need([r['answer'] for r in sorted(observed,key=lambda r:r['sent'])]==['SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'] and
                 all(type(r['delivered']) is int and not r.get('failedAttempt',False) for r in observed),
                 'joining interrupted preparation manifest-only transfer')
            # Failed extra sends on this trace must not disappear merely because
            # they offered no response and therefore are not in contents.
            for at,event in enumerate(events):
                if event.get('event') not in e.n.SENDS or event.get('kind') not in ('CHUNK','TRANSFER_COMMIT'):continue
                _,sent=e.n.wire(event['bytes'])
                if sent['trace']==request['trace'] and sent['sender']==request['sender'] and sent['recipient']==request['recipient']:
                    need(any(at==r['sent'] and sent==r['request'] for r in observed),
                         'joining interrupted preparation continued trace')
            candidates.append((values,after))
        need(len(candidates)==1,'joining interrupted preparation exact rejected manifest')
        values,after=candidates[0];first=values[0]['offer']
        need('abortedPreparation' not in first and 'abortedPrefix' not in first,'joining interrupted preparation reused transfer')
        first['abortedPreparation']=dict(request=q,serverFailed=end,terminalAttempts=len(terminals),
            generationStart=after['start'],selector=after['sourcePredecessor'][1])
