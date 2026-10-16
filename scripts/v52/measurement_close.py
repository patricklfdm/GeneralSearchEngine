"""Compile the bounded shutdown probe against published and candidate public APIs."""
import argparse
import json
import os
from pathlib import Path
import shutil
from scripts.build_coordinates import current
from scripts.v51 import public_qualification_harness as q
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]
POLICY=dict(attempts=8,retryWindowMillis=20000,backoffMillis=100,
            retryReason='DEADLINE_EXCEEDED',retryOutcome='NOT_APPLICABLE')
CHECKS=['single-success-and-no-implicit-repeat','timeouts-then-success','attempt-exhaustion-no-ninth-close',
        'window-exhaustion','window-expired-during-backoff','non-timeout-outcome-and-cause-fail-fast',
        'interrupted-close-no-retry','interrupted-backoff-retains-timeout','original-failure-with-clean-cleanup',
        'original-failure-with-exhausted-cleanup','same-timeout-object-no-self-suppression']


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='consumer-close-policy-only',qualifiedMeasurement=False,paidCloud=False,cases={})
    try:
        for family,version in (('published','5.1.0'),('candidate',current())):
            own=root/family;own.mkdir();classes=own/'classes';classes.mkdir();jars=[]
            for artifact in ('general-search-engine','general-search-engine-replication'):
                source=(ROOT/'target/v52-controls' if family=='published' else ROOT/('target' if artifact=='general-search-engine' else artifact+'/target'))/(artifact+'-'+version+'.jar')
                jar=own/source.name;shutil.copyfile(source,jar);jars.append(jar)
            cp=os.pathsep.join(map(str,(*jars,classes)));java=ROOT/'scripts/v52/java'
            sources=[ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                     *(java/name for name in ('V52ReadQueries.java','V52MeasurementQueries.java','V52MeasurementConfiguration.java',
                        'V52MeasurementSampler.java','V52MeasurementConsumer.java','V52MeasurementCloseProbe.java'))]
            q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,*sources],own,'compile')
            result=q.command(['java','-cp',cp,q.PACKAGE+'admission.V52MeasurementCloseProbe'],own,'probe')
            value=json.loads(result.stdout)
            need(value==dict(status='PASS',execution='consumer-close-policy-only',checks=CHECKS,policy=POLICY),'measurement close policy/probe drift')
            receipt['cases'][family]=dict(result=value,artifacts={jar.name:digest(jar.read_bytes()) for jar in jars},
                classes={p.relative_to(classes).as_posix():digest(p.read_bytes()) for p in sorted(classes.rglob('*.class'))})
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(root/'receipt.json').write_bytes(encoded(receipt)+b'\n')
    print(json.dumps(dict(status='PASS',execution=receipt['execution'],checks=len(CHECKS),families=len(receipt['cases']))),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');run(p.parse_args().output)
