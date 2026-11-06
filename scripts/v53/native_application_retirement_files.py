"""Original certified-end retirement under a newer installed selector.

Callers must qualify the complete original history first. Neither the capture
sidecar nor the final empty directory supplies this transaction's authority.
"""
from . import native_retirement_evidence as retirement
from . import native_carried_application_evidence as application
from . import native_replay_files as replay
from .native_campaign_files import physical

need=application.need
PREFIXES=('CERTIFICATE_ACTIVE_','NATIVE_RETIREMENT_','STAGED_','SUPERSEDED_','REPLAY_')
KINDS={'application-retirement':PREFIXES}


def transaction(initial):
    need('applied-end' in initial and not any(k in initial for k in
         ('applied-end/retirement.gsat','applied-end/retirement.gsat.next')) and
         not any(k==replay.DIRECTORY or k.startswith(replay.DIRECTORY+'/') for k in initial),
         'application retirement fresh original derived end')
    frames,phases=application.p.data.pending(initial)
    need(phases==('PROOF','CERTIFICATE'),'application retirement original certified phase')
    final=application.retire(initial,frames['ENTRY'],frames['PAYLOAD'])
    marker=retirement.authority(initial);prefixes=[]
    cleaned,events=retirement.staging.cleanup(initial,marker,prefixes=prefixes)
    need(cleaned==final and events and events[0]=='STAGED_RETIREMENT_AUTHORITY_VALIDATED' and
         events==[point for point,_ in prefixes],'application retirement exact derived cleanup')
    # The certificate is forced in place. Typed replay creates and removes only
    # its owned scratch; the old end survives until the retirement marker wins.
    original=physical(initial);kind='application-retirement'
    result=[(kind,point,dict(original)) for point in
            ('CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','NATIVE_RETIREMENT_CERTIFICATE_RETAINED')]
    result.append((kind,prefixes[0][0],physical(prefixes[0][1])))
    result.extend((kind,point,state) for _,point,state in replay.retirement(initial))
    result.extend((kind,point,physical(files)) for point,files in prefixes[1:])
    need(result[-1][1]=='STAGED_RETIREMENT_BEFORE_RETURN' and result[-1][2]==physical(final),
         'application retirement exact final state')
    return result
