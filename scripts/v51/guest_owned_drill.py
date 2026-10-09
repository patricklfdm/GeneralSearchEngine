"""All twelve owned fault cells under one offline source/package/lease binding."""
import base64
from . import guest_owned_faults as faults, guest_owned_network as network
from . import performance_model as m, format_inspector as f, remote_faults
from . import guest_fault_recovery as recovery, native_experiment_timing as timing

MODE='failure-drill-faults'
SCOPE='owned-complete-failure-drill'
CASES=remote_faults.CASES


class Cell(network.Cell):
    def command(self, peer, action, **values):
        return self.succeeded(self.member(peer),'fault',dict(action=action,**values),self.end)['result']

    def observe(self, node):return self.command(node,'observe-recovery')

    def start_group(self):
        if self.case!='minority-capacity':return super().start_group()
        self.parallel(lambda member:self.command('node-'+str(member[0]),'prepare-direction'))
        self.parallel(self.start,self.clients[:2])
        leader=self.leader(min(self.end,self.clock()+timing.control(self.services.provider.req,'activation',30)),exclude=('node-3',))
        self.start(self.member('node-3'))
        self.parallel(lambda member:self.command('node-'+str(member[0]),'heal-direction'))
        def stable():
            a,b=self.status(leader),self.status('node-3')
            return a['state']=='LEADER_READY' and b['state']=='FOLLOWER' and a['epoch']==b['epoch']
        self.wait(stable,min(self.end,self.clock()+timing.control(self.services.provider.req,'activation',30)),'owned bounded voter initial fencing')
        return leader

    def status(self, node, deadline=None):
        if self.case!='minority-capacity' or node!='node-3':return super().status(node,deadline)
        value=self.succeeded(self.member(node),'fault',dict(action='status'),deadline or self.end)['result']['response']
        m.need(value['outcome']=='SUCCESS','bounded voter diagnostic unavailable');return value

    def after_seed(self, leader):
        if self.case not in recovery.CASES:return
        through=self.status(leader)['provenIndex'];self.record['seedThrough']=through
        for node in self.running:self.rejoin(node,through)
        self.record['seedRejoins']=self.record['rejoins'];self.record['rejoins']=[]

    def retained_stop(self, node):
        m.need(node not in self.stopped,'owned retained stop consumed');self.stopped.add(node)
        return self.succeeded(self.member(node),'stop-voter',dict(forced=False,retain=True),self.end)['result']

    def source(self, leader, through, deadline):
        def floor():
            observed=self.observe(leader)['floor']
            return observed if observed and observed['index']>=through else None
        return self.wait(floor,deadline,'owned exportable recovery source')

    def partition(self, node, action):
        self.event('recovery-'+action,node=node)
        if action=='heal':
            # Rules act at the sender. Release the recipient first, then permit
            # senders to deliver the armed chunk; guest-clock heal precedes cut.
            result={node:self.command(node,action)}
            result.update(self.parallel(lambda member:('node-'+str(member[0]),self.command('node-'+str(member[0]),action)),
                                        [member for member in self.clients if member!=self.member(node)]))
            return result
        return dict(self.parallel(lambda member:('node-'+str(member[0]),
            self.command('node-'+str(member[0]),action,**(dict(node=node) if action=='isolate' else {})))))

    def recipient_observation(self, node):
        value=self.observe(node)
        self.record['recipientLastObservation']={k:value[k] for k in ('campaign','heartbeat','cut')}
        m.need(value['campaign']==self.record['recipientCampaign'],
               'owned recovery recipient started a campaign before intended fault: '+node)
        return value

    def recipient_heartbeat(self, node, old, through, applied, deadline):
        def received():
            row=self.recipient_observation(node)['heartbeat'];frame=recovery.heartbeat_frame(row)
            return row if frame and row['localNanos']>applied and frame['sender']==old and frame['recipient']==node and \
                frame['payload']['activated'] and frame['payload']['provenIndex']>=through else None
        self.record['recipientHeartbeat']=self.wait(received,deadline,'owned recovery recipient heartbeat missing')

    def cut(self, node, deadline):
        observe=self.recipient_observation if self.case=='interrupted-transfer' else self.observe
        self.record['cut']=self.wait(lambda:observe(node)['cut'],deadline,'owned original durable cut missing')
        m.need(self.record['cut']['cut']==recovery.CUTS[self.case],'owned wrong crash cut')

    def start_target(self, node):
        m.need(len(self.history)<24,'owned fault operation cap');intent=f'call-{len(self.history)+1:02d}'
        record=dict(kind='addAll',intentId=intent,node=node,startNanos=int(self.clock()*1e9),endNanos=None,
                    outcome='PENDING',documents=recovery.documents(40,512));self.history.append(record)
        result=self.command(node,'start-target',intentId=intent)
        record.update(opId=result['request']['opId'],pid=result['identity']['pid'],generation=result['identity']['generation'])
        return record

    def extra_scenario(self, old, deadline):
        if self.case not in recovery.CASES:return False
        case=self.case
        if case in ('entry-chosen','proof-quorum'):
            self.command(old,'arm-cut');pending=self.start_target(old);self.cut(old,deadline)
            self.stop_node(old,True);pending['disconnectNanos']=int(self.clock()*1e9)
            active=self.progress(deadline);through=self.status(active)['provenIndex']
            self.start(self.member(old),True);self.rejoin(old,through)
        elif case=='group-restart':
            self.parallel(lambda member:self.retained_stop('node-'+str(member[0])))
            self.event('group-stopped');self.parallel(lambda member:self.start(member,True))
            active=self.progress(deadline);through=self.status(active)['provenIndex']
            for node in self.running:self.rejoin(node,through)
        elif case=='interrupted-transfer':
            selected=self.observe(old)['selected'];m.need(selected is not None,'owned transfer selected source pair')
            pair={b['node'] for b in f.inspect(base64.b64decode(selected['selected'],validate=True),'SELECTED')['bases']}
            target=next(n for n in self.running if n not in pair);self.record.update(selected=selected,targetNode=target)
            self.record['recipientCampaign']=self.observe(target)['campaign']
            isolation=self.partition(target,'isolate')
            m.need(self.call(old,'addAll',documents=recovery.documents(40,4096))['outcome']=='SUCCESS','owned transfer seed failed')
            through=self.status(old)['provenIndex'];self.record['sourceFloor']=self.source(old,through,deadline)
            self.recipient_heartbeat(target,old,through,isolation[target]['appliedNanos'],deadline)
            self.command(target,'arm-cut');self.partition(target,'heal');self.cut(target,deadline)
            self.stop_node(target,True);self.start(self.member(target),True);self.rejoin(target,through)
            self.record['transferRejoin']=self.record['rejoins'].pop()
            active=self.progress(deadline);self.rejoin(target,self.status(active)['provenIndex'])
        else:
            self.record['recipientCampaign']=self.observe('node-3')['campaign']
            isolation=self.partition('node-3','isolate')
            for tag in (40,60):m.need(self.call(old,'addAll',documents=recovery.documents(tag,20000))['outcome']=='SUCCESS','owned capacity target failed')
            through=self.status(old)['provenIndex'];self.record['sourceFloor']=self.source(old,through,deadline)
            self.recipient_heartbeat('node-3',old,through,isolation['node-3']['appliedNanos'],deadline)
            self.partition('node-3','heal')
            def rejected():
                value=self.recipient_observation('node-3')
                return value if value['rejection'] and value['capacityReply'] else None
            observed=self.wait(rejected,deadline,'owned real capacity rejection/reply missing');self.record['rejection']=observed['rejection']
            self.command('node-3','status',boundary='resource-rejected')
            self.record['refusals']=[self.call('node-3','addAll',documents=remote_faults.documents(90)),self.call('node-3','read')]
            m.need(all(r['outcome']!='SUCCESS' for r in self.record['refusals']),'bounded voter served public call')
            active=self.progress(deadline,exclude=('node-3',))
            self.retained_stop('node-3');self.start(self.member('node-3'),True);self.final_read(('node-3',))
            self.retained_stop(active);self.start(self.member(active),True);self.final_read(('node-3',))
        return True


class Services(faults.Services):
    mode=MODE
    cases=CASES


class Probe(faults.Probe):
    cell_type=Cell
    mode=MODE
    scope=SCOPE
    cases=CASES
