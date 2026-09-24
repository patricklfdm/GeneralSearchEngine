"""Persistent local guest JVM pipes with concurrent, identity-bound responses."""
from concurrent.futures import Future
import os
import threading
import time
from . import performance_harness as base, performance_model as m


class Worker(base.Worker):
    def __init__(self,*args,**kwargs):
        self.lock=threading.Lock()
        self.pending={}
        self.reader_failure=None
        self.reader=None
        super().__init__(*args,**kwargs)
        self.reader=threading.Thread(target=self._read,name='guest-replies-'+self.node,daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while True:
                while b'\n' not in self.buffer:
                    data=os.read(self.proc.stdout.fileno(),65536)
                    if not data:
                        with self.lock:
                            if self.pending:raise EOFError('guest exited with pending commands')
                        return
                    self.buffer+=data
                    m.need(len(self.buffer)<=4<<20,'guest reply bound')
                raw,self.buffer=self.buffer.split(b'\n',1)
                response=m.strict_json(raw)
                with self.lock:
                    op_id=response['opId']
                    m.need(op_id in self.pending,'unexpected/duplicate guest response')
                    future=self.pending.pop(op_id)
                future.set_result(response)
        except BaseException as error:
            with self.lock:
                self.reader_failure=error
                for future in self.pending.values():future.set_exception(error)
                self.pending.clear()

    def command(self,name,**values):
        with self.lock:
            m.need(self.reader_failure is None,'guest pipe reader failed: '+str(self.reader_failure))
            request=dict(command=name,opId=f'{self.node}-g1-{len(self.record["exchanges"])+1}',**values)
            row=dict(request=request,startNanos=time.monotonic_ns(),outcome='PENDING')
            self.record['exchanges'].append(row)
            future=Future();self.pending[request['opId']]=future
            self.proc.stdin.write(m.canonical(request)+b'\n');self.proc.stdin.flush()
        try:
            result=future.result(timeout=self.run.remaining(12))
            row.update(endNanos=time.monotonic_ns(),response=result,outcome=result['outcome'])
            m.need(all(result[k]==v for k,v in dict(command=name,opId=request['opId'],node=self.node,pid=self.proc.pid).items()),'guest response identity')
            m.need(result['outcome']=='SUCCESS','guest command failed: '+str(result))
            return result
        except BaseException as error:
            row.update(endNanos=time.monotonic_ns(),failure=dict(type=type(error).__name__,message=str(error)))
            raise

    def stop(self,failed=False):
        try:super().stop(failed)
        finally:
            if self.reader is not None:
                self.reader.join(timeout=5)
                m.need(not self.reader.is_alive(),'guest reader not reaped')
