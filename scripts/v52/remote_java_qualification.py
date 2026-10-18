"""Actual jlink, pinned OpenSSH installation and one complete original history.

Loopback processes only: neither independent hosts nor cloud qualification.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from . import remote_java_evidence as j,remote_python_runtime_qualification as q


def probes(context,parent,output):
    from . import remote_python_context as python
    bad=output/'ambient-java';bad.mkdir(mode=0o700)
    (bad/'java').write_text('#!/bin/sh\nexit 99\n');(bad/'java').chmod(0o700)
    env=dict(os.environ,PATH=str(bad),JAVA_TOOL_OPTIONS='-invalid-ambient-option')
    selected=python.command(context,'delivery',['probe',parent],python=sys.executable)
    result=subprocess.run(selected,input=b'',capture_output=True,env=env,timeout=60)
    (output/'java-selected-probe.stderr').write_bytes(result.stderr)
    q.need(result.returncode==0 and set(json.loads(result.stdout))=={'host'},'Java explicit runtime ignored/ambient environment leaked')
    wrong=dict(context,java=dict(context['java'],descriptorSha256='0'*64))
    result=subprocess.run(python.command(wrong,'delivery',['probe',parent],python=sys.executable),input=b'',capture_output=True,timeout=60)
    (output/'java-wrong-pin.stderr').write_bytes(result.stderr)
    q.need(result.returncode!=0 and not result.stdout and b'Java original source/descriptor changed' in result.stderr,'Java wrong external pin accepted')


def negatives(owner,*,locations):
    cases={
        'changed-java-bytes':(lambda p:q.previous.change_byte(p/j.ARCHIVE),'Java retained archive hash'),
        'missing-java-bytes':(lambda p:(p/j.ARCHIVE).unlink(),None),
        'missing-java-process':(lambda p:(p/'node-1-control/java-process.json').unlink(),None),
        'changed-java-source':(lambda p:q.previous.change(p/j.FILE,lambda v:v['source'].update(source='0'*40)),'Java retained original source changed'),
        'ambient-java':(lambda p:q.previous.change(p/'node-1-control/java-process.json',lambda v:v.update(executable='/usr/bin/java')),'Java retained process executable changed'),
        'changed-java-start':(lambda p:q.previous.change(p/'node-2-control/java-process.json',lambda v:v['process'].update(startTicks=1)),'Java retained process executable changed'),
        'changed-java-selection':(lambda p:q.previous.change(p/'node-3-control/python-runtime.json',lambda v:v['java']['selection'].update(root='/usr')),'Java retained runtime selection'),
        'missing-bootstrap-selection':(lambda p:q.previous.change(p/'node-1-python-bootstrap.json',lambda v:v.pop('java')),'Python retained runtime identity'),
    }
    results=[]
    for location in locations:
        q.evidence.validate(owner.root/location,owner.binding)
        for name,(mutate,reason) in cases.items():
            root=owner.root/'java-negatives'/location/name;shutil.copytree(owner.root/location,root)
            mutate(root);q.h.runtime.save(root/q.h.bundle.INDEX,q.h.bundle.members(root))
            try:q.evidence.validate(root,owner.binding)
            except (ValueError,FileNotFoundError) as error:
                q.need(reason is None and isinstance(error,FileNotFoundError) or str(error)==reason,'Java unrelated negative: '+name+': '+str(error))
                results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('Java negative accepted: '+name)
            shutil.rmtree(root)
    q.h.runtime.save(owner.root/'java-negatives/results.json',results);return results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
    print(json.dumps(q.run(args.output,java_runtime=True)),flush=True)
