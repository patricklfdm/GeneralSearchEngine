"""Actual public backup exported from one group and imported into a distinct group."""
import argparse
import json
from pathlib import Path
import tempfile
import shutil
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_import_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name,backup=None,old=None):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    try:
        (root/'promise-evidence').touch()
        if name=='backup-import':(root/'group-id.txt').write_text('22222222-2222-2222-2222-222222222222')
        binding,cp=healthy.prepare(root,scenario=name,backup=backup);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history,keys=(100,110,120) if backup else (20,30,40))
        details['carriedOp']=carried['opId']
        if name=='backup-export':details['backupOp']=active.call('backup')['opId']
        else:
            details['oldToken']=old['token']
            denied=active.send('read',policy='AT_LEAST_INDEX',minimum=old['token'],waitTimeoutMillis=60000).result(timeout=10)
            need(denied and denied.get('reasonCode')=='INCOMPATIBLE_HISTORY','import accepted old group token: '+str(denied))
            details['deniedOp']=denied['opId']
            details['freshOp']=active.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=60000)['opId']
            absent=root/'token-only';absent.mkdir();shutil.copyfile(root/'ports.txt',absent/'ports.txt')
            # This is a separate no-authority probe; it never runs the observer or
            # supplies a fourth voter to either qualified three-process history.
            result=healthy.q.command(['java','-cp',cp,healthy.PACKAGE+'V52PublicReadConsumer',absent,'token-only',old['token']],root,'token-only')
            save(root/'token-only.json',json.loads(result.stdout))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-import.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'import read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-import-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable import query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable import physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable import rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='public-read-backup-import',paidCloud=False,cases=[])
    try:
        source=root/'backup-export';imported=root/'backup-import'
        for name in checker.CASES:
            old=None
            if name=='backup-import':
                details=evidence.read(source/'read-import.json')
                old=next(a['response'] for a in evidence.read(source/'history.json') if a['opId']==details['carriedOp'])
            result=scenario(root/name,name,source/'backup' if old else None,old)
            item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        receipt['pair']=checker.pair(source,imported)
        need(checker.pair(root/'backup-export-relocated',root/'backup-import-relocated')==receipt['pair'],'relocated backup/import pair differs')
        receipt.update(status='PASS',binding=evidence.read(source/'binding.json'))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();run(a.output)
