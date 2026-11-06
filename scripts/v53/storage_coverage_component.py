"""Same-callback storage coverage for the short conditional replay writers."""
import argparse
import json
from pathlib import Path
from . import replay_prefix_component as component
from . import replica_storage_coverage as coverage

p=component.p


def validate(root):
    root=Path(root);before=p.collection.inventory(root)
    original=component.validate(root)  # Original model and captured bytes must agree first.
    events=p.shared.g.json_file(root/'events.json')[1];boundaries=p.shared.g.json_file(root/'boundaries.json')[1]
    initial=component.physical.c.inventory(root/'before');applied=component.physical.c.inventory(root/'applied')
    plan=p.model.transaction(initial,applied)
    points=[i for i,v in enumerate(events) if v['event'].startswith('REPLAY_')]
    rows=[dict(life=2,node='node-1',eventIndex=at,point=point,files=files)
          for at,(_,point,files) in zip(points,plan)]
    _,trace=coverage.t.read(root/'resources.json')
    result=coverage.bind(rows,trace,events,boundaries,'node-1',2,closed=True,ordinals=coverage.ordinal_plans(rows))
    p.need(p.collection.inventory(root)==before,'storage coverage component original changed')
    return dict(status='PASS',original=original,coverage=result,capturedCallbackBytesQualified=True,
                protocolAuthority='conditional-initial-history',nativeCarriedProcess=False,
                wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
