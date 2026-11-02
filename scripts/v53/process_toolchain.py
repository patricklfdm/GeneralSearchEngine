"""Stable tool identities with original per-host diagnostics retained separately."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from . import joining_history_run as h

SCHEMA='gse-v53-process-toolchain-v2'
PROPERTIES=('java.version','java.runtime.version','java.vendor','java.vm.name','java.vm.version','os.arch','os.name')


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def paths(stdout):
    text=re.sub(r'\x1b\[[0-9;]*m','',stdout)
    homes=re.findall(r'^Maven home: (.+)$',text,re.M)
    java=re.findall(r'^Java version: (.+?), vendor: (.+?), runtime: (.+)$',text,re.M)
    versions=re.findall(r'^Apache Maven (.+)$',text,re.M)
    h.need(len(homes)==len(java)==len(versions)==1,'process toolchain exact version output')
    return dict(maven=versions[0],mavenHome=homes[0],javaVersion=java[0][0],javaVendor=java[0][1],javaHome=java[0][2])


def capture(maven,work):
    version=subprocess.run([str(maven),'-version'],cwd=work,text=True,capture_output=True,timeout=30)
    h.need(version.returncode==0,'process toolchain Maven unavailable');locations=paths(version.stdout)
    java_home=Path(locations['javaHome']);maven_home=Path(locations['mavenHome'])
    java=subprocess.run([str(java_home/'bin/java'),'-XshowSettings:properties','-version'],cwd=work,text=True,capture_output=True,timeout=30)
    h.need(java.returncode==0,'process toolchain Java unavailable')
    props={}
    for key in PROPERTIES:
        found=re.findall(r'^\s*'+re.escape(key)+r' = (.+)$',java.stderr,re.M)
        h.need(len(found)==1,'process toolchain Java property: '+key);props[key]=found[0]
    h.need(props['java.version']==locations['javaVersion'] and props['java.vendor']==locations['javaVendor'],
           'process toolchain Maven/Java mismatch')
    # Hash executable/runtime and actual Maven libraries, not installation paths
    # or a claimed version alone. Kernel/path diagnostics remain in stdout.
    binaries={'java/bin/java':file_hash(java_home/'bin/java'),'java/lib/modules':file_hash(java_home/'lib/modules')}
    for sub in ('bin','boot','lib'):
        for path in sorted((maven_home/sub).rglob('*')):
            if path.is_file():binaries['maven/'+path.relative_to(maven_home).as_posix()]=file_hash(path)
    result=dict(schema=SCHEMA,exit=0,stdout=version.stdout,stderr=version.stderr,javaDiagnostics=java.stderr,
                identity=dict(schema=SCHEMA,maven=locations['maven'],java=props,binaries=binaries))
    validate(result);return result


def validate(value):
    h.need(type(value) is dict and set(value)=={'schema','exit','stdout','stderr','javaDiagnostics','identity'} and
           value['schema']==SCHEMA and type(value['exit']) is int and value['exit']==0 and
           all(type(value[k]) is str for k in ('stdout','stderr','javaDiagnostics')),'process toolchain record')
    identity=value['identity'];h.need(type(identity) is dict and set(identity)=={'schema','maven','java','binaries'} and
        identity['schema']==SCHEMA and type(identity['java']) is dict and set(identity['java'])==set(PROPERTIES),
        'process toolchain identity')
    locations=paths(value['stdout']);props=identity['java']
    h.need(identity['maven']==locations['maven'] and props['java.version']==locations['javaVersion'] and
           props['java.vendor']==locations['javaVendor'],'process toolchain diagnostic binding')
    for key,text in props.items():
        h.need(type(text) is str and re.findall(r'^\s*'+re.escape(key)+r' = (.+)$',value['javaDiagnostics'],re.M)==[text],
               'process toolchain property binding')
    binaries=identity['binaries'];h.need(type(binaries) is dict and 4<=len(binaries)<=256 and
        {'java/bin/java','java/lib/modules','maven/bin/mvn'}<=set(binaries) and
        any(k.startswith('maven/lib/') for k in binaries),'process toolchain binary inventory')
    for name,digest in binaries.items():
        path=Path(name);h.need(not path.is_absolute() and path.as_posix()==name and '..' not in path.parts and
            (name in ('java/bin/java','java/lib/modules') or name.startswith(('maven/bin/','maven/boot/','maven/lib/'))) and
            type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest),'process toolchain binary hash')
    return identity


def pin(raw):
    value=json.loads(raw)
    if value.get('schema')==SCHEMA:return h.digest(h.snapshot.f.canonical(validate(value)))
    h.need(set(value)=={'exit','stdout','stderr'} and type(value['exit']) is int and value['exit']==0 and
        all(type(value[k]) is str for k in ('stdout','stderr')),'process toolchain legacy record')
    return h.digest(raw)


def locate(wrapper,work):
    value=subprocess.run([str(wrapper),'-version'],cwd=work,text=True,capture_output=True,timeout=300)
    h.need(value.returncode==0,'process Maven wrapper initialization')
    maven=Path(paths(value.stdout)['mavenHome'])/'bin/mvn'
    h.need(maven.is_file(),'process Maven executable missing');return str(maven)
