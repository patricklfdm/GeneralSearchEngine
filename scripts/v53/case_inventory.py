"""Materialize the frozen finite S/N inventory. Planning is never runtime acceptance."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path

from .contract_check import DOCS,plan_check
from .membership_model import need

SCHEMA='gse-v53-finite-inventory-v1'
REJECTIONS=(
    'provenance/source','provenance/build','provenance/attempt','identity/root-history',
    'identity/configuration','durability/accept','durability/proof','quorum/duplicate',
    'quorum/joint','identity/storage','admission/learner','admission/preparation',
    'operation/irreversibility','capsule/boundary','capsule/catalog','capsule/descriptor',
    'recovery/owned-tail','durability/selector','reclamation/floor','reads/cut',
    'execution/crash-label','execution/attempt-coverage','provenance/control','inventory/coverage')
COUNTS=dict(zip((f'S{i:02}' for i in range(1,11)),(168,336,200,840,336,756,90,24,336,224)))


def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()


def contexts(plan,selector):
    profiles=plan['profiles']
    if selector=='stable-3-4-5':return [dict(profile='stable-'+str(n),initial=n,change=None,era='stable') for n in (3,4,5)]
    need(selector in ('all-seven','old-joint-new','add-and-replace'),'unknown context selector')
    return [dict(profile=str(p['initial'])+'-'+p['kind'],initial=p['initial'],change=p['kind'],era=era)
            for p in profiles if selector!='add-and-replace' or p['kind'] in ('ADD','REPLACE')
            for era in (('old','joint','new') if selector=='old-joint-new' else ('transition',))]


def generate(plan):
    plan_check(plan);need(plan['status']=='FROZEN-LOCAL-DESIGN' and plan['scope']=='requirements, not executed runtime evidence','plan authority scope')
    scenarios=[]
    for family in plan['scenarios']:
        for context,boundary,cut,mode in product(contexts(plan,family['profiles']),family['boundaries'],family['cuts'],family['modes']):
            key='/'.join((family['id'],context['profile'],context['era'],boundary,cut,mode))
            scenarios.append(dict(id=key,scenario=family['id'],family=family['family'],context=context,boundary=boundary,cut=cut,mode=mode,
                                  requiredPhase=family['requiredPhase'],state='PLANNED',inapplicablePolicy='explicit-refusal-with-unchanged-bytes'))
    negatives=[dict(**deepcopy(row),expectedRejectionFamily=family,state='PLANNED',originalMustPass=True,unrelatedFailureIsRejection=False)
               for row,family in zip(plan['negatives'],REJECTIONS)]
    return dict(schema=SCHEMA,execution='inventory-only',runtimeQualified=False,planSha256=digest(encoded(plan)),
                indivisible=deepcopy(plan['indivisible']),oracles=deepcopy(plan['oracles']),scenarios=scenarios,negatives=negatives)


def validate(value,plan):
    expected=generate(plan)
    need(type(value) is dict and set(value)==set(expected),'inventory envelope')
    for key in expected.keys()-{'scenarios','negatives'}:need(value[key]==expected[key],'inventory scope/plan binding: '+key)
    for key in ('scenarios','negatives'):
        rows=value[key];need(type(rows) is list and all(type(r) is dict and type(r.get('id')) is str for r in rows),'inventory rows')
        actual={r['id']:r for r in rows};want={r['id']:r for r in expected[key]}
        need(len(actual)==len(rows) and actual==want,'incomplete/altered '+key+' inventory')
    counts=dict(Counter(r['scenario'] for r in value['scenarios']))
    need(counts==COUNTS,'frozen scenario counts changed')
    return dict(status='PASS',execution='inventory-only',runtimeQualified=False,scenarios=sum(counts.values()),byScenario=counts,negativeFamilies=len(value['negatives']))


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    plan_path=DOCS/'acceptance-plan.json';plan_raw=plan_path.read_bytes();plan=json.loads(plan_raw)
    receipt=dict(schema=SCHEMA,status='RUNNING',execution='inventory-only',runtimeQualified=False)
    try:
        inventory=generate(plan);raw=encoded(inventory);packed=gzip.compress(raw,mtime=0)
        (output/'plan.json').write_bytes(plan_raw);(output/'inventory.json.gz').write_bytes(packed)
        checked=validate(json.loads(gzip.decompress((output/'inventory.json.gz').read_bytes())),json.loads((output/'plan.json').read_bytes()))
        need(plan_path.read_bytes()==plan_raw,'plan changed during generation')
        receipt.update(checked,planFileSha256=digest(plan_raw),inventorySha256=digest(packed),decodedInventorySha256=digest(raw),
                       collectorSha256=digest(Path(__file__).read_bytes()),unpackedBytes=len(raw),compressedBytes=len(packed))
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:(output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
