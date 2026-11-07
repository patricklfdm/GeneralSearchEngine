"""Bind retained ZIP/bundle bytes to live maximum-workflow observations.

Only GET JSON metadata is fetched. ZIPs and unpacked bundles are explicit local
inputs. This is not an owning physical reader or a Phase 3 closure decision.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import zipfile
from . import maximum_resource_workflows as workflows
from .maximum_transition_inventory import identity,inventory

w=workflows.observed;seeds=w.seeds;need=w.need;h=w.h;tc=seeds.shared.tc
SCHEMA='gse-v53-maximum-resource-artifact-binding-v1'
MAX_ARTIFACTS=4096
ZIP_OVERHEAD=16*1024**2
META_KEYS=('id','name','size_in_bytes','digest','expired','created_at','updated_at','expires_at','workflow_run')


def github(path):
    if not re.fullmatch(r'actions/runs/[1-9][0-9]{0,19}/artifacts\?per_page=100&page=[1-9][0-9]*',path):
        return w.github(path)
    result=subprocess.run(['gh','api','--hostname','github.com','--method','GET',
        '-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2026-03-10',
        'repos/'+w.REPOSITORY+'/'+path],capture_output=True,timeout=30)
    need(result.returncode==0 and 0<len(result.stdout)<=w.MAX_RESPONSE,'maximum artifacts GitHub read failed/oversized')
    return result.stdout


def metadata(value,ctx,name,maximum,now):
    need(type(value) is dict and all(k in value for k in META_KEYS),'maximum artifacts metadata fields')
    w.integer(value['id'],1,10**20-1,'maximum artifacts ID')
    w.integer(value['size_in_bytes'],1,maximum+ZIP_OVERHEAD,'maximum artifacts ZIP size')
    need(value['name']==name and value['expired'] is False and type(value['digest']) is str and
         re.fullmatch(r'sha256:[0-9a-f]{64}',value['digest']),'maximum artifacts name/expiry/digest')
    run=value['workflow_run']
    need(type(run) is dict and type(run.get('id')) is int and run['id']==int(ctx['run']) and
         all(type(run.get(k)) is int and run[k]==w.REPOSITORY_ID for k in ('repository_id','head_repository_id')) and
         run.get('head_sha')==ctx['source'] and run.get('head_branch')==ctx['ref'].removeprefix('refs/heads/'),
         'maximum artifacts repository/run/source')
    need(0<w.stamp(value['created_at'])<=w.stamp(value['updated_at'])<=now<w.stamp(value['expires_at']),
         'maximum artifacts valid retention interval')
    return {k:value[k] for k in META_KEYS}


def observe(value,output,get):
    """Retain every page, including earlier attempt artifacts and diagnostics."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    selected={};inventory={};total_bytes=0;global_ids=set();modules=workflows.adapters()
    for component,ctx in value['cohorts'].items():
        rows=[];count=None;ids=set()
        for page in range(1,(MAX_ARTIFACTS+99)//100+1):
            endpoint=f"actions/runs/{ctx['run']}/artifacts?per_page=100&page={page}";raw=get(endpoint)
            need(type(raw) is bytes and 0<len(raw)<=w.MAX_RESPONSE,'maximum artifacts bounded API bytes')
            total_bytes+=len(raw);need(total_bytes<=128*1024**2,'maximum artifacts observation byte bound')
            path=output/component/f'page-{page}.json';path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(raw)
            inventory[str(path.relative_to(output))]=dict(endpoint=endpoint,bytes=len(raw),sha256=h.digest(raw))
            h.save(output/'api-inventory.json',inventory)
            part=seeds.plan.decode(raw)
            need(type(part) is dict and type(part.get('artifacts')) is list,'maximum artifacts API page')
            total=w.integer(part.get('total_count'),0,MAX_ARTIFACTS,'maximum artifacts page total')
            need(count is None or count==total,'maximum artifacts changed page total');count=total
            need(len(part['artifacts'])==min(100,count-len(rows)),'maximum artifacts truncated/oversized page')
            for row in part['artifacts']:
                need(type(row) is dict,'maximum artifacts row')
                identifier=w.integer(row.get('id'),1,10**20-1,'maximum artifacts ID')
                need(identifier not in ids and identifier not in global_ids,'maximum artifacts duplicate/mixed ID');ids.add(identifier)
            rows.extend(part['artifacts'])
            if len(rows)==count:break
        need(len(rows)==count,'maximum artifacts incomplete pagination');global_ids.update(ids)
        selected[component]={}
        for kind in ('seed','raw'):
            name=workflows.artifact_name(component,ctx,kind);found=[r for r in rows if r.get('name')==name]
            need(len(found)==1,'maximum artifacts exact selected attempt artifact')
            selected[component][kind]=metadata(found[0],ctx,name,modules[component].limit(kind),datetime.now(timezone.utc).timestamp())
        h.save(output/'selected.json',selected)
    return selected


def local_layout(index,zips,bundles):
    value=seeds.read(index);modules=workflows.adapters();workflows.validate_index(value,modules)
    for root in (zips,bundles):
        root=seeds.unlinked(root);need(root.is_dir() and {p.name for p in root.iterdir()}==set(modules),'maximum artifacts exact local components')
    identities={}
    for component,adapter in modules.items():
        zipped=seeds.unlinked(Path(zips)/component);packed=seeds.unlinked(Path(bundles)/component)
        need(zipped.is_dir() and {p.name for p in zipped.iterdir()}=={'seed.zip','raw.zip'} and
             packed.is_dir() and {p.name for p in packed.iterdir()}=={'seed','raw'},'maximum artifacts exact local roles')
        identities[component]={}
        for kind in ('seed','raw'):
            path=seeds.unlinked(zipped/(kind+'.zip'));state=path.lstat()
            need(stat.S_ISREG(state.st_mode) and state.st_nlink==1 and 0<state.st_size<=adapter.limit(kind)+ZIP_OVERHEAD,
                 'maximum artifacts regular bounded ZIP')
            identities[component][kind]=dict(zipIdentity=identity(state),zipSha256=tc.file_hash(path),
                bundle=seeds.bundle_identity(packed/kind,maximum=adapter.limit(kind)))
            need(identity(path.lstat())==identity(state),'maximum artifacts ZIP changed during inventory')
    return value,identities


def zip_binding(path,bundle,row,ctx,adapter,kind):
    """Hash the original ZIP and stream both members without extra extraction."""
    path=seeds.unlinked(path);bundle=seeds.unlinked(bundle);state=path.lstat();maximum=adapter.limit(kind)
    need(stat.S_ISREG(state.st_mode) and state.st_nlink==1 and state.st_size==row['size_in_bytes'] and
         state.st_size<=maximum+ZIP_OVERHEAD and 'sha256:'+tc.file_hash(path)==row['digest'],
         'maximum artifacts API ZIP digest/size binding')
    before=seeds.bundle_identity(bundle,maximum=maximum);manifest=seeds.read(bundle/'manifest.json')
    need(type(manifest) is dict and set(manifest)=={'schema','context','kind','case','inventory','archiveSha256'} and
         manifest['schema']==adapter.SCHEMA and manifest['context']==ctx and manifest['kind']==kind and manifest['case']==adapter.PROFILE,
         'maximum artifacts inner workflow/profile binding')
    wanted={'manifest.json':before['manifestSha256'],'bundle.tar.gz':before['archiveSha256']}
    with zipfile.ZipFile(path) as archive:
        members=archive.infolist()
        need(len(members)==2 and {v.filename for v in members}==set(wanted),'maximum artifacts exact ZIP members')
        for item in members:
            limit=8*1024**2 if item.filename=='manifest.json' else maximum
            need(not item.is_dir() and not item.flag_bits&1 and stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG) and
                 item.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and
                 0<item.file_size<=limit and item.file_size==(bundle/item.filename).stat().st_size,
                 'maximum artifacts regular bounded ZIP member')
            digest=hashlib.sha256();count=0
            with archive.open(item) as stream:
                while True:
                    block=stream.read(1024**2)
                    if not block:break
                    count+=len(block);need(count<=item.file_size,'maximum artifacts expanded ZIP bound');digest.update(block)
            need(count==item.file_size and digest.hexdigest()==wanted[item.filename],'maximum artifacts ZIP differs from retained bundle')
    need(identity(path.lstat())==identity(state) and seeds.bundle_identity(bundle,maximum=maximum)==before,
         'maximum artifacts input changed during ZIP binding')
    return dict(artifactId=row['id'],artifactName=row['name'],zipSha256=row['digest'][7:],zipBytes=state.st_size,**before)


def bind(index,zips,bundles,output,get=github):
    index,zips,bundles,output=map(seeds.unlinked,(index,zips,bundles,output))
    need(not index.is_relative_to(output) and all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in (zips,bundles)),
         'maximum artifacts output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',workflowExecutionAttested=False,artifactBytesBound=False,
                 originalHistoriesReplayed=False,priorFailuresResolved=False,combinedResourcesQualified=False,phase3Complete=False)
    try:
        before=local_layout(index,zips,bundles);value,inputs=before;raw=seeds.read_bytes(index);(output/'index.json').write_bytes(raw)
        h.save(output/'local-inputs.json',inputs)
        first=workflows.collect(index,output/'workflow-before',get)
        need(first.get('schema')==workflows.SCHEMA and first.get('status')=='PARTIAL' and
             first.get('workflowExecutionAttested') is True and first.get('phase3Complete') is False and
             first.get('source')==value['source'] and first.get('indexSha256')==h.digest(raw),
             'maximum artifacts observed workflow prerequisite')
        snapshots={'workflow-before':inventory(output/'workflow-before',maximum=1024**3)}
        observed=observe(value,output/'artifacts-before',get)
        snapshots['artifacts-before']=inventory(output/'artifacts-before',maximum=1024**3)
        bound={};modules=workflows.adapters()
        for component,adapter in modules.items():
            bound[component]={}
            for kind in ('seed','raw'):
                with seeds.shared.progress('maximum-artifact-byte-binding',component+'-'+kind):
                    bound[component][kind]=zip_binding(zips/component/(kind+'.zip'),bundles/component/kind,
                        observed[component][kind],value['cohorts'][component],adapter,kind)
                h.save(output/'bindings.json',bound)
        last_observed=observe(value,output/'artifacts-after',get)
        snapshots['artifacts-after']=inventory(output/'artifacts-after',maximum=1024**3)
        need(observed==last_observed,'maximum artifacts selected metadata changed')
        last=workflows.collect(index,output/'workflow-after',get)
        snapshots['workflow-after']=inventory(output/'workflow-after',maximum=1024**3)
        need(all(first[k]==last[k] for k in ('schema','status','workflowExecutionAttested','phase3Complete','source','indexSha256','contractsSha256','observationsSha256','selectedJobs','priorAttempts','cohorts')),
             'maximum artifacts workflow changed during binding')
        need(local_layout(index,zips,bundles)==before and seeds.read_bytes(index)==raw,'maximum artifacts inputs changed after binding')
        need(all(inventory(output/name,maximum=1024**3)==seen for name,seen in snapshots.items()),
             'maximum artifacts retained observations changed')
        h.save(output/'observation-inventories.json',snapshots)
        receipt.update(status='PARTIAL',source=value['source'],indexSha256=h.digest(raw),workflowExecutionAttested=True,
            artifactBytesBound=True,selectedJobs=first['selectedJobs'],priorAttempts=first['priorAttempts'],
            priorAttemptsRequireReview=first['priorAttemptsRequireReview'],bindingsSha256=tc.file_hash(output/'bindings.json'),
            localInputsSha256=tc.file_hash(output/'local-inputs.json'),
            observationInventoriesSha256=tc.file_hash(output/'observation-inventories.json'),
            acceptanceAuthority='live execution plus exact API ZIP/bundle bytes only; owning original replay and Phase 3 audit remain required')
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('index','zips','bundles','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args()
    with seeds.shared.progress('maximum-resource-artifact-binding','exact-attempts'):
        value=bind(a.index,a.zips,a.bundles,a.output)
    print(json.dumps({k:value[k] for k in ('status','workflowExecutionAttested','artifactBytesBound','phase3Complete')},sort_keys=True))
