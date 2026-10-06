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
from . import guest_delivery_receiver as r

SCHEMA='gse-v51-native-session-v1'
EXECUTION='native-v51-guest-service'
MODES=('published-v4.4-local','published-v5.0-configured','candidate-v5.1-automatic')
FAULTS=('leader-loss','maintenance','no-quorum')


def identity(value):
    raw=r.canonical(value)
    return r.descriptor(dict(schema='gse-v51-helper-delivery-v1',binding=value['binding'],instanceId=value['instanceId'],
        diskId=value['diskId'],guestAccessSha256=value['guestAccessSha256'],payloadSha256=r.sha(raw),payloadBytes=len(raw)))


def validate(session, value):
    r.need(type(session) is dict and set(session)=={'schema','packageSha256','preparation','leaseExpiresNanos','hosts','port'} and
           session['schema']==SCHEMA and session['packageSha256']==r.sha(r.canonical(value)), 'native session package/fields')
    budget=r.validate_budget(session['preparation'],identity(value))
    end=session['leaseExpiresNanos'];sample=budget['sample']
    r.need(type(end) is int and budget['expiresNanos'] <= end <= sample['sampledNanos']+5400*10**9,'native session original lease bound')
    hosts=session['hosts'];port=session['port']
    r.need(type(hosts) is list and len(hosts)==3 and len(set(hosts))==3 and type(port) is int and 1024<=port<=65535,
           'native session topology')
    networks=[ipaddress.ip_network(v) for v in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    for host in hosts:
        address=ipaddress.IPv4Address(host)
        r.need(str(address)==host and any(address in network for network in networks),'native private peer address')
    return session


def configuration(value, session, mode, cell=None, *, node=None):
    validate(session,value)
    r.need(mode in MODES and (cell is None or cell in FAULTS and mode==MODES[2]),'native session cell/mode')
    binding=dict(value['binding']);binding['node']=node or binding['node']
    r.need(binding['node'] in ('node-1','node-2','node-3'),'native session node')
    sha=value['nativeVolume']['request']['requestSha256']
    result=dict(schema='gse-v51-guest-service-v1',execution=EXECUTION,binding=binding,
        packageManifestSha256=value['manifestSha256'],root='/mnt/gse-v51/'+(cell or mode),mode=mode,
        hosts=session['hosts'],ports=[session['port']]*3,groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+(cell or mode))))
    if cell:result['faultCell']=cell
    return result


def check_config(config, value, session, *, node=None):
    r.need(type(config) is dict and config==configuration(value,session,config.get('mode'),config.get('faultCell'),node=node),
           'native session exact configuration')


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
    r.guest_deadline(session['preparation'],identity(value))
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


def dispatch(action, value, session, tail, stream):
    # These imports exist in the trusted controller bundle. They are deliberately
    # absent from the packaged daemon path above, which cannot admit new actions.
    from . import guest_native_package as native, guest_package_receiver as package
    native.validate(value);validate(session,value)
    preparation=action in ('begin','producer','source','bootstrap')
    deadline=r.guest_deadline(session['preparation'],identity(value)) if preparation else lease_deadline(session,value)
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
                r.need(value['binding']['node']=='node-1' and type(request.get('configs')) is list and
                       len(request['configs']) in (1,3),'native producer members')
                for i,cfg in enumerate(request['configs'],1):check_config(cfg,value,session,node='node-'+str(i))
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
    if action in ('begin','producer','source','bootstrap'):deadline=r.guest_deadline(session['preparation'],identity(value))
    def expired(*_):raise TimeoutError('native session original deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        result=dispatch(action,value,session,tail,sys.stdin.buffer)
        if result is not None:
            sys.stdout.buffer.write(result if isinstance(result,bytes) else r.canonical(result)+b'\n');sys.stdout.buffer.flush()
    finally:signal.setitimer(signal.ITIMER_REAL,0)
