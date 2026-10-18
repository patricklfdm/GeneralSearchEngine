"""Build a deterministic bounded guest Java image from the original controller JDK."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import platform
from . import remote_java_receiver as r,remote_python_package as python


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while raw:=stream.read(r.PIECE):digest.update(raw)
    return digest.hexdigest()


def inventory(root):
    result={}
    for path in sorted(Path(root).rglob('*')):
        info=path.lstat()
        if stat.S_ISDIR(info.st_mode):continue
        r.p.need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=r.MAX_FILE,'Java build regular file')
        name=r.name(path.relative_to(root).as_posix())
        result[name]=dict(bytes=info.st_size,sha256=sha(path),executable=bool(info.st_mode&0o111))
        r.p.need(len(result)<=r.MAX_FILES,'Java build file count')
    return result


def create(root,expected,output):
    root=Path(root).resolve();output=Path(output).absolute()
    r.p.need(python.binding(root)==expected,'Java build original checkout/JDK')
    r.p.need(platform.system()=='Linux' and platform.machine()=='x86_64','Java image requires Linux x86_64')
    r.p.need(not any(p.is_symlink() for p in (output,*output.parents)),'Java build linked output')
    output.mkdir(parents=True,exist_ok=False);image=output/'image'
    java=Path(shutil.which('java')).resolve();home=java.parent.parent
    r.p.need(r.properties(java)==expected['java'],'Java build original version')
    tools=[java,home/'bin/jlink',*(home/('jmods/'+name+'.jmod') for name in r.MODULES)]
    before={str(p):sha(p) for p in tools}
    with (output/'jlink.stdout').open('xb') as out,(output/'jlink.stderr').open('xb') as err:
        subprocess.run([str(home/'bin/jlink'),'--add-modules',','.join(r.MODULES),
            '--strip-debug','--no-header-files','--no-man-pages','--output',str(image)],
            check=True,stdout=out,stderr=err,timeout=300,env=r.ENV)
    for path in sorted(image.rglob('*')):
        if path.is_symlink():
            resolved=path.resolve();r.p.need(resolved.is_relative_to(image) and resolved.is_file(),'Java external image link')
            raw=resolved.read_bytes();path.unlink();path.write_bytes(raw)
    files=inventory(image);archive=output/'runtime.tar.gz'
    with archive.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
            for name,row in sorted(files.items()):
                entry=tarfile.TarInfo(name);entry.mode=0o755 if row['executable'] else 0o644;entry.size=row['bytes']
                with (image/name).open('rb') as source:tar.addfile(entry,source)
    value=r.descriptor(dict(schema=r.SCHEMA,source=expected,modules=list(r.MODULES),files=files,
        bytes=archive.stat().st_size,sha256=sha(archive)))
    r.p.need(inventory(image)==files and {str(p):sha(p) for p in tools}==before and python.binding(root)==expected,
             'Java source/JDK/image changed during packaging')
    r.p.need(r.properties(image/'bin/java')==expected['java'],'Java built runtime differs')
    (output/'descriptor.json').write_bytes(r.p.encoded(value)+b'\n')
    receipt=dict(status='BUILT_NOT_INSTALLED',descriptorSha256=r.p.digest(r.p.encoded(value)),source=expected,
        archiveSha256=value['sha256'],archiveBytes=value['bytes'],files=len(files),expandedBytes=sum(v['bytes'] for v in files.values()),
        originalTools=before,paidCloud=False,fullRemoteQualification=False)
    (output/'receipt.json').write_bytes(r.p.encoded(receipt)+b'\n');return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
    value=create(python.ROOT,python.binding(python.ROOT),args.output)
    print(json.dumps(dict(status='BUILT_NOT_INSTALLED',bytes=value['bytes'],sha256=value['sha256'])))
