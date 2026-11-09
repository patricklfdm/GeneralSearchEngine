"""Original healthy ADD: discovery and complete-copy floor lifetimes.

The complete original physical/network/export/control reader runs first. A
STATUS is only a hint. Floor witnesses are independently derived generation
bytes acquired by actual transfers, or the two explicitly identified in-process
fixture calls. This reader does not turn those direct calls into network work.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_control_evidence as control

c=control; e=c.e; n=c.n; f=c.f; disk=c.disk; need=c.need; sha=c.sha


def floor_events(copies,local,network,*,pinned=False):
    """Derive exact force and release counts from complete original members."""
    need(type(pinned) is bool and (not pinned or local in copies),'joining maintenance pinned local copy')
    ordered=sorted((v for node,v in copies.items() if not pinned or node!=local),
                   key=lambda v:((v['node']==local) if network else False,sha(v['manifest'])))
    names=['FLOOR_RESERVED','FLOOR_DIRECTORY_CREATED','FLOOR_PROPOSAL_WRITTEN','FLOOR_PROPOSAL_FORCED']
    if pinned:names[2:2]=['FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN',
                          'FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED']
    for own in ordered:
        names+=['FLOOR_COPY_CREATED','FLOOR_MANIFEST_WRITTEN','FLOOR_MANIFEST_FORCED']
        for member in sorted(own['members']):
            kind='IMAGE' if member.endswith('.image') else 'MEMBER'
            names+=['FLOOR_'+kind+'_WRITTEN','FLOOR_'+kind+'_FORCED']
        names+=['FLOOR_COPY_DIRECTORY_FORCED']
        if network:names+=['FLOOR_COPY_HANDED_OFF']
    names+=['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_WRITTEN','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
            'FLOOR_RELEASE_AUTHORITY_CREATED','FLOOR_RELEASE_AUTHORITY_WRITTEN','FLOOR_RELEASE_AUTHORITY_FORCED',
            'FLOOR_RELEASE_PARENT_FORCED','FLOOR_RELEASE_RELINQUISHED']
    names+=['FLOOR_RELEASE_FILE_DELETED']*sum(len(v['members'])+1 for v in ordered)
    names+=['FLOOR_RELEASE_COPY_DELETED']*len(ordered)
    names+=['FLOOR_RELEASE_PROPOSAL_CLEARED']
    if pinned:names+=['FLOOR_RELEASE_LOCAL_CLEARED']
    names+=['FLOOR_RELEASE_AUTHORITY_CLEARED','FLOOR_RELEASE_CLEARED','FLOOR_RELEASE_BEFORE_RETURN']
    return names


def same_cut(copies,own):
    cap=own['packet']['capsule'];identities=n.s.catalog.identities(c.catalog(own)['identities'])
    need(own['node'] in copies and copies[own['node']]==own,'joining maintenance original local copy')
    for node,copy in copies.items():
        other=copy['packet']['capsule']
        need(copy['identity']==identities.get(node) and other['root']==cap['root'] and disk.anchor(other)==disk.anchor(cap),
             'joining maintenance exact governing copies')
    n.s.catalog.majority(cap['cut']['view'],sorted(copies))
    view=cap['cut']['view']
    if view['operation'] is not None:
        need((set(view['new'])-set(view['old']))<=copies.keys(),'joining maintenance missing original joining copy')


def retirement_order(events,node,start,end,scope):
    rows=[(at,v) for at,v in enumerate(events) if start<=at<=end and v.get('node')==node]
    points={name:[at for at,v in rows if v['event']==name] for name in
            ('FLOOR_BEFORE_RETURN','FLOOR_RELEASE_AUTHORITY_CREATED','RETIREMENT_RESERVED','RETIREMENT_AUTHORITY_FORCED',
             'RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_BEFORE_RETURN')}
    floor=points['FLOOR_BEFORE_RETURN'];release=points['FLOOR_RELEASE_AUTHORITY_CREATED']
    need(len(floor)==len(release)==1 and floor[0]<release[0],'joining maintenance floor authority interval')
    if points['RETIREMENT_RESERVED']:
        chain=[points[k] for k in ('RETIREMENT_RESERVED','RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED',
                                   'RETIREMENT_DELETE_VALIDATED','RETIREMENT_BEFORE_RETURN')]
        need(all(len(v)==1 for v in chain) and floor[0]<chain[0][0] and
             all(a[0]<b[0] for a,b in zip(chain,chain[1:])) and chain[-1][0]<release[0],
             'joining maintenance generation retirement lifetime')
    for at,row in rows:
        if row['event'].startswith(('RETIREMENT_','SOURCE_RETIREMENT_')):
            observed_scope=row.get('scope')
            if row['event']==n.physical.observed.EVENT and observed_scope=='network-owner':observed_scope=None
            need(floor[0]<at<release[0] and observed_scope==scope,'joining maintenance retirement outside floor')
    return len(points['RETIREMENT_RESERVED'])


class Replay(c.Replay):
    expected_status_count=55
    expected_floor_counts=(38,2,96,52)
    joining_status_scopes={'continuation-endpoint':'continuation-owner'}

    def governing(self,copies,own):same_cut(copies,own)

    def expected_events(self,copies,own,network,start,end):
        return floor_events(copies,own['node'],network)

    def discovery(self,statuses,packet,q,remote):
        need(len(statuses)==1,'joining maintenance acquisition before discovery')
        row=statuses[0]
        need(row['delivered']<packet[0]['offer']['sent'] and row['response']['payload']['cut']==remote['packet']['capsule']['cut'] and
             row['request']['view']==q['view'] and row['request']['ballot']==q['ballot'],
             'joining maintenance acquisition before discovery')
        return row

    def statuses(self):
        self.status_rows=[]
        for row in self.rows:
            if row['kind']!='STATUS_PROBE':continue
            q,a=row['request'],row['response'];own=self.current(q['recipient']['node'],row['received'],row['offered'])
            ids=n.s.catalog.identities(c.catalog(own)['identities']);proposer=ids.get(q['ballot']['proposer'])
            need(q['sequence']==1 and set(q['payload'])=={'nonce'} and q['sender']==ids.get(q['sender']['node']) and
                 proposer is not None and q['ballot']['incarnation']==proposer['storage'],
                 'joining maintenance discovery original identity')
            need(row['answer']=='STATUS' and a['payload']==dict(nonce=q['payload']['nonce'],cut=own['packet']['capsule']['cut'],ready=False),
                 'joining maintenance exact discovery hint')
            # Historical correlation does not become the responder's current
            # view/ballot, a new PROMISE, READY or a retained-copy observation.
            if own['node']==self.model.joining:
                scope=self.joining_status_scopes.get(self.events[row['received']].get('scope'))
                need(scope is not None,'joining maintenance discovery endpoint')
                c.owner_lifetime(self.events,self.model.joining,scope,row['received'],row['offered'])
            self.status_rows.append(row)
        if self.expected_status_count is not None:
            need(len(self.status_rows)==self.expected_status_count,'joining maintenance complete discovery observations')

    def acquired(self,own,lower,start):
        node=own['node'];copies={node:own};used=[]
        for values in self.groups:
            first,last=values[0]['offer'],values[-1]['commit'];q=first['request'];peer=q['recipient']['node']
            if 'abortedPrefix' in first or 'abortedPreparation' in first:continue
            if q['sender']['node']!=node or not lower<first['sent']<start:continue
            remote=self.current(peer,first['received'],last['offered'])
            reference=e.native.current_reference(remote['packet']['capsule'],'retained-current-generation-metadata')
            if q['payload']['digest']!=reference:continue
            need(peer not in copies,'joining maintenance duplicate acquired copy')
            need(last['delivered']<start,'joining maintenance copy delivered after floor')
            packets=[v for v in self.groups if v[0]['offer']['request']['sender']==q['sender'] and
                     v[0]['offer']['request']['recipient']==q['recipient'] and lower<v[0]['offer']['sent'] and
                     v[-1]['commit']['delivered']<first['sent'] and v[0]['offer']['request']['payload']['digest']==
                     e.native.current_reference(remote['packet']['capsule'],'retained-current-packet')]
            need(len(packets)==1,'joining maintenance complete packet acquisition');packet=packets[0]
            need(len(packet)==1 and packet[0]['raw']==remote['members']['source.gscp'] and
                 packet[0]['offer']['request']['view']==q['view'] and packet[0]['offer']['request']['ballot']==q['ballot'],
                 'joining maintenance original packet correlation')
            statuses=[v for v in self.status_rows if v['request']['sender']==q['sender'] and v['request']['recipient']==q['recipient'] and
                      lower<v['sent']<packet[0]['offer']['sent']]
            discovery=self.discovery(statuses,packet,q,remote)
            # Packet-only transfer borrows actual local image bytes. The
            # matching terminal application hash alone cannot create an image.
            for digest,size in remote['packet']['images'].items():
                raw=own['members'].get(digest+'.image')
                need(raw is not None and len(raw)==size and sha(raw)==digest,'joining maintenance missing borrowed original image')
            e.authorize_generation(values,self.windows);copies[peer]=remote;used.append(discovery['requestHash'])
        need(len(copies)>1,'joining maintenance absent acquired copies')
        return copies,used

    def direct(self,own,start):
        """The fixture explicitly hands three live copies to two old owners."""
        cap=own['packet']['capsule'];node=own['node']
        need(node in ('node-1','node-2') and cap['cut']==self.model.states[9]['cut'],
             'joining maintenance direct fixture boundary')
        initialized=[i for i,v in enumerate(self.events) if v.get('node')=='node-4' and v.get('scope')=='initial-owner' and
                     v['event']=='CURRENT_DIRECTORY_FORCED']
        need(len(initialized)==1,'joining maintenance direct joining owner')
        copies={}
        for peer in ('node-1','node-2','node-4'):
            points=[i for i,v in enumerate(self.events) if initialized[0]<i<start and v.get('node')==peer and v['event']=='FLOOR_COPY_BEFORE_RETURN']
            need(points,'joining maintenance direct original copy missing')
            copy=self.current(peer,points[0],start)
            if peer=='node-4':c.owner_lifetime(self.events,peer,'initial-owner',points[0],start)
            copies[peer]=copy
        return copies

    def floors(self):
        positions=[i for i,v in enumerate(self.events) if v['event']=='FLOOR_RESERVED'];previous={};used=set()
        network=direct=copies_total=generations=0;covered=set()
        for start in positions:
            node=self.events[start]['node'];scope=self.events[start].get('scope')
            ends=[i for i,v in enumerate(self.events) if i>start and v.get('node')==node and v['event']=='FLOOR_RELEASE_BEFORE_RETURN']
            need(ends,'joining maintenance incomplete floor release');end=ends[0]
            own=self.current(node,start,end);lower=max(own['start'],previous.get(node,-1))
            need(lower<start,'joining maintenance overlapping floors')
            actual=[(i,v) for i,v in enumerate(self.events) if start<=i<=end and v.get('node')==node and
                    v['event'].startswith('FLOOR_') and v['event']!='FLOOR_COPY_BEFORE_RETURN']
            is_network=any(v['event']=='FLOOR_COPY_HANDED_OFF' for _,v in actual)
            if is_network:
                copies,new=self.acquired(own,lower,start)
                need(not used.intersection(new),'joining maintenance discovery reused by floor');used.update(new);network+=1
            else:copies=self.direct(own,start);direct+=1
            self.governing(copies,own)
            need([v['event'] for _,v in actual]==self.expected_events(copies,own,is_network,start,end) and all(v.get('scope')==scope for _,v in actual),
                 'joining maintenance exact copy force/release order')
            if node==self.model.joining:c.owner_lifetime(self.events,node,'continuation-owner',start,end)
            generations+=retirement_order(self.events,node,start,end,scope)
            covered.update(i for i,_ in actual);copies_total+=len(copies);previous[node]=end
        eligible={i for i,v in enumerate(self.events) if v['event'].startswith('FLOOR_') and v['event']!='FLOOR_COPY_BEFORE_RETURN'}
        need(covered==eligible,'joining maintenance unbound floor events')
        if self.expected_floor_counts is not None:
            need((network,direct,copies_total,len(used))==self.expected_floor_counts,'joining maintenance complete original floors')
        return dict(networkFloors=network,directFixtureFloors=direct,completeCopies=copies_total,acquiredRemoteCopies=len(used),
                    retiredGenerations=generations,floorEvents=len(covered))

    def run(self):
        self.statuses();result=self.floors()
        return dict(status='PASS',scope='one-native-'+self.kind+'-discovery-and-complete-copy-floor-lifetimes',**result,
                    discoveryHints=len(self.status_rows),maintenanceForceQualified=True,phase3Complete=False,
                    completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False)


def replay(root):return Replay(root).run()


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root);c.validate(root);result=replay(root)
    need(n.s.collection.inventory(root)==before,'joining maintenance original changed');return result


NEGATIVES={
    'status-cut':'joining maintenance exact discovery hint',
    'status-ready':'joining maintenance exact discovery hint',
    'status-nonce':'joining maintenance exact discovery hint',
    'discovery-after-packet':'joining maintenance acquisition before discovery',
    'copy-after-reservation':'joining maintenance copy delivered after floor',
    'manifest-force':'joining maintenance exact copy force/release order',
    'handoff-before-directory':'joining maintenance exact copy force/release order',
    'authority-before-copies':'joining maintenance exact copy force/release order',
    'release-before-force':'joining maintenance exact copy force/release order',
    'release-member-count':'joining maintenance exact copy force/release order',
    'retirement-before-floor':'joining maintenance generation retirement lifetime',
    'retirement-after-release':'joining maintenance generation retirement lifetime',
    'direct-copy-missing':'joining maintenance direct original copy missing',
    'unbound-floor':'joining maintenance unbound floor events',
}


def mutate(root,name,*,reader=None):
    root=Path(root);reader=Replay(root) if reader is None else reader;events=reader.events
    if name.startswith('status-'):
        wires=json.loads((root/'wire.json').read_bytes());row=next(v for v in wires if n.wire(v['request'])[0]=='STATUS_PROBE')
        old=sha(base64.b64decode(row['response']));kind,body=n.wire(row['response'])
        if name=='status-cut':body['payload']['cut']['entry']='f'*64
        elif name=='status-ready':body['payload']['ready']=True
        else:body['payload']['nonce']='00000000-0000-0000-0000-000000000001'
        raw=f.encode('wire',kind,body);row['response']=c.encoded(raw)
        for event in events:
            if event.get('response')==old:event['response']=sha(raw)
        (root/'wire.json').write_bytes(f.canonical(wires))
    else:
        def event(point,node='node-1'):return next(v for v in events if v.get('node')==node and v['event']==point)
        def move(value,target,after=False):
            events.remove(value);events.insert(events.index(target)+int(after),value)
        if name=='discovery-after-packet':
            row=next(v for v in reader.rows if v['kind']=='STATUS_PROBE')
            delivery=events[row['delivered']];target=next(v for v in reader.groups if v[0]['offer']['sent']>row['delivered'])[0]['offer']
            move(delivery,events[target['sent']],True)
        elif name=='copy-after-reservation':
            start=events.index(event('FLOOR_RESERVED'));last=max(v[-1]['commit']['delivered'] for v in reader.groups if v[-1]['commit']['delivered']<start)
            move(events[last],events[start],True)
        elif name=='manifest-force':event('FLOOR_MANIFEST_FORCED')['event']='REMOVED_MANIFEST_FORCE'
        elif name=='handoff-before-directory':move(event('FLOOR_COPY_HANDED_OFF'),event('FLOOR_COPY_DIRECTORY_FORCED'))
        elif name=='authority-before-copies':move(event('FLOOR_AUTHORITY_FORCED'),event('FLOOR_COPIES_FORCED'))
        elif name=='release-before-force':move(event('FLOOR_RELEASE_RELINQUISHED'),event('FLOOR_RELEASE_AUTHORITY_FORCED'))
        elif name=='release-member-count':event('FLOOR_RELEASE_FILE_DELETED')['event']='REMOVED_RELEASE_DELETION'
        elif name=='retirement-before-floor':move(event('RETIREMENT_RESERVED'),event('FLOOR_BEFORE_RETURN'))
        elif name=='retirement-after-release':move(event('RETIREMENT_BEFORE_RETURN'),event('FLOOR_RELEASE_RELINQUISHED'),True)
        elif name=='direct-copy-missing':event('FLOOR_COPY_BEFORE_RETURN',reader.model.joining)['event']='REMOVED_DIRECT_COPY'
        else:events.append(dict(node='node-1',event='FLOOR_MANIFEST_FORCED'))
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root,progress=None):
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root);outcomes=[]
    if progress:progress(dict(stage='original',status='PASS'))
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-maintenance-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=n.s.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and after['directories']==before['directories'],
                 'joining maintenance negative changed physical inputs')
            n.network(changed);prior=e.replay(changed);c.replay(changed,prior)
            try:replay(changed)
            except ValueError as error:need(str(error)==reason,'joining unrelated maintenance negative: '+name+': '+str(error))
            else:raise ValueError('joining maintenance mutation accepted: '+name)
        result=dict(case=name,status='REJECTED',networkExportControlPrecondition='PASS',reason=reason);outcomes.append(result)
        if progress:progress(result)
    need(n.s.collection.inventory(root)==before,'joining maintenance negative changed original')
    return dict(original=original,negatives=outcomes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    result=qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result,sort_keys=True))
