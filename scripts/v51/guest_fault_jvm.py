"""Owned two-field fault JVM pipes with generation-bound original exchanges."""
from concurrent.futures import Future
from pathlib import Path
import subprocess
import threading
import time
from .guest_jvm import Jvm as Pipes
from . import performance_model as m, remote_command as c, public_trace


class Jvm(Pipes):
    def __init__(self, args, root, node, generation, deadline):
        self.root,self.node,self.generation,self.deadline=Path(root),node,generation,deadline
        self.prefix=f'{node}-g{generation}';self.lock=threading.Lock();self.pending={};self.failed=None;self.buffer=b''
        self.rows=[];self.closed=False;self.stderr=(self.root/(self.prefix+'-stderr.log')).open('xb')
        self.proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,start_new_session=True)
        try:
            self.identity=dict(pid=self.proc.pid,startTicks=Path(f'/proc/{self.proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19],
                bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),args=args,node=node,generation=generation)
            c.write_once(self.root/(self.prefix+'-jvm.json'),self.identity)
            ready=self.line(min(deadline,time.monotonic()+30))
            m.need(ready==dict(status='STARTED',pid=self.proc.pid),'fault JVM ready identity')
            self.ready=dict(status='STARTED',identity=self.identity)
        except BaseException:
            self.proc.kill();self.proc.wait(timeout=5);self.streams_close();raise
        self.reader=threading.Thread(target=self.read,name='fault-'+self.prefix,daemon=True);self.reader.start()

    def line(self, deadline):
        try:return super().line(deadline)
        except ValueError as error:
            if error.args==('guest JVM EOF',):
                # Diagnostic only. Inspect a bounded tail for the exact observer
                # exception; never copy JVM/provider text into the Runner summary.
                try:
                    with (self.root/(self.prefix+'-stderr.log')).open('rb') as stream:
                        offset=max(0,stream.seek(0,2)-8192)
                        # Include the preceding byte so a clipped line cannot
                        # turn arbitrary text into an exact diagnostic match.
                        stream.seek(offset-1 if offset else 0)
                        lines=stream.read(8193 if offset else 8192).splitlines()
                        if offset:lines=lines[1:]
                    if b'Caused by: java.io.IOException: remote fault trace per-node bound' in lines:
                        raise ValueError('remote fault trace per-node bound') from None
                except OSError:pass
            raise

    def submit(self, kind, **values):
        with self.lock:
            if self.failed is not None:raise self.failed
            m.need(not self.closed and len(self.rows)<2000,'fault JVM unavailable/command bound')
            request=dict(kind=kind,opId=f'{self.prefix}-{len(self.rows)+1}',**values)
            row=dict(request=request,startNanos=time.monotonic_ns(),outcome='PENDING');self.rows.append(row)
            future=Future();self.pending[request['opId']]=future
            self.proc.stdin.write(m.canonical(request)+b'\n');self.proc.stdin.flush()
        return row,future

    def finish(self, pending):
        row,future=pending;request=row['request']
        try:
            response=future.result(timeout=max(.001,min(15,self.deadline-time.monotonic())))
            m.need(all(response.get(k)==v for k,v in request.items()),'fault JVM response identity/payload')
            row.update(response=response,endNanos=time.monotonic_ns(),outcome=response['outcome'])
            return dict(identity=self.identity,response=response)
        except BaseException as error:
            row.update(endNanos=time.monotonic_ns(),failure=dict(type=type(error).__name__,message=str(error)[:2000]));raise

    def command(self, kind, **values):return self.finish(self.submit(kind,**values))

    def stop(self, forced=False):
        if self.closed:return
        failed=None
        try:
            if self.proc.poll() is None:
                if forced:self.proc.kill()
                else:self.proc.stdin.write(b'{"kind":"close"}\n');self.proc.stdin.flush()
            self.proc.wait(timeout=max(.001,min(15,self.deadline-time.monotonic())))
            m.need(self.proc.returncode==(-9 if forced else 0),'fault JVM unexpected exit')
        except BaseException as error:failed=error
        finally:
            if self.proc.poll() is None:self.proc.kill();self.proc.wait(timeout=5)
            self.reader.join(timeout=5);self.closed=True;self.streams_close()
            # A real SIGKILL can disconnect the one armed mutation. Keep the
            # original invocation unresolved; never invent a response or replay.
            if forced and self.proc.returncode==-9:
                for row in self.rows:
                    if row['outcome']=='PENDING' and 'response' not in row and 'failure' not in row:
                        row['disconnectNanos']=time.monotonic_ns()
            c.write_once(self.root/(self.prefix+'-exchanges.json'),self.rows)
            c.write_once(self.root/(self.prefix+'-stop.json'),dict(**self.identity,exitCode=self.proc.returncode,
                forced=forced or failed is not None,readerReaped=not self.reader.is_alive()))
            public_trace.finish(self.root,self.node,self.proc,self.generation)
        m.need(not self.reader.is_alive(),'fault JVM reader remains active')
        if failed:raise failed
