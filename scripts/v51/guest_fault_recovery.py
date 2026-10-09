"""Closed, offline guest actions for retained crashes, transfer and capacity."""
import base64
import re
import threading
import time
from . import performance_model as m, remote_command as c, public_trace

CASES = ('interrupted-transfer', 'entry-chosen', 'proof-quorum', 'group-restart', 'minority-capacity')
CUTS = {'entry-chosen':'ACCEPT_ACK_RECEIVED', 'proof-quorum':'PROOF_ACK_RECEIVED',
        'interrupted-transfer':'STORAGE_CUT:TRANSFER_PROGRESS_BEFORE_ACK'}
NODES = ('node-1','node-2','node-3')
# Withhold mutation/recovery traffic, not the heartbeat that keeps a lagging
# recipient a follower during slow SSH control exchanges.
DATA_BLOCKED_TYPES = ('PREPARE','BASIS_CHUNK','SELECTED_OFFER','ACCEPT','COMMIT_PROOF',
    'COMMIT_ADVANCE','SNAPSHOT_OFFER','SNAPSHOT_CHUNK','REJOIN_INSTALL','SNAPSHOT_ABORT','SOURCE_OFFER','SOURCE_CHUNK')


def isolation_rules(case, node):
    m.need(case in ('interrupted-transfer','minority-capacity'),'recovery data isolation scope')
    return [f'{a} {b} BEFORE_REQUEST_WRITE {kind}' for a in NODES for b in NODES
            if a!=b and node in (a,b) for kind in DATA_BLOCKED_TYPES]


def heartbeat_frame(row):
    if row is None:return None
    request=m.strict_json(base64.b64decode(row['request'],validate=True)[48:])
    response=m.strict_json(base64.b64decode(row['frame'],validate=True)[48:])
    return request if request['type']=='HEARTBEAT' and response['type']=='HEARTBEAT_ACK' else None


def documents(tag, size):
    return [dict(id=tag+i,value=(f'tag-{tag+i}-'+'x'*size)[:size]) for i in (0,1)]


def bulk_allowed(case, docs):
    if type(docs) is not list or len(docs)!=2:return False
    ordinary=all(type(d) is dict and set(d)=={'id','value'} and type(d['id']) is int and
                 type(d['value']) is str and len(d['value'].encode())==64 for d in docs)
    size={'interrupted-transfer':4096,'minority-capacity':20000}.get(case)
    return ordinary or size is not None and docs in [documents(tag,size) for tag in ((40,60) if case=='minority-capacity' else (40,))]


class Controls:
    def __init__(self, handler):
        self.h=handler;self.pending=None;self.armed=False;self.direction=False;self.direction_healed=False;self.direction_timer=None

    def before_kill(self):
        h=self.h
        rows=public_trace.live_rows(h.s.cell,h.s.node)
        m.need(self.armed and any(v['event']=='CUT_REACHED' and v['cut']==CUTS[h.case] and v['mode']=='kill' and
               v['pid']==h.s.jvm.identity['pid'] for v in rows) and
               (h.case=='interrupted-transfer' or self.pending is not None),'recovery SIGKILL before original cut')

    def release_direction(self, watchdog=False):
        h=self.h
        with h.lock:
            if not self.direction or self.direction_healed:return
            h.rules([]);self.direction_healed=True
            self.direction_record.update(healedNanos=time.monotonic_ns(),watchdog=watchdog)
            c.write_once(h.s.cell/'prepare-isolation.json',self.direction_record)
            if self.direction_timer is not None:self.direction_timer.cancel()

    def handle(self, payload):
        h=self.h;s=h.s;root=s.cell;action=payload.get('action')
        from . import native_preset_timing as full, native_experiment_timing as timing
        native=full.fault_configuration(s.config,CASES)
        if action=='prepare-direction':
            m.need(payload=={'action':action} and h.case=='minority-capacity' and h.generation==0 and
                   s.jvm is None and not self.direction,'bounded PREPARE direction consumed/scope')
            c.write_once(root/'prepare-direction-claim.json',payload);self.direction=True
            rules=[f'{a} {b} BEFORE_REQUEST_WRITE PREPARE' for a in NODES for b in NODES if a!=b and 'node-3' in (a,b)]
            h.rules(rules);self.direction_record=dict(appliedNanos=time.monotonic_ns(),rules=rules)
            self.direction_timer=threading.Timer(timing.CONTROLS['isolation'] if native else 60,lambda:self.release_direction(True))
            self.direction_timer.daemon=True;self.direction_timer.start();return dict(self.direction_record)
        m.need(s.jvm is not None and not s.jvm.closed,'recovery live voter required')
        if action=='heal-direction':
            m.need(payload=={'action':action} and h.case=='minority-capacity' and self.direction,'bounded PREPARE heal scope')
            self.release_direction();return c.read(root/'prepare-isolation.json')
        if action=='arm-cut':
            m.need(payload=={'action':action} and h.case in CUTS and not self.armed and h.generation==1,'fault cut consumed/scope')
            c.write_once(root/'cut-claim.json',payload);self.armed=True
            with (root/(s.node+'-arm.txt')).open('x') as out:out.write(CUTS[h.case]+'\nkill\n')
            return dict(cut=CUTS[h.case],identity=s.jvm.identity)
        if action=='start-target':
            m.need(set(payload)=={'action','intentId'} and h.case in ('entry-chosen','proof-quorum') and self.armed and self.pending is None and
                   type(payload['intentId']) is str and re.fullmatch('call-(0[1-9]|1[0-9]|2[0-4])',payload['intentId']), 'target mutation consumed/scope')
            c.write_once(root/'target-claim.json',payload)
            self.pending=s.jvm.submit('addAll',intentId=payload['intentId'],documents=documents(40,512))
            return dict(identity=s.jvm.identity,request=self.pending[0]['request'])
        if action=='observe-recovery':
            m.need(payload=={'action':action},'recovery observation scope')
            rows=public_trace.live_rows(root,s.node)
            own=[v for v in rows if v['pid']==s.jvm.identity['pid']]
            rejection=next((v for v in own if v['event']=='RESOURCE_REJECTED'),None)
            replies=[v for v in own if rejection and v['event']=='REPLY' and v['order']>rejection['order']]
            def capacity(v):
                frame=m.strict_json(base64.b64decode(v['frame'],validate=True)[48:])
                return frame['type']=='REJECT' and frame['payload'].get('reason')=='CAPACITY_EXCEEDED'
            return dict(selected=next((v for v in reversed(own) if v['event']=='PROMISE_QUORUM'),None),
                floor=next((v for v in reversed(own) if v['event']=='RECOVERY_FLOOR'),None),
                campaign=next((v for v in reversed(own) if v['event']=='CAMPAIGN_BEGIN'),None),
                heartbeat=next((v for v in reversed(own) if v['event']=='REPLY' and heartbeat_frame(v)),None),
                cut=next((v for v in own if v['event']=='CUT_REACHED'),None),rejection=rejection,
                capacityReply=next((v for v in replies if capacity(v)),None))
        if action=='isolate':
            m.need(set(payload)=={'action','node'} and payload['node'] in NODES and h.case in ('interrupted-transfer','minority-capacity') and
                   not h.isolated and (h.case!='minority-capacity' or self.direction_healed and payload['node']=='node-3'),'recovery isolation consumed/scope')
            c.write_once(root/'network-injection-claim.json',payload)
            with h.lock:
                h.isolated=True;rules=isolation_rules(h.case,payload['node'])
                h.rules(rules);h.isolation=dict(appliedNanos=time.monotonic_ns(),rules=rules,node=payload['node'])
                h.timer=threading.Timer(timing.CONTROLS['isolation'] if native else 60,lambda:h.heal(True));h.timer.daemon=True;h.timer.start();return dict(h.isolation)
        if action=='heal':
            m.need(payload=={'action':action} and h.isolated,'recovery heal scope');h.heal();return c.read(root/'isolation.json')
        raise ValueError('unsupported recovery fault action')
