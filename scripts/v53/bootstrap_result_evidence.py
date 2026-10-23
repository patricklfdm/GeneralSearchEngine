"""Replay the exact immutable result against retained originals and progressed stores."""
import argparse
import json
from .bootstrap_store_admission_evidence import qualify
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root,with_result=True),sort_keys=True))
