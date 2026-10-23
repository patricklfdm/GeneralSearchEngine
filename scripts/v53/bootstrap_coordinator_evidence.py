"""Exact original-first replay of private bootstrap coordinator evidence."""
import argparse
import json
from .bootstrap_recheck_evidence import qualify

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root,coordinator=True),sort_keys=True))
