"""Retain provider fixtures as bytes without letting artifact globbing follow links."""
import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile


def pack(source, output):
    source, output = Path(source), Path(output)
    if source.is_symlink() or not source.is_dir(): raise ValueError('provider evidence directory')
    if output.resolve().is_relative_to(source.resolve()): raise ValueError('archive inside provider evidence')
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    # A failed collection must never leave a partial archive at the upload path.
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.provider-evidence-', suffix='.tmp') as temporary:
        with tarfile.open(fileobj=temporary, mode='w:gz', dereference=False) as archive:
            archive.add(source, arcname=source.name, recursive=True)
        temporary.flush(); os.fsync(temporary.fileno())
        os.link(temporary.name, output)  # Exclusive publication; preserve original fixtures.
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('source'); parser.add_argument('output')
    args = parser.parse_args()
    print(json.dumps(dict(status='PASS', archive=str(pack(args.source, args.output)))))
