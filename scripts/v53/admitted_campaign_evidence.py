"""Two stable publications with the old source hidden in the second RANGE."""
import json
import shutil
import tempfile
from pathlib import Path
from . import admitted_cross_view_evidence as q


def validate(root):
    root=Path(root);w=q.Walk(root,5,False)
    for _ in range(2):w.publish('BARRIER');w.campaign()
    w.required.add('receipt.json');q.selection.layout(root,w.required,'admitted campaign')
    q.same(q.read(root/'receipt.json'),dict(status='PASS',slots=2,voters=5,hiddenOriginalIndex=1,runtimeEnabled=False),'admitted campaign receipt')
    observed=q.read(root/'observations.json')
    q.e.need(len(observed)==len(w.observed) and {q.e.f.canonical(v) for v in observed}==w.observed,'admitted campaign observations')
    calls=q.read(root/'calls.json');expected=[]
    def many(label):expected.extend((n,label) for n in w.active)
    def campaign(counter,stage):
        expected.append(('node-1','allocate-'+str(counter)))
        for phase in ('prepare','select','install'):many(phase+'-'+str(counter))
        many(stage+'-copy');many(stage+'-maintain')
    campaign(1,'round-1-settled')
    for slot in (1,2):
        expected.append(('node-1','inspect-context'))
        for phase in ('accept','proof','certificate','apply','publish'):many(phase+'-'+str(slot))
        many(f'slot-{slot}-settled-copy');many(f'slot-{slot}-settled-maintain')
        campaign(slot+2,f'campaign-{slot+2}-settled')
    many('inspect-ancestry')
    q.e.need([(v['node'],v['operation']) for v in calls]==expected,'admitted campaign exact calls')
    for value in calls:
        q.e.exact(value,'node operation events')
        q.e.need(type(value['events']) is list and 0<len(value['events'])<=4096,'admitted campaign event bound')
    required={'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
              'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
              'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
              'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
              'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
              'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
              'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
              'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}
    for label,nodes in w.phases.items():
        rows=[v for v in calls if v['operation']==label];events=required[label.rsplit('-',1)[0]]
        q.e.need([v['node'] for v in rows]==nodes,'admitted campaign force owners')
        for row in rows:q.e.need([v for v in row['events'] if v in set(events)]==events,'admitted campaign force order')
    return dict(status='PASS',slots=2,voters=5,hiddenOriginalIndex=1,publicBootstrap=True,publicRuntime=False,originalFirst=True)


def qualify(root):
    root=Path(root);result=validate(root);negative=[]
    for name in ('missing-ancestry','changed-ancestry','selector','force'):
        with tempfile.TemporaryDirectory(prefix='v53-campaign-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved)
            if name=='force':
                p=moved/'calls.json';rows=q.read(p);row=next(v for v in rows if v['operation']=='install-4');row['events'].remove('INSTALL_SELECTOR_FORCED');p.write_bytes(q.e.f.canonical(rows))
            else:
                node=moved/'campaign-4-installed/node-1';prefix,_,_=q.c.current(q.c.inventory(node))
                p=node/(prefix+'ancestry.gsr') if 'ancestry' in name else node/'selector.gsr'
                if name=='missing-ancestry':p.unlink()
                else:p.write_bytes(b'changed original')
            reason='admitted campaign force order' if name=='force' else 'admitted exact campaign-4-installed: node-1'
            try:validate(moved)
            except ValueError as error:q.e.need(str(error)==reason,'admitted campaign unrelated negative: '+str(error))
            else:raise ValueError('admitted campaign accepted mutation: '+name)
            negative.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negativeCases=negative)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
