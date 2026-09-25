"""Owned persistent guest pipes. SSH never carries individual timed GSE calls."""
from concurrent.futures import Future
import os
from pathlib import Path
import select
import subprocess
import threading
import time
from . import performance_model as m
from .remote_command import write_once


class Jvm:
    def __init__(self, args, root, node, deadline):
        self.root, self.node, self.deadline = Path(root), node, deadline
        self.lock, self.pending, self.failed, self.buffer = threading.Lock(), {}, None, b''
        self.rows = []; self.closed = False
        self.stderr = (self.root/(node+'-stderr.log')).open('xb')
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        try:
            ticks = Path(f'/proc/{self.proc.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
            self.identity = dict(pid=self.proc.pid, startTicks=ticks, bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), args=args)
            write_once(self.root/(node+'-jvm.json'), self.identity)
            ready = self.line(min(deadline, time.monotonic()+30))
            m.need(ready['status'] == 'STARTED' and ready['identity']['pid'] == self.proc.pid, 'guest JVM startup identity')
            self.ready = ready
        except BaseException:
            self.proc.kill(); self.proc.wait(timeout=5); self.streams_close(); raise
        self.reader = threading.Thread(target=self.read, name='v51-guest-'+node, daemon=True); self.reader.start()

    def line(self, deadline):
        while b'\n' not in self.buffer:
            left = deadline-time.monotonic()
            m.need(left > 0 and select.select([self.proc.stdout], [], [], left)[0], 'guest JVM response deadline')
            data = os.read(self.proc.stdout.fileno(), 65536); m.need(data, 'guest JVM EOF')
            self.buffer += data; m.need(len(self.buffer) <= 4 << 20, 'guest JVM response bound')
        raw, self.buffer = self.buffer.split(b'\n', 1)
        return m.strict_json(raw)

    def read(self):
        try:
            while True:
                response = self.line(self.deadline)
                with self.lock:
                    op_id = response['opId']; m.need(op_id in self.pending, 'guest duplicate/unknown operation result')
                    future = self.pending.pop(op_id)
                future.set_result(response)
        except BaseException as error:
            with self.lock:
                self.failed = error
                for future in self.pending.values(): future.set_exception(error)
                self.pending.clear()

    def command(self, name, **values):
        with self.lock:
            m.need(self.failed is None and not self.closed and len(self.rows) < 2000, 'guest JVM unavailable/command bound')
            request = dict(command=name, opId=f'{self.node}-g1-{len(self.rows)+1}', **values)
            row = dict(request=request, startNanos=time.monotonic_ns(), outcome='PENDING'); self.rows.append(row)
            future = Future(); self.pending[request['opId']] = future
            self.proc.stdin.write(m.canonical(request)+b'\n'); self.proc.stdin.flush()
        try:
            response = future.result(timeout=max(.001, min(12, self.deadline-time.monotonic())))
            row.update(response=response, endNanos=time.monotonic_ns(), outcome=response['outcome'])
            m.need(all(response[k] == v for k, v in dict(command=name, opId=request['opId'], node=self.node, pid=self.proc.pid).items()), 'guest JVM operation identity')
            m.need(response['outcome'] == 'SUCCESS', 'guest JVM command failed: '+str(response))
            return response
        except BaseException as error:
            row.update(endNanos=time.monotonic_ns(), failure=dict(type=type(error).__name__, message=str(error)[:2000])); raise

    def streams_close(self):
        for stream in (self.proc.stdin, self.proc.stdout, self.stderr):
            try: stream.close()
            except BrokenPipeError: pass

    def stop(self, forced=False):
        if self.closed: return
        failure = None
        try:
            if self.proc.poll() is None and not forced: self.command('close')
            if self.proc.poll() is None and forced: self.proc.kill()
            self.proc.wait(timeout=10)
            m.need(forced or self.proc.returncode == 0, 'guest JVM abnormal close')
        except BaseException as error: failure = error
        finally:
            if self.proc.poll() is None: self.proc.kill(); self.proc.wait(timeout=5)
            self.reader.join(timeout=5); self.closed = True; self.streams_close()
            write_once(self.root/(self.node+'-exchanges.json'), self.rows)
            write_once(self.root/(self.node+'-stop.json'), dict(**self.identity, exitCode=self.proc.returncode, forced=forced or failure is not None,
                       readerReaped=not self.reader.is_alive()))
        m.need(not self.reader.is_alive(), 'guest JVM reader remains active')
        if failure: raise failure
