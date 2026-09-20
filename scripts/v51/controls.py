"""Hash-pinned published controls downloaded independently of the local Maven cache."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def resolve(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'docs/v5x/v5.1/published-controls.json').read_text());result=[]
    for entry in manifest['artifacts']:
        artifact,version=entry['artifact'],entry['version'];name=f'{artifact}-{version}.jar';target=output/name
        url=f'https://repo.maven.apache.org/maven2/io/github/patricklfdm/{artifact}/{version}/{name}'
        if not target.exists():
            with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(64*1024*1024+1)
            if len(raw)>64*1024*1024:raise ValueError('published control size limit')
            if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('published control digest mismatch: '+name)
            target.write_bytes(raw)
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('control cache digest mismatch: '+name)
        result.append(dict(entry,path=str(target.resolve()),source=url))
    receipt=dict(status='PASS',artifacts=result)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(resolve(a.output)))
