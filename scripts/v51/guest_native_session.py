"""Closed native service session, tied to the installed package's original clock.

The controller's trusted copy admits requests before importing installed code.
The packaged copy checks the same immutable session before a daemon can start.
"""
import base64
import ipaddress
import os
from pathlib import Path
import signal
import sys
import time
import uuid
from . import guest_delivery_receiver as r, native_preset_timing as full

SCHEMA='gse-v51-native-session-v1'
EXECUTION='native-v51-guest-service'
MODES=('published-v4.4-local','published-v5.0-configured','candidate-v5.1-automatic')
FAULTS=('leader-loss','maintenance','no-quorum')


def identity(value):
    r.need(value.get('schema')=='gse-v51-native-package-transfer-v1','native session package domain')
    raw=r.canonical(value)
    return r.descriptor(dict(schema='gse-v51-helper-delivery-v1',binding=value['binding'],instanceId=value['instanceId'],
        diskId=value['diskId'],guestAccessSha256=value['guestAccessSha256'],payloadSha256=r.sha(raw),payloadBytes=len(raw)))


def validate(session, value):
    r.need(type(session) is dict and set(session)=={'schema','packageSha256','preparation','leaseExpiresNanos','hosts','port'} and
           session['schema']==SCHEMA and session['packageSha256']==r.sha(r.canonical(value)), 'native session package/fields')
    budget=r.validate_budget(session['preparation'],identity(value),profile=full.package_profile(value))
    end=session['leaseExpiresNanos'];sample=budget['sample']
    from .native_experiment_timing import LEASE_SECONDS
    req=full.package_request(value)
    if req is not None:LEASE_SECONDS=full.validate(req)['leaseSeconds']
    r.need(type(end) is int and budget['expiresNanos'] <= end <= sample['sampledNanos']+LEASE_SECONDS*10**9,'native session original lease bound')
    hosts=session['hosts'];port=session['port']
    r.need(type(hosts) is list and len(hosts)==3 and len(set(hosts))==3 and type(port) is int and 1024<=port<=65535,
           'native session topology')
    networks=[ipaddress.ip_network(v) for v in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    for host in hosts:
        address=ipaddress.IPv4Address(host)
        r.need(str(address)==host and any(address in network for network in networks),'native private peer address')
    return session


def configuration(value, session, mode, cell=None, *, node=None, workload=None):
    validate(session,value)
    req=full.package_request(value)
    selected=full.validate(req) if req is not None else None
    faults=selected['cells'] if selected else FAULTS
    r.need(mode in MODES and (cell is None or cell in faults and cell not in ('healthy','read-heavy','sustained') and mode==MODES[2]),'native session cell/mode')
    from . import cloud_package as layout
    r.need(workload is None or selected is not None and selected['preset']=='canonical' and cell is None and
           workload==dict(cell=workload.get('cell'),preset='canonical',repetition=selected['repetition']) and
           (mode,workload['cell']) in layout.CANONICAL_WORKLOADS,
           'native session canonical workload')
    if selected:
        r.need((selected['preset']=='failure-drill' and cell is not None) or
               (selected['preset']=='canonical' and (cell is not None or workload is not None)) or
               (selected['preset']=='experiment' and workload is None), 'native session preset scope')
    binding=dict(value['binding']);binding['node']=node or binding['node']
    r.need(binding['node'] in ('node-1','node-2','node-3'),'native session node')
    sha=value['nativeVolume']['request']['requestSha256']
    label=cell or mode
    if workload:label='canonical-r'+str(workload['repetition'])+'-'+workload['cell']+'-'+mode
    result=dict(schema='gse-v51-guest-service-v1',execution=EXECUTION,binding=binding,
        packageManifestSha256=value['manifestSha256'],root='/mnt/gse-v51/'+label,mode=mode,
        hosts=session['hosts'],ports=[session['port']]*3,groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+label)))
    if cell:result['faultCell']=cell
    if workload:result['workload']=dict(workload)
    if req is not None:result['nativeRequest']=dict(req)
    return result


def check_config(config, value, session, *, node=None):
    r.need(type(config) is dict and config==configuration(value,session,config.get('mode'),config.get('faultCell'),
           node=node,workload=config.get('workload')), 'native session exact configuration')


def lease_deadline(session, value):
    validate(session,value)
    r.need(session['preparation']['sample']['bootId']==r.boot_identity() and
           time.monotonic_ns()<session['leaseExpiresNanos'],'native session expired/boot changed')
    return session['leaseExpiresNanos']/1e9


def observe(base, session, value):
    lease_deadline(session,value);folder=Path(base).parent/'native-session'
    if not folder.exists():return dict(state='NOT_FOUND')
    r.owned(folder,os.getuid(),True)
    if not (folder/'request.json').exists():return dict(state='UNCERTAIN')
    r.need(r.decode(r.read(folder/'request.json',os.getuid()))==session,'native session consumed identity/deadline')
    if not (folder/'receipt.json').exists():return dict(state='UNCERTAIN')
    expected=dict(state='SUCCEEDED',sessionSha256=r.sha(r.canonical(session)))
    r.need(r.decode(r.read(folder/'receipt.json',os.getuid()))==expected,'native session receipt changed')
    return expected


def begin(base, session, value):
    r.guest_deadline(session['preparation'],identity(value),profile=full.package_profile(value))
    previous=observe(base,session,value)
    if previous['state']!='NOT_FOUND':return previous
    folder=Path(base).parent/'native-session'
    try:folder.mkdir(mode=0o700)
    except FileExistsError:return observe(base,session,value)
    r.sync(folder.parent);r.publish(folder/'request.json',session)
    r.publish(folder/'receipt.json',dict(state='SUCCEEDED',sessionSha256=r.sha(r.canonical(session))))
    return observe(base,session,value)


def service_deadline(base, config):
    """Called before daemon filesystem writes and again inside its new process."""
    base=Path(base);value=r.decode(r.read(base.parent/'request.json',os.getuid()))
    r.need(value['schema']=='gse-v51-native-package-transfer-v1','native service package domain')
    session=r.decode(r.read(base.parent/'native-session/request.json',os.getuid()))
    r.need(r.decode(r.read(base.parent/'deadline.json',os.getuid()))==session['preparation'],'native service original package clock')
    check_config(config,value,session)
    r.need(observe(base,session,value)['state']=='SUCCEEDED','native service session unavailable')
    return lease_deadline(session,value)


def preparation_deadline(base, config):
    """Authenticate the exact service config but retain its shorter setup clock."""
    service_deadline(base,config)
    base=Path(base);value=r.decode(r.read(base.parent/'request.json',os.getuid()))
    budget=r.decode(r.read(base.parent/'deadline.json',os.getuid()))
    return r.guest_deadline(budget,identity(value),profile=full.package_profile(value))


def dispatch(action, value, session, tail, stream):
    # These imports exist in the trusted controller bundle. They are deliberately
    # absent from the packaged daemon path above, which cannot admit new actions.
    from . import guest_native_package as native, guest_package_receiver as package
    native.validate(value);validate(session,value)
    preparation=action in ('begin','producer','source','bootstrap')
    deadline=r.guest_deadline(session['preparation'],identity(value),profile=full.package_profile(value)) if preparation else lease_deadline(session,value)
    native.context(value,deadline)
    base=package.installed('/mnt/gse-v51',value)
    r.need(package.read(base.parent/'deadline.json')==session['preparation'],'native session original package budget')
    if action in ('begin','query'):
        r.need(not tail,'native session arguments')
        answer=begin(base,session,value) if action=='begin' else observe(base,session,value)
    else:
        r.need(observe(base,session,value)['state']=='SUCCEEDED','native session not admitted')
        r.need(action in ('service','producer','source','bootstrap'),'native session action')
        if action=='service':
            r.need(tail and len(tail[0])<=65536,'native service request bound')
            config=r.decode(base64.b64decode(tail[0],validate=True));check_config(config,value,session)
            # package.service writes its own binary/JSON output; no second frame.
            package.service('/mnt/gse-v51',value,tail[0],tail[1:]);answer=None
        else:
            r.need(len(tail)>=2 and len(tail[1])<=90000,'native bootstrap request bound')
            request=r.decode(base64.b64decode(tail[1],validate=True))
            if action=='producer':
                from . import cloud_package as layout
                configs=request.get('configs')
                r.need(type(configs) is list and len(configs) in (1,3),'native producer members')
                nodes=layout.service_nodes(configs[0])
                r.need(len(configs)==len(nodes) and value['binding']['node']=='node-'+str(nodes[0]),'native producer host')
                for i,cfg in zip(nodes,configs):check_config(cfg,value,session,node='node-'+str(i))
            else:
                check_config(request['config'],value,session)
                if action=='bootstrap':r.need(set(request)=={'config','descriptorSha256','sourceTransferSha256'},'native transferred bootstrap only')
            if action=='source':answer=package.source_transfer('/mnt/gse-v51',value,session['preparation'],tail,stream)
            else:answer=getattr(package,action)('/mnt/gse-v51',value,session['preparation'],tail)
    native.context(value,deadline);r.need(time.monotonic()<deadline,'native session late result')
    return answer


def main():
    action,encoded,token,*tail=sys.argv[1:]
    r.need(len(encoded)<=131072 and len(token)<=8192,'native session envelope bound')
    value=r.decode(base64.b64decode(encoded,validate=True));session=r.decode(base64.b64decode(token,validate=True))
    deadline=lease_deadline(session,value)
    if action in ('begin','producer','source','bootstrap'):deadline=r.guest_deadline(session['preparation'],identity(value),profile=full.package_profile(value))
    def expired(*_):raise TimeoutError('native session original deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        result=dispatch(action,value,session,tail,sys.stdin.buffer)
        if result is not None:
            sys.stdout.buffer.write(result if isinstance(result,bytes) else r.canonical(result)+b'\n');sys.stdout.buffer.flush()
    finally:signal.setitimer(signal.ITIMER_REAL,0)
