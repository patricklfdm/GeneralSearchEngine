"""Closed fault controls in one authenticated, independently bootstrapped guest.

Only the frozen EMPTY two-field fault groups, observed-cut crashes, retained
restarts and bounded network/force controls are supported. No request supplies executable code, paths, durations or rules.
"""
import os
from pathlib import Path
import re
import shutil
import threading
import time
from . import cloud_package as package, remote_command as c, remote_collection as parts, performance_model as m
from . import guest_authority as authority, public_trace
from .guest_fault_jvm import Jvm
from .guest_fault_network import CASES as NETWORK_CASES, Controls
from . import guest_fault_recovery as recovery

CASES=('leader-loss','maintenance','no-quorum')
QUICK_CASES=('leader-loss','no-quorum')
RULES=[f'node-{a} node-{b} BEFORE_REQUEST_WRITE *' for a in (1,2,3) for b in (1,2,3) if a!=b]


def argv(base, config, action, generation=1):
    command=package.command(base,package.MODES[2])
    command[-1]=package.PACKAGE+('admission.V51RemoteFaultConsumer' if action=='setup' else 'replication.V51PublicWorker')
    from .native_experiment_timing import PROFILE
    tail=[PROFILE] if config['execution']=='native-v51-guest-service' else []
    return command+[config['root'],'setup'] if action=='setup' else command+[config['root'],config['binding']['node'][-1],'remote-fault',str(generation),*tail]


class Handler:
    def __init__(self, service):
        self.s=service;self.case=service.config['faultCell'];self.generation=0;self.isolated=False;self.healed=False
        self.pin=None;self.pin_released=False
        self.lock=threading.RLock();self.timer=None;self.isolation=None
        self.network=Controls(self) if self.case in NETWORK_CASES else None
        self.recovery=recovery.Controls(self) if self.case in recovery.CASES else None
    def rules(self, rows):
        path=self.s.cell/'network-rules.txt';temporary=path.with_suffix('.tmp')
        temporary.write_text('\n'.join(rows)+'\n');os.replace(temporary,path)
    def heal(self, watchdog=False):
        if self.recovery is not None:self.recovery.release_direction(watchdog)
        if self.network is not None:return self.network.release(watchdog)
        with self.lock:
            if not self.isolated or self.healed:return
            self.rules([]);self.healed=True
            self.isolation.update(healedNanos=time.monotonic_ns(),watchdog=watchdog)
            c.write_once(self.s.cell/'isolation.json',self.isolation)
            if self.timer is not None:self.timer.cancel()
    def handle(self, name, payload, checkpoint):
        s=self.s;root=s.cell;node=s.node;cfg=s.config
        m.need(self.case in (*CASES,*NETWORK_CASES,*recovery.CASES),'fault scope')
        if name=='prepare-cell':
            m.need(payload=={} and s.jvm is None,'fault preparation payload/state')
            c.write_once(root/'fault-prepare-claim.json',cfg)
            if self.case=='minority-capacity':(root/'resource-evidence').touch(exist_ok=False)
            for file,text in [('hosts.txt','\n'.join(cfg['hosts'])+'\n'),('ports.txt','\n'.join(map(str,cfg['ports']))+'\n'),
                              ('group-id.txt',cfg['groupId']+'\n'),('cell.txt',self.case+'\n')]:
                with (root/file).open('x') as out:out.write(text)
            for name in ('phase6-plan.json','phase6-cloud-workload-plan.json'):
                shutil.copyfile(s.base/'source-inputs/docs/v5x/v5.1'/name,root/('plan.json' if name=='phase6-plan.json' else 'cloud-plan.json'))
            operation=s.oneshot('empty-bootstrap',argv(s.base,cfg,'setup'))
            # Each guest creates its own public filesystem seals; unstarted sibling
            # outputs never become live authority and never cross machines.
            unstarted=s.root/'unstarted-bootstrap';unstarted.mkdir()
            for other in ('node-1','node-2','node-3','operation'):
                if other!=node:os.rename(root/other,unstarted/other)
            files=authority.inventory(root/node)
            result=dict(source='EMPTY',node=node,groupId=cfg['groupId'],files=files,
                manifestSha256=m.sha((root/node/'manifest.gsr').read_bytes()),genesisSha256=m.sha((root/node/'genesis.gsr').read_bytes()),operation=operation)
            c.write_once(root/'fault-prepared.json',result);return result
        if name=='start-voter':
            m.need(payload=={} and self.generation==0 and s.jvm is None,'fault first start consumed')
            prepared=c.read(root/'fault-prepared.json')
            m.need(c.read(root/'fault-prepare-claim.json')==cfg and authority.inventory(root/node)==prepared['files'],'fault bootstrap changed')
            self.generation=1
            s.jvm=Jvm(argv(s.base,cfg,'start',1),root,node,1,s.deadline);return s.jvm.ready
        if name=='fault':
            action=payload.get('action')
            if action=='restart':
                m.need(payload=={'action':'restart'} and self.case in ('leader-loss',*recovery.CASES) and self.generation==1 and s.jvm.closed and
                       s.jvm.proc.returncode in ((0,) if self.case in ('group-restart','minority-capacity') else (-9,)), 'fault retained restart state')
                archive=root/'crash'/node
                m.need(authority.inventory(archive)==authority.inventory(root/node),'fault retained restart authority changed')
                self.generation=2;s.jvm=Jvm(argv(s.base,cfg,'start',2),root,node,2,s.deadline);return s.jvm.ready
            if self.recovery is not None and action in ('prepare-direction','heal-direction','arm-cut','start-target','observe-recovery','isolate','heal'):
                return self.recovery.handle(payload)
            m.need(s.jvm is not None and not s.jvm.closed,'fault live voter required')
            if self.network is not None and action in ('isolate','heal','observe-network'):
                return self.network.handle(payload)
            if action=='status':
                m.need(payload=={'action':'status'} or self.case=='minority-capacity' and payload=={'action':'status','boundary':'resource-rejected'},'fault status payload')
                return s.jvm.command('status',**({} if 'boundary' not in payload else dict(boundary=payload['boundary'])))
            if action=='pin':
                m.need(self.case=='maintenance' and self.pin is None and set(payload)=={'action','intentId'} and
                       re.fullmatch('call-(0[1-9]|1[0-9]|2[0-4])',payload['intentId']), 'fault pin consumed/scope')
                c.write_once(root/'pin-claim.json',payload)
                (root/(node+'-arm.txt')).write_text('READ_CAPTURED\npause\n')
                self.pin=s.jvm.submit('read',intentId=payload['intentId'])
                return dict(identity=s.jvm.identity,opId=self.pin[0]['request']['opId'])
            if action=='pin-state':
                m.need(payload=={'action':'pin-state'} and self.case=='maintenance' and self.pin is not None,'fault pin observation scope')
                rows=public_trace.live_rows(root,node)
                cut=next((r for r in rows if r['event']=='CUT_REACHED' and r['cut']=='READ_CAPTURED'),None)
                installed=next((r for r in rows if cut and r['event']=='REJOIN_INSTALLED' and r['order']>cut['order']),None)
                unpinned=next((r for r in rows if self.pin_released and r['event']=='PERFORMANCE_SAMPLE' and
                               r['localNanos']>self.pin[0]['endNanos'] and r['queues']['pinsBytes']==0),None)
                return dict(cut=cut,installed=installed,unpinned=unpinned,pending=not self.pin[1].done())
            if action=='release-pin':
                m.need(payload=={'action':'release-pin'} and self.case=='maintenance' and self.pin is not None and
                       not self.pin_released and not self.pin[1].done(),'fault pin release state')
                c.write_once(root/'pin-release-claim.json',payload)
                (root/(node+'-release')).touch(exist_ok=False)
                result=s.jvm.finish(self.pin);self.pin_released=True;return result
            if action=='call':
                kind=payload.get('kind');extra={'documents'} if kind=='addAll' else set()
                m.need(kind in (('addAll','read','checkpoint','backup') if self.case=='maintenance' else ('addAll','read')) and set(payload)=={'action','kind','intentId'}|extra and
                       re.fullmatch('call-(0[1-9]|1[0-9]|2[0-4])',payload['intentId']), 'fault public call payload')
                if kind=='addAll':
                    m.need(recovery.bulk_allowed(self.case,payload['documents']),'fault two-field bulk')
                claims=root/'calls';claims.mkdir(exist_ok=True)
                c.write_once(claims/(payload['intentId']+'.json'),payload)
                return s.jvm.command(kind,**{k:v for k,v in payload.items() if k not in ('action','kind')})
            if action=='isolate':
                m.need(not self.isolated and ((self.case=='no-quorum' and payload=={'action':'isolate'}) or
                       (self.case=='maintenance' and set(payload)=={'action','node'} and payload['node'] in ('node-1','node-2','node-3'))),'fault isolation consumed/scope')
                with self.lock:
                    self.isolated=True
                    rules=RULES if self.case=='no-quorum' else [r for r in RULES if payload['node'] in r.split()[:2]]
                    self.rules(rules);self.isolation=dict(appliedNanos=time.monotonic_ns(),rules=rules)
                    # Independent emergency release. Triggering it FAILS validation;
                    # it is never accepted in lieu of the controller's 15s hold.
                    from . import native_experiment_timing as timing
                    seconds=timing.CONTROLS['isolation'] if cfg['execution']=='native-v51-guest-service' else (17 if self.case=='no-quorum' else 60)
                    self.timer=threading.Timer(seconds,lambda:self.heal(True));self.timer.daemon=True;self.timer.start()
                    return dict(self.isolation)
            if action=='heal':
                m.need(payload=={'action':'heal'} and self.isolated,'fault heal scope');self.heal();return c.read(root/'isolation.json')
            raise ValueError('unsupported owned fault action')
        if name=='stop-voter':
            retained=payload.get('retain') is True and set(payload)=={'forced','retain'} and self.case in ('group-restart','minority-capacity') and self.generation==1
            m.need((set(payload)=={'forced'} or retained) and type(payload['forced']) is bool and s.jvm is not None and not s.jvm.closed,'fault stop state')
            m.need(not payload['forced'] or self.case in ('leader-loss',*recovery.CUTS) and self.generation==1,'fault kill scope')
            if payload['forced'] and self.recovery is not None:self.recovery.before_kill()
            s.jvm.stop(payload['forced'])
            if payload['forced'] or retained:
                (root/'crash').mkdir();authority.capture(root,node,root/'crash'/node)
                c.write_once(root/'crash/inventory.json',authority.inventory(root/node))
            return c.read(root/(s.jvm.prefix+'-stop.json'))
        if name=='restore-backup':
            m.need(payload=={} and self.case=='maintenance' and s.jvm is not None and s.jvm.closed,'fault restore scope')
            c.write_once(root/'restore-claim.json',dict(config=cfg,files=authority.inventory(root/'backup')))
            args=package.command(s.base,package.MODES[0]);args[-1]=package.PACKAGE+'admission.V51OwnedFaultRestore';args.append(str(root))
            result=s.oneshot('maintenance-restore',args)
            for suffix in ('stdout','stderr'):shutil.copyfile(s.root/('maintenance-restore.'+suffix),root/('restore.'+suffix))
            c.write_once(root/'restore.json',result);return result
        if name=='collect':
            m.need(payload=={'physical':True} and s.jvm is not None and s.jvm.closed,'fault stopped collection scope')
            m.need(not self.isolated or self.healed,'fault still isolated')
            raw=s.root/'collection';raw.mkdir()
            shutil.copytree(s.root/'store',raw/'store',ignore=shutil.ignore_patterns(s.current['commandId'],'executor.lock'))
            for path in root.iterdir():
                if path.name in ('agents','app-'+node,'restored') or path.name in ('node-1','node-2','node-3'):continue
                if path.name==node+'-trace.jsonl':
                    public_trace.copy_fault_trace(root,raw,node);continue
                m.need(not path.is_symlink(),'fault collection symlink')
                if path.is_dir():shutil.copytree(path,raw/path.name)
                else:shutil.copyfile(path,raw/path.name)
            authority.capture(root,node,raw/'authority'/node)
            return parts.pack(raw,s.root/'parts',m.sha(m.canonical(cfg['binding'])))
        raise ValueError('unsupported owned fault command')
