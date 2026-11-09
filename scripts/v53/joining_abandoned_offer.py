"""Authenticate revoked generation offers without creating received content."""
from . import joining_export_evidence as e

need=e.need


def authorize(rows,windows):
    result=[]
    for row in rows:
        claim=row.get('abortedPrefix',{})
        if not claim.get('offerOnly',False):continue
        q=row['request'];node=q['recipient']['node']
        own=e.current(windows,node,row['received'],row['offered']);cap=own['packet']['capsule']
        identities=e.n.s.catalog.identities(e.f.decode(own['packet']['objects'][cap['catalog']],'records','CATALOG')['identities'])
        proposer=identities.get(q['ballot']['proposer'])
        need(q['sender']==identities.get(q['sender']['node']) and q['recipient']==own['identity'] and
             proposer is not None and q['ballot']['incarnation']==proposer['storage'] and
             q['root']==cap['root'] and q['view']==e.n.s.catalog.authority(cap['root'],cap['cut']['view']),
             'joining abandoned offer permanent authority')
        reference=q['payload']['digest']
        expected=[values[0] for values in e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])
                  if values[0][0]==reference]
        need(len(expected)==1 and claim['selector']==own['end'], 'joining abandoned offer generation boundary')
        _,raw,kind=expected[0];offer=row['response']['payload']
        need(row['answer']=='SOURCE_OFFER' and row['request']['sequence']==1 and
             q['payload']==dict(id=offer['id'],action='REQUEST',offset=0,digest=reference,bytes='') and
             offer==dict(id=offer['id'],digest=e.sha(raw),bytes=len(raw),kind=kind) and
             claim['request']['payload']==dict(id=offer['id'],action='REQUEST',offset=0,digest=e.sha(raw),bytes=''),
             'joining abandoned offer exact original manifest')
        result.append(dict(owner=node,reader=q['sender']['node'],trace=q['trace'],selector=claim['selector'],
            manifest=e.sha(raw),offeredBytes=len(raw),receivedBytes=0,committedObjects=0,
            generationCopy=False,terminalAttempts=claim['attempts']))
    return result


def content_sessions(counts,exports):
    """Every excluded session needs its separately authenticated original offer."""
    offers=exports.get('abandonedGenerationOffers',[])
    need(len(offers)==counts.get('abandonedOfferSessions',0),'joining abandoned offer complete accounting')
    return counts['transferSessions']-counts['rejectedTransferAttempts']-len(offers)
