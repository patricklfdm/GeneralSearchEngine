"""Persistent per-voter local service. No SSH routing or cross-host admission.

A disconnected channel never owns the JVM lifetime. The consumed launch and
operation sequence cannot restart a service or reissue a public operation.
"""
import argparse
from concurrent.futures import Future
from copy import deepcopy
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from . import remote_command as c, remote_host as host, remote_history as h
from . import measurement_history as ledger
from .evidence import need, encoded, digest, strict

SCHEMA='gse-v52-voter-service-v1'
FRAME=64<<10
MAX_CALLS=4096
MAX_BYTES=32<<20
MAX_PENDING=128


def send(channel,value):
    raw=encoded(value)+b'\n';need(len(raw)<=FRAME,'voter frame bound');channel.sendall(raw)


def receive(stream):
    raw=stream.readline(FRAME+1)
    if not raw:return None
    need(len(raw)<=FRAME and raw.endswith(b'\n'),'voter frame bound/truncated')
    value=strict(raw);need(type(value) is dict,'voter frame object');return value


def process(pid):
    fields=Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()
    return dict(bootId=c.boot_id(),pid=pid,startTicks=int(fields[19]))


def validate_config(value,control,*,fresh_socket=True):
    need(type(value) is dict and set(value)=={'schema','execution','node','root','host','binding','socket','session'},'voter config fields')
    need(value['schema']==SCHEMA and value['execution']=='local-persistent-voters-only','voter scope')
    need(value['node'] in h.topology.NODES,'voter node');c.hex_value(value['session'],32,'voter session')
    root=host.path(value['root'])
    need(control==root/(value['node']+'-control') and host.observe(control)==value['host'],'voter host changed')
    bound=value['binding'];need(bound['mode'] in h.runtime.model.MODES and bound.get('driverExercise') is True and
        'measurementProfile' not in bound,'voter service admits only untimed histories')
    need(bound.get('remoteVoterControl')=='local-persistent-voters-v1','voter control binding')
    need(bound['remoteTopology']['placement']=='local-no-gcp' and h.topology.read(root)==bound['remoteTopology'],'voter local topology')
    need(bound['remoteReceivers'][value['node']]['originalRoot']==str(root),'voter root binding')
    source=h.source();need(all(source[k]==bound[k] for k in source),'voter source changed')
    for section,prefix in (('artifacts','artifacts/'),('classes','')):
        for name,sha in bound[section].items():
            if section=='classes' and name.startswith('control-classes/'):continue
            path=root/(prefix+name)
            need(not path.is_symlink() and h.bundle.sha_file(path)==sha,'voter delivered bytes changed')
    need(not (root/h.options.FILE).exists() and not (root/h.recovery.FILE).exists(),'voter unexpected parameters')
    endpoint=host.path(value['socket']);host.observe(endpoint.parent)
    need(type(fresh_socket) is bool and len(os.fsencode(endpoint))<100 and
         (not fresh_socket or not endpoint.exists()),'voter socket path')
    return root


class Engine:
    """Bounded, append-only dispatch/result ledger, independent of connections."""
    def __init__(self,worker,control,config_sha,identity):
        self.worker=worker;self.control=control;self.sha=config_sha;self.identity=identity
        self.condition=threading.Condition(threading.RLock());self.events=[];self.serial=0
        self.pending=set();self.bytes=0;self.closing=False;self.closed=False;self.failure=None
        self.journal=(control/'events.jsonl').open('xb')

    def event(self,kind,**fields):
        with self.condition:
            row=dict(seq=len(self.events)+1,kind=kind,localNanos=time.monotonic_ns(),**fields)
            raw=encoded(row)+b'\n';need(len(raw)<=FRAME and self.bytes+len(raw)<=MAX_BYTES,'voter journal bound')
            self.journal.write(raw);self.journal.flush();self.bytes+=len(raw)
            self.events.append(row);self.condition.notify_all();return row

    def submit(self,request):
        with self.condition:
            need(not self.closing and self.failure is None,'voter stopping/failed')
            need(type(request) is dict and ledger.request(request)==request,'voter request fields')
            need(request.get('opId')==f'{self.worker.node}-g1-{self.serial+1}','voter consumed/out-of-order operation')
            need(self.serial<MAX_CALLS and len(self.pending)<MAX_PENDING,'voter operation bound')
            need(len(encoded(request))+1<=16384,'voter public request bound')
            # Reserve worst-case response space before touching the public API.
            need(self.bytes+(len(self.pending)+2)*FRAME<=MAX_BYTES,'voter journal admission bound')
            self.event('SUBMIT',request=deepcopy(request));self.serial+=1;self.pending.add(request['opId'])
            # The service is never restarted. A partial write/exception consumes
            # this identity, leaves an incomplete ledger and cannot be replayed.
        # Worker completes Futures under its pipe lock. Never acquire that lock
        # while holding the journal condition: a callback needs this condition.
        try:
            values={k:v for k,v in request.items() if k not in ('opId','kind')}
            op,future=self.worker.submit(request['kind'],**values)
            need(op==request['opId'],'voter dispatch identity')
            future.add_done_callback(lambda result:self.complete(op,result))
        except BaseException:
            with self.condition:self.failure='DISPATCH_UNCERTAIN'
            raise

    def complete(self,op,future):
        with self.condition:
            try:
                value=future.result();need(value is not None and value.get('opId')==op,'voter missing original response')
                self.event('RESULT',response=value);self.pending.remove(op)
            except BaseException:
                self.failure='RESPONSE_UNCERTAIN';self.condition.notify_all()

    def close(self):
        with self.condition:
            if self.closing:return
            self.closing=True
        try:
            self.worker.stop()
            need(not self.pending and self.failure is None,'voter incomplete original operations')
        except BaseException as error:
            self.failure=repr(error)[:2000]
        finally:
            with self.condition:
                try:
                    row=self.event('STOPPED',exitCode=self.worker.proc.returncode,failure=self.failure)
                    os.fsync(self.journal.fileno())
                    c.write_once(self.control/'stopped.json',dict(schema=SCHEMA,configSha256=self.sha,
                        identity=self.identity,lastSequence=row['seq'],journalSha256=h.bundle.sha_file(self.control/'events.jsonl'),
                        exitCode=self.worker.proc.returncode,failure=self.failure))
                finally:self.closed=True;self.condition.notify_all()

    def serve(self,channel):
        channel.settimeout(5);stream=channel.makefile('rb');disconnected=threading.Event();writer=None
        try:
            hello=receive(stream)
            need(type(hello) is dict and set(hello)=={'configSha256','after'} and hello['configSha256']==self.sha,'voter channel binding')
            after=hello['after']
            need(type(after) is int and 0<=after<=len(self.events),'voter replay cursor')
            send(channel,dict(kind='IDENTITY',configSha256=self.sha,identity=self.identity))
            channel.settimeout(None)
            def write():
                cursor=after
                try:
                    while not disconnected.is_set():
                        with self.condition:
                            self.condition.wait_for(lambda:cursor<len(self.events) or self.closed or disconnected.is_set(),1)
                            batch=self.events[cursor:cursor+32]
                            done=self.closed and not batch
                        for row in batch:send(channel,row);cursor+=1
                        if done:break
                except (OSError,ValueError):pass
                finally:
                    disconnected.set()
                    try:channel.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
            writer=threading.Thread(target=write,daemon=True);writer.start()
            while not disconnected.is_set():
                value=receive(stream)
                if value is None:break
                if set(value)=={'close'} and value['close'] is True:
                    threading.Thread(target=self.close,daemon=True).start()
                else:self.submit(value)
        except (OSError,ValueError,KeyError,TypeError):
            # Reject this channel; never erase operations or restart its voter.
            pass
        finally:
            disconnected.set()
            with self.condition:self.condition.notify_all()
            try:channel.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            if writer:writer.join(5)
            stream.close();channel.close()


def serve(control):
    control=c.directory(Path(control).absolute());value=c.read(control/'config.json',c.REQUEST_BYTES)
    root=validate_config(value,control);sha=digest(encoded(value))
    need(c.read(control/'launch.json')==dict(configSha256=sha),'voter launch binding')
    # Atomic publication/partial publication both consume the original launch.
    c.write_once(control/'started.json',dict(configSha256=sha,service=process(os.getpid())))
    worker=None;engine=None
    try:
        worker=h.Worker(root,value['node'],h.Receivers.paths(root,value['binding']),value['binding']['mode'],[])
        identity=dict(service=process(os.getpid()),jvm=process(worker.proc.pid),consumer=worker.identity,
                      host=host.observe(control),session=value['session'])
        c.write_once(control/'identity.json',identity)
        engine=Engine(worker,control,sha,identity)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
            listener.bind(value['socket']);os.chmod(value['socket'],0o600);listener.listen(1);listener.settimeout(1)
            while not engine.closed:
                try:channel,_=listener.accept()
                except TimeoutError:continue
                engine.serve(channel)
    finally:
        if engine:
            engine.close();engine.journal.close()
        elif worker:worker.stop(kill=True)
        Path(value['socket']).unlink(missing_ok=True)


class Client:
    """One persistent stream. Reconnect reads results; submit is never retried."""
    def initialize(self,root,node,history):
        self.root,self.node,self.generation,self.history=Path(root),node,1,history
        self.control=self.root/(node+'-control')
        self.lock=threading.RLock();self.pending={};self.serial=0;self.cursor=0
        self.channel=None;self.reader=None;self.error=None;self.terminal=Future();self.agent=None
        self.proc=SimpleNamespace(pid=0,returncode=None,poll=lambda:self.proc.returncode)
        self.events=[];self.owner_identity=None;self.identity=None;self.connections=0

    def __init__(self,root,node,binding,history):
        self.initialize(root,node,history);self.control.mkdir(mode=0o700)
        self.socket_dir=tempfile.TemporaryDirectory(prefix='v52-voter-')
        self.config=dict(schema=SCHEMA,execution='local-persistent-voters-only',node=node,root=str(self.root),
                         host=host.observe(self.control),binding=binding,socket=self.socket_dir.name+'/channel',session=os.urandom(16).hex())
        self.sha=digest(encoded(self.config))
        self.agent_log=(self.control/'agent.log').open('xb')
        try:
            c.write_once(self.control/'config.json',self.config,c.REQUEST_BYTES)
            c.write_once(self.control/'launch.json',dict(configSha256=self.sha))
            self.agent=subprocess.Popen([sys.executable,'-m','scripts.v52.remote_voter',str(self.control)],cwd=h.ROOT,
                stdin=subprocess.DEVNULL,stdout=self.agent_log,stderr=self.agent_log,start_new_session=True)
            deadline=time.monotonic()+40
            while not Path(self.config['socket']).exists():
                need(self.agent.poll() is None,'voter agent startup failed: '+str(self.control/'agent.log'))
                need(time.monotonic()<deadline,'voter agent startup timeout');time.sleep(.05)
            self.connect()
        except BaseException:self.abort();raise

    def open_channel(self):
        channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);channel.settimeout(10)
        try:
            channel.connect(self.config['socket']);return channel
        except BaseException:channel.close();raise

    def connect(self):
        need(self.channel is None,'voter channel already connected')
        channel=self.open_channel();stream=None
        try:
            stream=channel.makefile('rb')
            send(channel,dict(configSha256=self.sha,after=self.cursor));identity=receive(stream)
            expected=self.observe_identity()
            need(identity==dict(kind='IDENTITY',configSha256=self.sha,identity=expected),'voter channel identity')
            need(self.owner_identity is None or self.owner_identity==expected,'voter process changed on reconnect')
            self.owner_identity=expected;self.identity=expected['consumer'];self.proc.pid=expected['jvm']['pid']
            channel.settimeout(None);self.channel=channel;self.error=None;self.connections+=1
            self.reader=threading.Thread(target=self.receive,args=(stream,),daemon=True);self.reader.start()
        except BaseException:
            if stream:stream.close()
            channel.close();raise

    def observe_identity(self):
        expected=c.read(self.control/'identity.json')
        need(expected['host']==self.config['host'] and expected['session']==self.config['session'] and
             expected['service']['pid']==self.agent.pid and c.process_alive(expected['service']) and
             c.process_alive(expected['jvm']),'voter process ownership')
        return expected

    def wait_stopped(self):
        need(self.agent.wait(timeout=10)==0,'voter agent exit failed')

    def receive(self,stream):
        try:
            while True:
                row=receive(stream)
                if row is None:break
                self.receive_event(row)
                if row['kind']=='STOPPED':break
        except BaseException as error:self.error=repr(error)
        finally:stream.close()

    def receive_event(self,row):
        with self.lock:
            need(row['seq']==self.cursor+1,'voter missing/repeated stream event')
            self.events.append(row);self.cursor=row['seq']
            if row['kind']=='RESULT':
                result=row['response'];future,record=self.pending.pop(result['opId'])
                record.update(endNanos=time.monotonic_ns(),outcome=result['outcome'],response=result);future.set_result(result)
            elif row['kind']=='STOPPED':
                self.proc.returncode=row['exitCode'];self.terminal.set_result(row)
            else:need(row['kind']=='SUBMIT','voter unknown stream event')

    def disconnect(self):
        if self.channel:
            try:self.channel.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.channel.close();self.channel=None
        if self.reader:self.reader.join(5);need(not self.reader.is_alive(),'voter channel reader did not stop')

    def submit(self,kind,**values):
        with self.lock:
            need(self.channel is not None and self.error is None and self.reader.is_alive(),'voter stream unavailable; query original')
            self.serial+=1;op=f'{self.node}-g1-{self.serial}';request=dict(opId=op,kind=kind,**values)
            record=dict(request,node=self.node,pid=self.proc.pid,generation=1,startNanos=time.monotonic_ns(),endNanos=None,outcome='PENDING')
            future=Future();self.pending[op]=(future,record);self.history.append(record)
            send(self.channel,request);return op,future

    def send(self,kind,**values):return self.submit(kind,**values)[1]

    def call(self,kind,**values):
        result=self.send(kind,**values).result(timeout=35)
        need(result is not None and result['outcome']=='SUCCESS','measurement public call failed: '+str(result));return result

    def stop(self):
        try:
            if not self.terminal.done():
                if self.channel is None or not self.reader.is_alive():self.disconnect();self.connect()
                send(self.channel,{'close':True})
            row=self.terminal.result(timeout=h.runtime.STOP_TIMEOUT_SECONDS+5)
            need(row['failure'] is None and row['exitCode']==0 and not self.pending,'voter incomplete close: '+str(row))
            self.wait_stopped()
        finally:self.abort()

    def abort(self):
        try:self.disconnect()
        finally:
            if self.agent and self.agent.poll() is None:
                # Only our still-owned child session. Never a PID recovered from
                # untrusted evidence or a replacement process.
                os.killpg(self.agent.pid,signal.SIGKILL);self.agent.wait(timeout=10)
                if self.owner_identity:
                    self.proc.returncode=-9
            self.agent_log.close();self.socket_dir.cleanup()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('control');serve(parser.parse_args().control)
