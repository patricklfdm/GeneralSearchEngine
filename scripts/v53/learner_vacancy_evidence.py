"""Independent portable A25 vacancy binding, not native history acceptance.

A full history reader must first prove the original source/selection/force trace.
This component can reject inconsistent copied records but cannot authorize reuse
or infer that a record observed on disk was forced before a crash.
"""
import argparse
import json
import re
from . import learner_slot_snapshot as s
f, e, need = s.f, s.e, s.need
SEED={'.','successor.lock','install.json','selected.json','head.json','retire.json'}
TYPED={'.','preparation.lock','preparation.json','learner.gsr','backup',
       'backup/gse-backup-checkpoint','backup/gse-backup-manifest','backup/gse-backup-metadata'}
HEAD={'schema','plan','source','generation','receipt','headKey','seedFiles','previousFiles','previousTyped','currentFiles'}
CLEAR={'schema','plan','head','headKey','clearKey','previousFiles','previousTyped','seedFiles'}


def record(raw, reason):
    need(type(raw) is bytes and len(raw)<=16384, reason)
    return e.parse(raw)


def fingerprints(value):
    need(type(value) is list and 1<=len(value)<=33, 'learner vacancy fingerprint shape')
    names=[]
    for row in value:
        need(type(row) is dict and set(row)=={'path','sha256'} and type(row['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None, 'learner vacancy fingerprint shape')
        s.member_path(row['path']);names.append(row['path'])
    need(names==sorted(set(names)) and names[0]=='.', 'learner vacancy fingerprint shape')


def binding(snapshot):
    slots=snapshot.files['slots'];typed=snapshot.files['slot-typed'];seed=snapshot.files['seed']
    head=record(slots.get('head.json'), 'learner vacancy original head required')
    need(type(head) is dict and set(head)==HEAD and head['schema']=='gse-v53-learner-slot-head/1.3',
         'learner vacancy head shape')
    names={'cleared.json','cleared.next.json'} & set(slots)
    need(len(names)==1, 'learner vacancy original marker location');name=next(iter(names))
    clear=record(slots[name], 'learner vacancy bounded marker')
    need(type(clear) is dict and set(clear)==CLEAR, 'learner vacancy marker shape')
    for field in ('seedFiles','previousFiles','previousTyped','currentFiles'):fingerprints(head[field])
    identities=snapshot.identities['slots']['members']
    need(head['headKey']==identities['head.json']['key'] and clear['clearKey']==identities[name]['key'],
         'learner vacancy original selecting inode')
    expected=dict(schema='gse-v53-learner-slot-cleared/1.3',plan=head['plan'],head=s.digest(slots['head.json']),
                  headKey=head['headKey'],clearKey=identities[name]['key'])
    expected.update({k:s.digest(f.canonical(head[k])) for k in ('previousFiles','previousTyped','seedFiles')})
    need(clear==expected, 'learner vacancy exact selected binding')
    need(set(seed)==SEED and not snapshot.identities['seed-typed']['present']
         and not snapshot.identities['initial-typed']['present'], 'learner vacancy original roots not cleared')
    need(head['seedFiles']==snapshot.fingerprints('seed',SEED), 'learner vacancy immutable seed metadata')
    need(set(typed)==TYPED and head['currentFiles']==snapshot.fingerprints('slot-typed',TYPED),
         'learner vacancy current typed fingerprints')
    references={'plan':('slots','b.json'),'source':('slots','source-b/source.gscp'),
                'generation':('slots','source-b/generation.gsr'),'receipt':('slot-typed','learner.gsr')}
    for field,(root,member) in references.items():
        need(type(snapshot.files[root].get(member)) is bytes and head[field]==s.digest(snapshot.files[root][member]),
             'learner vacancy current original binding')
    return dict(marker=name,head=s.digest(slots['head.json']),plan=head['plan'],
                candidateOnly=name=='cleared.next.json')


def validate(root):
    return dict(status='PARTIAL',scope='portable-original-vacancy-binding',binding=binding(s.read(root)),
                nativeHistoryQualified=False,forceOrderQualified=False,reuseAuthorized=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
