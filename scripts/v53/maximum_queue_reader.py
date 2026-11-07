"""One fresh-process whole native replay, with measured process high-water RSS.

Memory is an observation of this complete execution, not a frozen runtime budget
or a claim about every possible input. No replay retry or size fallback exists.
"""
import argparse
import os
from pathlib import Path
import resource
import sys
import time
from . import queue_completion_run as m
from . import maximum_transition_capacity as capacity
from .maximum_native_reader import proc_peak

SCHEMA='gse-v53-maximum-queue-reader-observation-v1'
PROFILE=m.MAXIMUM_PROFILE
need=m.need


def run(output,producer,pins):
    output=Path(output)
    need(not output.resolve().is_relative_to(Path(producer).resolve()),'maximum queue measurement original separation')
    output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic_ns();cpu=time.process_time_ns()
    value=dict(schema=SCHEMA,status='FAIL',profile=PROFILE,processId=os.getpid(),
               scope='fresh-process-whole-resource-verification',retries=0,
               wholeReaderMemoryQualified=False,phase3Complete=False)
    try:
        need(sys.platform=='linux','maximum queue reader Linux RSS units')
        m.verify(output/'verification',producer,PROFILE,pins)
        value['status']='PASS'
    except BaseException as error:
        value['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        failing=sys.exc_info()[0] is not None
        value.update(elapsedNanos=time.monotonic_ns()-start,cpuNanos=time.process_time_ns()-cpu)
        receipt=output/'verification/receipt.json'
        value['verificationReceiptSha256']=m.tc.file_hash(receipt) if receipt.is_file() else None
        try:
            raw=Path('/proc/self/status').read_bytes();peak=proc_peak(raw,os.getpid())
            (output/'memory-status.txt').write_bytes(raw)
            value.update(peakRssBytes=peak,procStatusSha256=m.h.digest(raw),rssSource='/proc/self/status:VmHWM',
                         rusagePeakRssBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        except BaseException as error:
            value.update(status='FAIL',measurementFailure=dict(type=type(error).__name__,message=str(error)))
            if not failing:raise
        finally:m.h.save(output/'memory.json',value)
    return value


def result(output,pins):
    """Validate the complete child result and exact measurement/result binding."""
    m.check_pins(pins)
    output=Path(output);value=m.read(output/'memory.json')
    fields={'schema','status','profile','processId','scope','retries','wholeReaderMemoryQualified','phase3Complete',
            'elapsedNanos','cpuNanos','peakRssBytes','verificationReceiptSha256','procStatusSha256','rssSource','rusagePeakRssBytes'}
    need(type(value) is dict and set(value)==fields and value['schema']==SCHEMA and value['status']=='PASS' and
         value['profile']==PROFILE and value['scope']=='fresh-process-whole-resource-verification' and
         type(value['retries']) is int and value['retries']==0 and
         all(type(value[k]) is int and value[k]>0 for k in ('processId','elapsedNanos','peakRssBytes','rusagePeakRssBytes')) and
         value['rssSource']=='/proc/self/status:VmHWM' and
         type(value['cpuNanos']) is int and value['cpuNanos']>=0 and
         value['wholeReaderMemoryQualified'] is False and value['phase3Complete'] is False,
         'maximum queue complete reader measurement')
    raw=m.h.snapshot.s.regular(output/'memory-status.txt',16384)
    need(m.h.digest(raw)==value['procStatusSha256'] and proc_peak(raw,value['processId'])==value['peakRssBytes'],
         'maximum queue measured proc status binding')
    path=output/'verification/receipt.json';qualified=m.read(path)
    need(value['verificationReceiptSha256']==m.tc.file_hash(path),'maximum queue measurement result binding')
    need(type(qualified) is dict and qualified.get('schema')==m.MAXIMUM_SCHEMA and qualified.get('status')=='PASS' and qualified.get('profile')==PROFILE and
         qualified.get('scope')=='maximum-image-joint-queue-component-only' and
         all(qualified.get(k)==v for k,v in pins.items()) and
         all(qualified.get(k) is True for k in ('originalFirst','originalPreserved','queuePressureQualified','nativeFinalCompleted')) and
         all(qualified.get(k) is False for k in ('combinedResourcesQualified','phase3Complete')),
         'maximum queue measured qualification scope')
    m.check_result(qualified.get('qualification'),PROFILE)
    capacity.validate(qualified.get('verificationCapacity'),'verify')
    need(all(m.shared.hash_field(qualified.get(k)) for k in ('producerReceiptSha256','rawInventorySha256')),
         'maximum queue measured original binding')
    return qualified,value


def observe(output,producer,pins):
    """Use one child, so prior preparation/parent peaks cannot contaminate RSS."""
    m.check_pins(pins)
    output=Path(output).absolute();producer=Path(producer).absolute()
    need(not output.resolve().is_relative_to(producer.resolve()),'maximum queue measurement original separation')
    output.mkdir(parents=True,exist_ok=False);m.h.save(output/'pins.json',pins)
    command=[sys.executable,'-B','-m','scripts.v53.maximum_queue_reader',str(output/'reader'),
             '--producer',str(producer),'--pins',str(output/'pins.json')]
    execution=m.h.execute(command,m.h.ROOT,output/'reader.log',stage='maximum-queue-whole-reader')
    m.h.save(output/'execution.json',dict(command=command,**execution))
    need(type(execution.get('exit')) is int and execution['exit']==0,
         'maximum queue reader process failed; observations retained')
    need(m.read(output/'pins.json')==pins,'maximum queue measurement pins changed')
    m.check_pins(pins)
    return result(output/'reader',pins)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--producer',required=True);p.add_argument('--pins',required=True)
    a=p.parse_args();run(a.output,a.producer,m.read(a.pins))
