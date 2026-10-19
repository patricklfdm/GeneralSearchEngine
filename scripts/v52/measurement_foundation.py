"""Compile one closed query program against both cores; no replica timing claims."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from scripts.v51 import public_qualification_harness as q
from . import controls,measurement_model as model,measurement_oracle as oracle,measurement_close
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v52-measurement-foundation-v1',status='FAIL',execution='core-query-foundation-only',measured=False,paidCloud=False)
    try:
        receipt['program']=model.load();receipt['binding']=build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        control=controls.resolve(ROOT/'target/v52-controls');receipt['controls']=control
        inputs=root/'inputs';inputs.mkdir();calls=model.program()
        for name,value in (('corpus.json',model.corpus()),('calls.json',calls),('queries.json',model.queries())):
            (inputs/name).write_bytes(encoded(value)+b'\n')
        sources=[ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                 ROOT/'scripts/v52/java/V52ReadQueries.java',ROOT/'scripts/v52/java/V52MeasurementQueries.java',ROOT/'scripts/v52/java/V52MeasurementOracle.java']
        modes={'published-v44':ROOT/'target/v52-controls/general-search-engine-4.4.0.jar','candidate-core':ROOT/f'target/general-search-engine-{current()}.jar'}
        results={};receipt['artifacts']={};receipt['classes']={}
        for name,source in modes.items():
            own=root/name;own.mkdir();jar=own/source.name;shutil.copyfile(source,jar);receipt['artifacts'][name]=dict(path=str(jar),sha256=digest(jar.read_bytes()))
            classes=own/'classes';classes.mkdir()
            q.command(['javac','--release','21','-proc:none','-cp',jar,'-d',classes,*sources],own,'compile')
            receipt['classes'][name]={p.relative_to(classes).as_posix():digest(p.read_bytes()) for p in sorted(classes.rglob('*.class'))}
            result=q.command(['java','-cp',os.pathsep.join((str(classes),str(jar))),PACKAGE+'V52MeasurementQueries',own/'run',inputs],own,'query-foundation')
            need(result.stderr.strip()=='coreSource='+str(jar),'measurement core loaded from wrong artifact')
            value=json.loads(result.stdout);need(value['status']=='PASS' and value['measured'] is False,'measurement foundation result')
            need([v['sequence'] for v in value['states']]==[1,2,65,66,181],'measurement query state set')
            for state in value['states']:
                prefix=[r for r in calls if r['kind']=='update' and r['ordinal']<state['sequence']-1]
                expected=model.projection(prefix);need(state['documents']==expected['documents'],'measurement corpus/update projection differs')
                need([r['query'] for r in state['answers']]==model.queries(),'measurement query descriptor set')
            oracle_input=oracle.prepare([dict(sequence=state['sequence'],query=answer['query']) for state in value['states'] for answer in state['answers']],
                                        [r['document'] for r in calls if r['kind']=='update'])
            (own/'oracle-input.json').write_bytes(encoded(oracle_input)+b'\n')
            replay=q.command(['java','-cp',os.pathsep.join((str(classes),str(jar))),PACKAGE+'V52MeasurementOracle',own/'oracle',own/'oracle-input.json'],own,'oracle')
            need(replay.stderr.strip()=='coreSource='+str(jar),'measurement oracle loaded wrong artifact')
            need(json.loads(replay.stdout)==dict(status='PASS',measured=False,requests=690,updatesApplied=180,finalSequence=181),'measurement oracle execution incomplete')
            answers=oracle.validate_output(oracle_input,own/'oracle/answers.jsonl')
            need(answers=={oracle.key(state['sequence'],answer['query']):answer['answer'] for state in value['states'] for answer in state['answers']},
                 'persistent measurement oracle differs from direct core query execution')
            sparse_input=oracle.prepare_selected([dict(sequence=sequence,query=query) for sequence in range(1,7) for query in model.queries()],
                                                [0,2,65,130,179])
            (own/'selected-input.json').write_bytes(encoded(sparse_input)+b'\n')
            replay=q.command(['java','-cp',os.pathsep.join((str(classes),str(jar))),PACKAGE+'V52MeasurementOracle',own/'selected',own/'selected-input.json'],own,'selected')
            need(replay.stderr.strip()=='coreSource='+str(jar),'selected oracle loaded wrong artifact')
            need(json.loads(replay.stdout)==dict(status='PASS',measured=False,requests=828,updatesApplied=5,finalSequence=6),'selected oracle incomplete')
            selected=oracle.validate_output(sparse_input,own/'selected/answers.jsonl')
            value['selectedAnswers']=selected
            # Last successful reads need not observe the terminal chosen update.
            # Exercise both input schemas without inventing a terminal read.
            for label,complete,known,through in (('prefix-tail',oracle_input,answers,1),('selected-tail',sparse_input,selected,5)):
                tail=dict(complete,requests=[row for row in complete['requests'] if row['sequence']<=through])
                oracle.validate(tail);input_path=own/(label+'-input.json');input_path.write_bytes(encoded(tail)+b'\n')
                replay=q.command(['java','-cp',os.pathsep.join((str(classes),str(jar))),PACKAGE+'V52MeasurementOracle',own/label,input_path],own,label)
                need(replay.stderr.strip()=='coreSource='+str(jar),'tail oracle loaded wrong artifact')
                need(json.loads(replay.stdout)==dict(status='PASS',measured=False,requests=len(tail['requests']),
                     updatesApplied=len(tail['updates']),finalSequence=1+len(tail['updates'])),'tail oracle execution incomplete: '+label)
                need(oracle.validate_output(tail,own/label/'answers.jsonl')=={r['key']:known[r['key']] for r in tail['requests']},
                     'tail updates changed earlier query answers: '+label)
            results[name]=value
        need(results['published-v44']==results['candidate-core'],'candidate queries differ from actual published core')
        receipt['consumerClose']=measurement_close.run(root/'consumer-close')
        receipt.update(status='PASS',states=5,queriesPerCore=5*len(model.queries()),updatesPerCore=180,persistentOracleQueriesPerCore=690,selectedOracleQueriesPerCore=828,
                       terminalUpdateCasesPerCore=2)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(root/'receipt.json').write_bytes(encoded(receipt)+b'\n')
    print(json.dumps({k:receipt[k] for k in ('status','execution','measured','states','queriesPerCore')}),flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
