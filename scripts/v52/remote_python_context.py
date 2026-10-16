"""Explicit trusted installed-source context; never infer authority from a file."""
from pathlib import Path
import os
import re
import subprocess
import sys
from . import remote_python_receiver as r

ATTRIBUTE = '_gse_v52_installed_python'
ROOT = Path(__file__).resolve().parents[2]
SELECTORS = ('delivery', 'voter', 'relay', 'partition', 'partition-stream')

# This source follows the trusted standalone receiver definitions. No installed
# module is imported until the externally supplied descriptor pin is checked.
BOOTSTRAP = '''
need(len(sys.argv)>=4 and sys.flags.isolated and sys.flags.no_site, 'Python launch isolation/arguments')
root=Path(sys.argv[1]);pin=sys.argv[2];selector=sys.argv[3];args=sys.argv[4:]
hex_value(pin,64)
need(selector in ('delivery','voter','relay','partition','partition-stream'), 'Python launch entry')
value=descriptor(decode(read(root/'descriptor.json',MAX_MANIFEST)))
need(digest(encoded(value))==pin,'Python launch trusted descriptor changed')
installed(root,value)
need(not any(n=='scripts' or n.startswith('scripts.') for n in sys.modules),'Python launch preloaded repository')
sys.dont_write_bytecode=True
sys.path.insert(0,str(root/'files'))
sys._gse_v52_installed_python=(str(root),pin)
sys.argv=['gse-v52-'+selector,*args]
from scripts.v52 import remote_python_context as context
context.source()
if selector=='delivery':
 from scripts.v52.remote_delivery_guest import main
elif selector=='voter':
 from scripts.v52.remote_voter_guest import main
elif selector=='relay':
 from scripts.v52.remote_voter_relay import main
elif selector=='partition':
 from scripts.v52.remote_partition_guest import main
else:
 from scripts.v52.remote_partition_guest import stream_main as main
main()
'''


def trusted():
    # Setting __name__ suppresses the standalone receiver's install/verify main.
    return "__name__='gse_v52_trusted_launch'\n" + Path(r.__file__).read_text() + '\n' + BOOTSTRAP


def selection(value):
    r.need(type(value) is dict and set(value)=={'root','descriptorSha256'}, 'Python launch selection')
    r.hex_value(value['descriptorSha256'],64)
    r.need(type(value['root']) is str, 'Python launch root')
    root=Path(value['root'])
    r.need(root.is_absolute() and str(root)==value['root'] and '..' not in root.parts and
           0<len(value['root'])<=4096 and '\x00' not in value['root'],
           'Python launch root')
    return value


def command(value, entry, args, *, python='python3'):
    selection(value);r.need(entry in SELECTORS,'Python launch entry')
    return [python,'-I','-S','-c',trusted(),value['root'],value['descriptorSha256'],entry,*map(str,args)]


def active():
    return hasattr(sys,ATTRIBUTE)


def verify():
    raw=getattr(sys,ATTRIBUTE,None)
    r.need(type(raw) is tuple and len(raw)==2 and all(type(v) is str for v in raw), 'Python explicit launch context')
    value=selection(dict(root=raw[0],descriptorSha256=raw[1]));root=Path(raw[0])
    r.need(ROOT==root/'files' and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
           'Python launched root/isolation changed')
    descriptor=r.descriptor(r.decode(r.read(root/'descriptor.json',r.MAX_MANIFEST)))
    r.need(r.digest(r.encoded(descriptor))==value['descriptorSha256'],'Python launch trusted descriptor changed')
    receipt=r.installed(root,descriptor)
    for name,module in list(sys.modules.items()):
        if name=='scripts' or name.startswith('scripts.'):
            path=getattr(module,'__file__',None)
            if path:
                relative=Path(path).relative_to(ROOT).as_posix()
                r.need(relative in descriptor['files'],'Python loaded module outside inventory')
            for location in getattr(module,'__path__',()):
                r.need(Path(location)==ROOT/Path(*name.split('.')),'Python foreign package path')
    return value,descriptor,receipt


def source():
    if not active():return None
    _,descriptor,_=verify()
    java=subprocess.run(['java','-XshowSettings:properties','-version'],check=True,capture_output=True,text=True).stderr
    properties=dict(re.findall(r'^\s*(java\.(?:runtime.version|vendor)) = (.+)$',java,re.MULTILINE))
    r.need(properties==descriptor['source']['java'],'Python capsule Java changed')
    return descriptor['source']


def child(entry, legacy, args):
    if not active():return [sys.executable,'-I','-c',legacy,str(ROOT),*map(str,args)]
    value,_,_=verify()
    return command(value,entry,args,python=sys.executable)


def require_binding(binding,node):
    if not active():
        r.need('remotePython' not in binding,'Python capsule requires explicit launch');return
    _,descriptor,receipt=verify()
    scope=binding.get('remotePython',{})
    r.need(type(scope) is dict and scope.get('descriptorSha256')==r.digest(r.encoded(descriptor)) and
           scope.get('nodes',{}).get(node)==receipt,'Python capsule receiver binding')


def record(path):
    if not active():return
    selection,descriptor,receipt=verify()
    r.write(Path(path),r.encoded(dict(schema='gse-v52-python-runtime-v1',selection=selection,
        source=descriptor['source'],installation=receipt,
        process=dict(pid=os.getpid(),entry=sys.argv[0]),isolated=True,noSite=True)))
