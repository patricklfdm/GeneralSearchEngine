"""Local receiver bootstrap/relocation qualification only; no voters or GCP."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from scripts.v51 import public_qualification_harness as q, storage_inspector as storage
from . import controls, measurement_model as model, measurement_bundle as bundle
from . import remote_topology as topology, remote_bootstrap_evidence as evidence
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


def save(path,value):path.write_bytes(encoded(value)+b'\n')


def check_topology_parity(root, cp):
    """Both compiled controls must reject malformed inputs for the same reasons."""
    import copy
    base=dict(schema=topology.SCHEMA,placement='local-no-gcp',groupId=str(uuid.uuid4()),
              members=[dict(node=node,host='127.0.0.1',port=25001+i) for i,node in enumerate(topology.NODES)])
    cases=[('local',base,True)]
    private=copy.deepcopy(base);private['placement']='owned-private-hosts'
    for row,host in zip(private['members'],('10.1.0.1','172.16.0.2','192.168.0.3')):row['host']=host
    cases.append(('private',private,True))
    edits=[('public-host',lambda v:v['members'][0].__setitem__('host','8.8.8.8')),
           ('metadata-host',lambda v:v['members'][0].__setitem__('host','169.254.169.254')),
           ('dns-host',lambda v:v['members'][0].__setitem__('host','localhost')),
           ('leading-zero-host',lambda v:v['members'][0].__setitem__('host','127.00.0.1')),
           ('ipv6',lambda v:v['members'][0].__setitem__('host','::1')),
           ('port-bool',lambda v:v['members'][0].__setitem__('port',True)),
           ('port-float',lambda v:v['members'][0].__setitem__('port',25001.0)),
           ('port-low',lambda v:v['members'][0].__setitem__('port',1023)),
           ('port-high',lambda v:v['members'][0].__setitem__('port',65536)),
           ('duplicate-endpoint',lambda v:v['members'][1].__setitem__('port',25001)),
           ('voter-order',lambda v:v['members'].reverse()),
           ('missing-voter',lambda v:v['members'].pop()),
           ('unknown-field',lambda v:v.__setitem__('provider','gcp')),
           ('wrong-schema',lambda v:v.__setitem__('schema','other')),
           ('unknown-placement',lambda v:v.__setitem__('placement','production')),
           ('nil-group',lambda v:v.__setitem__('groupId','00000000-0000-0000-0000-000000000000')),
           ('uppercase-group',lambda v:v.__setitem__('groupId',v['groupId'].upper()))]
    for name,edit in edits:
        value=copy.deepcopy(base);edit(value);cases.append((name,value,False))
    repeated=copy.deepcopy(private);repeated['members'][1]['host']=repeated['members'][0]['host'];cases.append(('private-same-host',repeated,False))
    folder=root/'topology-fixtures';folder.mkdir();results=[]
    for name,value,accepted in cases:
        case=folder/name;case.mkdir();save(case/topology.FILE,value)
        try:parsed=topology.read(case);python_ok=True
        except ValueError:python_ok=False
        process=subprocess.run(['java','-cp',cp,PACKAGE+'V52RemoteTopology',str(case)],capture_output=True,timeout=35)
        (case/'stdout').write_bytes(process.stdout);(case/'stderr').write_bytes(process.stderr)
        need(python_ok==accepted and (process.returncode==0)==accepted,'remote topology parser disagreement: '+name)
        if accepted:need(json.loads(process.stdout)==parsed==value,'remote topology parsed bytes differ')
        else:need(b'remote topology' in process.stderr or b'JSON' in process.stderr,'remote topology unrelated rejection')
        results.append(dict(case=name,status='ACCEPTED' if accepted else 'REJECTED'))
    return results


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='receiver-bootstrap-and-relocation-only',qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False,votersStarted=0,receivers=[])
    try:
        receipt['binding']=build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        controls.resolve(ROOT/'target/v52-controls');model.load()
        java=ROOT/'scripts/v52/java';common=[ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                                           java/'V52ReadQueries.java',java/'V52MeasurementQueries.java']
        seed=output/'seed-source';seed.mkdir();classes=seed/'classes';classes.mkdir()
        jar=ROOT/'target/v52-controls/general-search-engine-4.4.0.jar'
        q.command(['javac','--release','21','-proc:none','-cp',jar,'-d',classes,*common,java/'V52MeasurementSeed.java'],seed,'compile')
        save(seed/'corpus.json',model.corpus());control=q.command(['java','-cp',os.pathsep.join(map(str,(jar,classes))),PACKAGE+'V52MeasurementSeed',seed/'control',seed/'corpus.json'],seed,'seed')
        need(control.stderr.strip()=='coreSource='+str(jar) and json.loads(control.stdout)==dict(status='PASS',documents=64,sequence=1),'remote seed control identity')
        original_seed=bundle.members(seed/'control/seed');receipt['sourceBackupSha256']=digest(encoded(original_seed));receipt['families']={}
        for family,version in (('published','5.1.0'),('candidate',current())):
            root=output/family;root.mkdir();artifacts=root/'artifacts';artifacts.mkdir();classes=root/'classes';classes.mkdir();jars=[]
            for artifact in ('general-search-engine','general-search-engine-replication'):
                source=(ROOT/'target/v52-controls' if family=='published' else ROOT/('target' if artifact=='general-search-engine' else artifact+'/target'))/(artifact+'-'+version+'.jar')
                target=artifacts/source.name;shutil.copyfile(source,target);jars.append(target)
            cp=os.pathsep.join(map(str,(*jars,classes)))
            q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,*common,java/'V52MeasurementConfiguration.java',
                       java/'V52RemoteTopology.java',java/'V52RemoteBootstrap.java'],root,'compile')
            parity=check_topology_parity(root,cp)
            plan=dict(schema=topology.SCHEMA,placement='local-no-gcp',groupId=str(uuid.uuid4()),
                      members=[dict(node=node,host='127.0.0.1',port=25001+i) for i,node in enumerate(topology.NODES)])
            topology.validate(plan);bindings={};inspected={};collected=root/'collected';collected.mkdir()
            for node in topology.NODES:
                own=root/'receivers'/node;own.mkdir(parents=True);save(own/topology.FILE,plan)
                shutil.copytree(seed/'control/seed',own/'control/seed')
                result=q.command(['java','-cp',cp,PACKAGE+'V52RemoteBootstrap',own,node],own,'bootstrap');answer=json.loads(result.stdout)
                need(answer['status']=='PREPARED_NOT_STARTED' and answer['node']==node and answer['originalRoot']==str(own) and answer['topology']==plan,
                     'remote bootstrap response identity')
                need(answer['coreSource']==str(jars[0]) and answer['replicationSource']==str(jars[1]),'remote bootstrap loaded artifact')
                need(bundle.members(own/'control/seed')==original_seed,'remote bootstrap changed source')
                need({p.name for p in own.iterdir() if p.name in topology.NODES}=={node},'remote bootstrap retained live siblings')
                inspected[node]=storage.inspect(own/node)
                need(inspected[node]['node']==node and inspected[node]['applicationSequence']==1 and inspected[node]['provenThrough']==0,
                     'remote receiver bootstrap authority')
                bindings[node]={key:answer[key] for key in ('originalRoot','manifestSha256','genesisSha256')}
                shutil.copytree(own/node,collected/node);receipt['receivers'].append(dict(family=family,node=node))
                # A second preparation is an error, never an implicit repair/resume.
                again=subprocess.run(['java','-cp',cp,PACKAGE+'V52RemoteBootstrap',str(own),node],capture_output=True,timeout=35)
                (own/'duplicate.stderr').write_bytes(again.stderr)
                need(again.returncode!=0 and b'remote bootstrap consumed destination' in again.stderr,'remote duplicate bootstrap accepted')
            save(root/'receiver-bindings.json',bindings);save(collected/bundle.INDEX,bundle.members(collected))
            location=evidence.EvidenceLocation(collected,bindings)
            original={node:location.inspect(collected/node) for node in topology.NODES};need(original==inspected,'remote collected authority drift')
            archive=root/'authority.tar.gz';bundle.pack(collected,archive);relocated=bundle.unpack(archive,root/'relocated')
            location=evidence.EvidenceLocation(relocated,bindings)
            portable={node:location.inspect(relocated/node) for node in topology.NODES};need(portable==original,'remote relocated authority drift')
            rejected=[]
            for node in topology.NODES:
                wrong={n:dict(v) for n,v in bindings.items()};wrong[node]['originalRoot']+='/wrong'
                try:evidence.EvidenceLocation(relocated,wrong).inspect(relocated/node)
                except ValueError as error:need(str(error)=='copied/stale seal path','remote negative rejected at unrelated check')
                else:raise ValueError('remote copied seal accepted')
                rejected.append(dict(case='wrong-original-root-'+node,reason='copied/stale seal path'))
            receipt['families'][family]=dict(artifacts={p.name:bundle.sha_file(p) for p in jars},
                classes={p.relative_to(classes).as_posix():bundle.sha_file(p) for p in classes.rglob('*.class')},
                topologyParity=parity,receiverBindings=bindings,physical=original,archiveSha256=bundle.sha_file(archive),negatives=rejected)
        receipt['status']='PASS';return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(output/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();result=run(args.output)
    print(json.dumps({k:result[k] for k in ('status','execution','qualifiedMeasurement','fullRemoteQualification','paidCloud','votersStarted')}))
