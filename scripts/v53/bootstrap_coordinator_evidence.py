"""Exact original-first replay of private bootstrap coordinator evidence."""
import argparse
import json
from .bootstrap_recheck_evidence import qualify

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--admitted',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.root,coordinator=True,admitted=a.admitted),sort_keys=True))
