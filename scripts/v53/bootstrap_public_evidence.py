"""Original-result and admitted-store replay for public offline bootstrap."""
import argparse
import json
from .bootstrap_store_admission_evidence import qualify
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root,with_result=True,public_bootstrap=True),sort_keys=True))
