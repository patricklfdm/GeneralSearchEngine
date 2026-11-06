"""Exact vote replacement prefixes; expected bytes come from original authority.

The enclosing reader must validate the original protocol/history first. This
model neither treats a write as a force nor invents post-crash observations.
"""
import struct
from . import pending_accept_evidence as accept
from .native_campaign_files import physical
from .membership_model import need

PHASES=('ACCEPT','PROOF','CERTIFICATE')
SUFFIXES=('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
          'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED','BEFORE_RETURN')
POINTS={phase+'_'+suffix:phase.lower() for phase in PHASES for suffix in SUFFIXES}
ACTIVE=accept.ACTIVE
NEXT=accept.NEXT


def phase_bytes(frames,phase):
    """Project a phase from independently validated original complete frames."""
    need(phase in PHASES,'vote prefix phase')
    raw=accept.container([frames[key] for key in ('SELECTOR','PROMISE','SELECTED','ENTRY','ACCEPT')],frames['PAYLOAD'])
    raw+=b''.join(frames[key] for key in PHASES[1:PHASES.index(phase)+1])
    return raw[:8]+struct.pack('>I',len(raw))+raw[12:]


def transaction(initial,raw,phase,*,renamed=False):
    """Full replica states for a new exact candidate, optionally cut at rename."""
    need(phase in PHASES and type(renamed) is bool,'vote prefix phase/cut')
    need(ACTIVE in initial and NEXT not in initial and type(raw) is bytes and len(raw)>=12,
         'vote prefix original active/candidate')
    state=dict(initial);steps=[]
    for suffix in SUFFIXES[:7] if renamed else SUFFIXES:
        if suffix=='CANDIDATE_CREATED':state[NEXT]=b''
        elif suffix=='PREFIX_WRITTEN':state[NEXT]=raw[:len(raw)//2]
        elif suffix=='CANDIDATE_WRITTEN':state[NEXT]=raw
        elif suffix=='RENAMED':state[ACTIVE]=state.pop(NEXT)
        steps.append((phase.lower(),phase+'_'+suffix,physical(state)))
    return steps
