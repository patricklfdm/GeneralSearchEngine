"""Current peer confirmations/source retirement for the native restart original.

Explicit model selection, never a fallback after a historical reader failed.
Existing current-node reducers derive all bytes before snapshot comparisons.
"""
import struct
import base64
import json
from collections import defaultdict
from pathlib import Path
import shutil
import tempfile
from . import automatic_restart_evidence as physical
from . import automatic_restart_network as network
from . import node_owner_evidence as owner
from . import node_current_evidence as current
from . import node_current_network as confirmations
from . import node_owner_network as sources
from . import joining_history_run as history


class Service(current.Service):
    # Select ordinary slot publication explicitly; the current-node class also
    # supports interrupted DATA, which this original never admits.
    entry_bytes=owner.Service.entry_bytes
    snapshot=owner.Service.snapshot
    def campaign(self,number,counter):
        # This history has no interrupted client vote to carry. It uses the
        # original cold-node campaign reducer with the current maintenance,
        # original grant retirement, merge and ancestry hooks.
        owner.Service.campaign(self,number,counter)

    def data_documents(self):return [(100,'next-slot')]

    def advance(self,kind):
        self.group=self.maintenance(self.group,self.voters)
        text=b'100:next-slot'
        payload=b'\x01'+struct.pack('>HIII',1,1,4,100)+struct.pack('>I',len(text))+text if kind=='DATA' else None
        self.publish(kind,payload)


def replay_physical(root):return physical.validate(root,service_type=Service)


def unused_source(phase,expected,ballot,lower):
    values=[v for v in phase.sources if v['sender']=='node-1' and v['peer']=='node-3' and v['first']==expected[0][0]]
    network.need(len(values)<=1,'restart current one unused source')
    if values:sources.unused_source(phase,values[0],expected,ballot,lower)
    return len(values)


def rejection_reason(root,events,entries,index):
    # The first real activated contact already raised the unused peer's volatile
    # fence before slot work. It is still not a selected/installed voter. Later
    # slots follow that peer's physically reconstructed ballot-4 grant.
    if index==0:
        begin=next(i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_BEGIN')
        network.need(any(v['kind']=='HEARTBEAT' and v['request']['sender']['node']=='node-1' and
            v['request']['recipient']['node']=='node-3' and v['offered']<begin for v in entries),
            'restart current unused peer contact before slot')
    return 'retention intent installed selection required'


def heartbeats(root,events,entries,boundaries):
    """Consume actual contact replies, never a vote, source, grant or READY.

    This legacy producer records replies rather than every attempted send. No
    synthetic send time or claim of complete attempted-network coverage is made.
    """
    n,c,e,f,need=network.n,network.c,network.e,network.f,network.need
    cuts={node:[(-1,c.current(files)[2]['capsule']['cut'])] for node,files in network.group(root,'before-network').items()}
    installed=[]
    for ordinal,stage in enumerate(('installed-1','published-1','installed-2','published-2','published-3')):
        start,stop=boundaries[ordinal];group=network.group(root,stage)
        selected=f.decode(c.current(group['node-1'])[1]['selected.gsr'],'records','SELECTED')
        installing=stage.startswith('installed')
        if installing:installed.append((stop,selected))
        for source in selected['sources']:
            node=source['voter'];force='INSTALL_SELECTOR_FORCED' if installing else 'PUBLICATION_SELECTOR_FORCED'
            at=[i for i in range(start+1,stop) if events[i]['node']==node and events[i]['event']==force]
            need(len(at)==1,'restart contact exact selector boundary')
            cuts[node].append((at[0],c.current(group[node])[2]['capsule']['cut']))
    def cut(node,at):return max((v for v in cuts[node] if v[0]<at),key=lambda v:v[0])[1]
    samples=defaultdict(list);ignored=set();rows=[]
    for row in entries:
        q=row['request'];at=row['offered']
        if row['kind']!='HEARTBEAT' or q['sender']['node']!='node-1':continue
        previous=[selected for end,selected in installed if end<at]
        need(previous,'restart contact before installation');selected=previous[-1];peer=q['recipient']['node']
        need(peer in ('node-2','node-3') and q['ballot']==selected['ballot'] and q['sequence']==int(peer[-1])-1 and
             q['payload']==dict(cut=cut('node-1',at),activated=True),'restart contact original request cut')
        need(row['answer']=='HEARTBEAT_ACK' and row['response']['payload']==dict(cut=cut(peer,at)),
             'restart contact original response cut')
        samples[q['trace']].append(row);rows.append(row);ignored.add(at);ignored.update(row['deliveries'])
    for trace,values in samples.items():
        requests=defaultdict(list)
        for value in values:requests[value['request']['recipient']['node']].append(value)
        need(all(len(v)<=3 and all(x['row']==v[0]['row'] for x in v) for v in requests.values()),'restart contact exact bounded retries')
        first=min(v['offered'] for v in values);last=max([v['offered'] for v in values]+[at for v in values for at in v['deliveries']])
        need(all(v['request']['payload']==values[0]['request']['payload'] and v['request']['ballot']==values[0]['request']['ballot'] for v in values),
             'restart contact immutable sample')
        need(not any(first<at<=last and v['event']=='ROUND_INSTALLED' for at,v in enumerate(events)),
             'restart contact crosses replacement')
        responding={'node-1'}|{v['request']['recipient']['node'] for v in values if v['deliveries']}
        selected=next(v for end,v in reversed(installed) if end<first)
        need(all(len(responding & set(selected['cut']['view'][side]))>len(selected['cut']['view'][side])//2 for side in ('old','new')),
             'restart contact original responding majority')
    traces=set(samples)
    need(all(v['kind']=='HEARTBEAT' and v['request']['sender']['node']=='node-1' for v in entries if v['request']['trace'] in traces),
         'restart contact trace cannot hide protocol work')
    return dict(samples=len(samples),exchanges=len(rows),contactOnly=True,completeAttemptsQualified=False,_traces=traces,_events=ignored)


def validate(root):
    root=Path(root);unused=[]
    def observed_unused(*args):unused.append(unused_source(*args))
    value=network.validate(root,physical_reader=replay_physical,maintenance_replay=current.maintenance_network,
                           background_replay=heartbeats,unused_source_replay=observed_unused,rejection_reason=rejection_reason)
    events=physical.n.read(root/'events.json');held=[i for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    for start,stop,number in ((-1,held[0],1),(held[2],held[4],2)):
        group=network.group(root,f'installed-{number}')
        selected=physical.f.decode((root/f'selected-{number}.gsr').read_bytes(),'records','SELECTED')
        confirmations.installation_retention(events,start,stop,group,selected)
    # The complete activation reader admits an optional third candidate only
    # in the second campaign. No callback means no such received source.
    network.need(len(unused)<=1,'restart current complete unused-source observations')
    return dict(value,retentionSemantics='original-copy-confirmation',unusedSourcePulls=sum(unused))


# The old fixed capsule-offer boundary is not present in every cancelled pull.
# Replace those two mutations with an exact actual-prefix corruption. Absence
# of an unused pull is legitimate and cannot itself be a negative assertion.
NETWORK_NEGATIVES={k:v for k,v in network.NEGATIVES.items() if k not in ('unused-capsule-offer','missing-unused-offer')}
CURRENT_NEGATIVES={
    'contact-request-cut':'restart contact original request cut',
    'contact-reply-cut':'restart contact original response cut',
    'contact-majority':'restart contact original responding majority',
    'unused-offer-bytes':'node network exact unused source prefix',
    'missing-install-retention':'current node selected retention forces: node-1',
    'missing-first-peer-contact':'restart current unused peer contact before slot',
}
NEGATIVES={**{k:v[1] for k,v in physical.NEGATIVES.items()},**NETWORK_NEGATIVES,**CURRENT_NEGATIVES}
NEGATIVES.update({name:'node owner original selection' for name in ('first-selection','second-selection')})
NEGATIVES['missing-retirement']='current node exact maintenance forces: node-1'


def negative_cases(original):
    count=original.get('unusedSourcePulls')
    network.need(type(count) is int and 0<=count<=1,'restart current derived unused sources')
    cases=dict(NEGATIVES);absent={}
    if count==0:
        del cases['unused-offer-bytes']
        absent['unused-offer-bytes']='Original history contains no unused-source transfer.'
    return cases,absent


def mutate(root,name):
    if name in ('first-selection','second-selection'):
        path=root/('selected-1.gsr' if name=='first-selection' else 'selected-2.gsr')
        value=network.f.decode(path.read_bytes(),'records','SELECTED');value['sources'][0]['basisDigest']='0'*64
        path.write_bytes(network.f.encode('records','SELECTED',value));return
    if name in NETWORK_NEGATIVES:return network.mutate(root,name)
    if name in physical.NEGATIVES:return physical.mutate(root,name)
    network.need(name in CURRENT_NEGATIVES,'restart current unknown negative')
    rows=network.n.read(root/'wire.json');events=network.n.read(root/'events.json');f=network.f;e=network.e
    decoded=[(row,*[network.n.transfer.t.wire(row[k]) for k in ('request','response')]) for row in rows]
    contacts=[v for v in decoded if v[1][0]=='HEARTBEAT' and v[1][1]['sender']['node']=='node-1']
    def hashes(row):return tuple(e.digest(base64.b64decode(row[k],validate=True)) for k in ('request','response'))
    def rewrite(value,change):
        row,(kind,q),(answer,z)=value;old_q,old_z=hashes(row);change(q,z)
        raw_q=f.encode('wire',kind,q);raw_z=f.encode('wire',answer,z)
        for other in rows:
            if hashes(other)==(old_q,old_z):other.update(request=base64.b64encode(raw_q).decode(),response=base64.b64encode(raw_z).decode())
        for event in events:
            if event['event']=='WIRE_RESPONSE' and event['request']==old_q and event['response']==old_z:
                event.update(request=e.digest(raw_q),response=e.digest(raw_z))
            elif event['event']=='NETWORK_RECEIVED' and event['response']==old_z:event['response']=e.digest(raw_z)
    if name in ('contact-request-cut','contact-reply-cut'):
        rewrite(contacts[0],lambda q,z:(q if name=='contact-request-cut' else z)['payload']['cut'].update(index=99))
    elif name=='contact-majority':
        trace=contacts[0][1][1]['trace'];responses={hashes(row)[1] for row,(_,q),_ in contacts if q['trace']==trace}
        events[:]=[v for v in events if not(v['event']=='NETWORK_RECEIVED' and v['response'] in responses)]
    elif name=='unused-offer-bytes':
        value=next(v for v in decoded if v[1][0]=='CHUNK' and v[1][1]['recipient']['node']=='node-3' and v[2][0]=='SOURCE_OFFER')
        rewrite(value,lambda q,z:z['payload'].update(digest='0'*64))
    elif name=='missing-install-retention':
        events.remove(next(v for v in events if v['node']=='node-1' and v['event']=='SELECTED_RETENTION_COMPLETED'))
    elif name=='missing-first-peer-contact':
        trace=contacts[0][1][1]['trace']
        for row,(_,q),_ in contacts:
            if q['trace']!=trace or q['recipient']['node']!='node-3':continue
            qh,zh=hashes(row);rows.remove(row)
            events[:]=[v for v in events if not(v['event']=='WIRE_RESPONSE' and v['request']==qh and v['response']==zh)
                       and not(v['event']=='NETWORK_RECEIVED' and v['response']==zh)]
    (root/'wire.json').write_bytes(f.canonical(rows));(root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);before=history.inventory(root);original=validate(root);negatives=[]
    cases,absent=negative_cases(original)
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-current-restart-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);mutate(path,name)
            try:validate(path)
            except ValueError as error:network.need(str(error)==reason,'restart current unrelated negative '+name+': '+str(error))
            else:raise ValueError('restart current accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(negatives),total=len(cases))),flush=True)
    network.need(history.inventory(root)==before,'restart current original changed')
    return dict(original=original,negatives=negatives,notApplicable=absent)
