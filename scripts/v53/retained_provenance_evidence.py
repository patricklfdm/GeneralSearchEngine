"""Original force/publication history -> complete read-only retained copy.

The same physical and exact-byte wire oracle applies. The bound Java qualification
uses the typed completed-copy path without injecting former voter observations.
No historical witness hash is promoted to a live voting receipt.
"""
import argparse
import json
from pathlib import Path
from . import prefix_discovery_evidence as p

e=p.e


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'prefix evidence directory')
    e.need({v.name for v in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'prefix complete inventory')
    cases=[p.case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-retained-provenance-v1',status='PASS',cases=cases,network=True,publicRuntime=False,adoption=False,scope='authenticated-complete-historical-copy')
    e.need(e.f.canonical(p.load(root/'receipt.json'))==e.f.canonical(expected),'prefix scope/receipt');return expected


def qualify(directory):return p.qualify(directory,validate)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('directory');a.add_argument('--qualify',action='store_true');args=a.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
