"""Explicit trusted installed-source context; never infer authority from a file."""
from pathlib import Path
import os
import sys
from . import remote_python_receiver as r

ATTRIBUTE = '_gse_v52_installed_python'
JAVA_ATTRIBUTE = '_gse_v52_installed_java'
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
if args[:1]==['--java-runtime']:
 need(len(args)>=2,'Java launch selection missing')
 java=decode(args[1].encode())
 need(type(java) is dict and set(java)=={'root','descriptorSha256'},'Java launch selection')
 sys._gse_v52_installed_java=(java['root'],java['descriptorSha256'])
 args=args[2:]
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
    r.need(type(value) is dict and set(value) in ({'root','descriptorSha256'},{'root','descriptorSha256','java'}), 'Python launch selection')
    if 'java' in value:
        from . import remote_java_receiver as j
        j.selection(value['java'])
    r.hex_value(value['descriptorSha256'],64)
    r.need(type(value['root']) is str, 'Python launch root')
    root=Path(value['root'])
    r.need(root.is_absolute() and str(root)==value['root'] and '..' not in root.parts and
           0<len(value['root'])<=4096 and '\x00' not in value['root'],
           'Python launch root')
    return value


def command(value, entry, args, *, python='python3'):
    selection(value);r.need(entry in SELECTORS,'Python launch entry')
    prefix=[] if 'java' not in value else ['--java-runtime',r.encoded(value['java']).decode()]
    return [python,'-I','-S','-c',trusted(),value['root'],value['descriptorSha256'],entry,*prefix,*map(str,args)]


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
    from . import remote_java_receiver as j
    properties=j.properties(java(),env=environment())
    r.need(properties==descriptor['source']['java'],'Python capsule Java changed')
    return descriptor['source']


def child(entry, legacy, args):
    if not active():return [sys.executable,'-I','-c',legacy,str(ROOT),*map(str,args)]
    value,_,_=verify()
    if hasattr(sys,JAVA_ATTRIBUTE):value['java']=java_selection()
    return command(value,entry,args,python=sys.executable)


def require_binding(binding,node):
    if not active():
        r.need('remotePython' not in binding and 'remoteJava' not in binding,'Python capsule requires explicit launch');return
    _,descriptor,receipt=verify()
    scope=binding.get('remotePython',{})
    r.need(type(scope) is dict and scope.get('descriptorSha256')==r.digest(r.encoded(descriptor)) and
           scope.get('nodes',{}).get(node)==receipt,'Python capsule receiver binding')
    if hasattr(sys,JAVA_ATTRIBUTE):
        value,own=java_image();java_scope=binding.get('remoteJava',{})
        r.need(java_scope.get('descriptorSha256')==r.digest(r.encoded(value)) and
               java_scope.get('nodes',{}).get(node)==own,'Java capsule receiver binding')
    else:r.need('remoteJava' not in binding,'Java capsule requires explicit launch')


def record(path):
    if not active():return
    selection,descriptor,receipt=verify()
    value=dict(schema='gse-v52-python-runtime-v1',selection=selection,
        source=descriptor['source'],installation=receipt,
        process=dict(pid=os.getpid(),entry=sys.argv[0]),isolated=True,noSite=True)
    if hasattr(sys,JAVA_ATTRIBUTE):
        _,own=java_image();value['java']=dict(selection=java_selection(),installation=own)
    r.write(Path(path),r.encoded(value))


def java_selection():
    from . import remote_java_receiver as j
    value=getattr(sys,JAVA_ATTRIBUTE,None)
    r.need(type(value) is tuple and len(value)==2,'Java explicit launch context')
    return j.selection(dict(root=value[0],descriptorSha256=value[1]))


def java_image():
    from . import remote_java_receiver as j
    _,python,_=verify();own=java_selection();root=Path(own['root'])
    value=j.descriptor(r.decode(r.read(root/'descriptor.json',j.MAX_MANIFEST)))
    r.need(r.digest(r.encoded(value))==own['descriptorSha256'] and value['source']==python['source'],
           'Java original source/descriptor changed')
    return value,j.installed(root,value)


def java():
    if not hasattr(sys,JAVA_ATTRIBUTE):return 'java'
    r.need(active(),'Java requires installed Python');_,receipt=java_image()
    return str(Path(receipt['root'])/'files/bin/java')


def environment():
    if not hasattr(sys,JAVA_ATTRIBUTE):return None
    from . import remote_java_receiver as j
    return dict(j.ENV)


def record_java_process(control,identity):
    if not hasattr(sys,JAVA_ATTRIBUTE):return
    value,receipt=java_image();binary=Path(receipt['root'])/'files/bin/java'
    proc=Path('/proc')/str(identity['pid'])
    r.need((proc/'exe').resolve()==binary and
           int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])==identity['startTicks'],
           'Java original process executable changed')
    r.write(Path(control)/'java-process.json',r.encoded(dict(schema='gse-v52-java-process-v1',process=identity,
        selection=java_selection(),executable=str(binary),executableSha256=value['files']['bin/java']['sha256'])))
