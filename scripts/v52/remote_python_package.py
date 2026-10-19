"""Closed transitive guest Python inputs, independent of a receiver Git checkout."""
import argparse
import ast
import base64
import json
from pathlib import Path
import stat
import subprocess
import sys
from . import remote_python_receiver as receiver

ROOT = Path(__file__).resolve().parents[2]


def source_file(root, name):
    path = root/name
    for p in (path.parent, *path.parent.relative_to(root).parents):
        # The first path is absolute; remaining paths are relative to root.
        observed = p if p.is_absolute() else root/p
        receiver.need(stat.S_ISDIR(observed.lstat().st_mode), 'Python source linked directory')
    info = path.lstat()
    receiver.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= receiver.MAX_FILE,
                  'Python source file type/bound')
    raw = path.read_bytes()
    receiver.need(len(raw) == info.st_size, 'Python source changed while reading')
    return raw


def module_path(root, module):
    path = module.replace('.', '/')
    for name in (path + '.py', path + '/__init__.py'):
        if (root/name).exists() or (root/name).is_symlink():
            return name
    return None


def imports(module, name, raw, exists):
    """Static closure only; no imported code is executed to discover inputs."""
    tree = ast.parse(raw, filename=name)
    package = module if name.endswith('/__init__.py') else module.rsplit('.', 1)[0]
    result = set()
    def add(target, required=True):
        if not target:
            return
        if target == 'scripts' or target.startswith('scripts.'):
            if exists(target):
                result.add(target)
            elif required:
                receiver.need(target == 'scripts', 'Python dependency missing: ' + target)
        else:
            receiver.need(target.split('.')[0] in sys.stdlib_module_names,
                          'Python dependency outside standard library: ' + target)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                add(item.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split('.')
                receiver.need(node.level <= len(parts), 'Python relative import escapes package')
                prefix = '.'.join(parts[:len(parts) - node.level + 1])
                target = prefix + ('.' + node.module if node.module else '')
            else:
                target = node.module or ''
            add(target)
            if target == 'scripts' or target.startswith('scripts.'):
                for item in node.names:
                    receiver.need(item.name != '*', 'Python star dependency')
                    add(target + '.' + item.name, required=False)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '__import__':
            receiver.need(len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Constant) and
                          type(node.args[0].value) is str and node.args[0].value in sys.stdlib_module_names,
                          'Python dynamic dependency')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                'import_module', 'spec_from_file_location', 'exec_module'):
            raise ValueError('Python dynamic dependency')
    for count in range(1, len(module.split('.'))):
        parent = '.'.join(module.split('.')[:count])
        if exists(parent):
            result.add(parent)
    return sorted(result)


def collect(root):
    root = Path(root).resolve()
    pending = list(receiver.ENTRIES); graph = {}; files = {}
    while pending:
        module = pending.pop()
        if module in graph:
            continue
        name = module_path(root, module)
        receiver.need(name is not None, 'Python dependency missing: ' + module)
        receiver.name(name); raw = source_file(root, name)
        dependencies = imports(module, name, raw, lambda m:module_path(root, m) is not None)
        graph[module] = dependencies; files[name] = raw; pending.extend(dependencies)
        receiver.need(len(files) <= receiver.MAX_FILES, 'Python dependency count')
    for name in sorted(receiver.DATA):
        files[name] = source_file(root, name)
    return files, graph


def compose(root, source):
    files, graph = collect(root)
    payload = receiver.encoded(dict(schema=receiver.SCHEMA, files={name:base64.b64encode(raw).decode('ascii')
                                                                    for name, raw in sorted(files.items())}))
    value = dict(schema=receiver.SCHEMA, source=source, entries=list(receiver.ENTRIES),
                 files={name:dict(bytes=len(raw), sha256=receiver.digest(raw)) for name, raw in sorted(files.items())},
                 bytes=len(payload), sha256=receiver.digest(payload))
    receiver.payload(payload, value)
    return payload, value, graph


def binding(root):
    from scripts.ci_v51_bundle import binding as source_binding
    return source_binding(root, subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip())


def create(root, output):
    root = Path(root).resolve(); output = Path(output)
    before = binding(root); raw, value, graph = compose(root, before)
    receiver.need(binding(root) == before, 'Python source changed during packaging')
    output.mkdir(parents=True, exist_ok=False)
    for name, data in (('payload.json', raw), ('descriptor.json', receiver.encoded(value)),
                       ('dependencies.json', receiver.encoded(graph))):
        (output/name).write_bytes(data)
    return dict(status='PASS', source=before, files=len(value['files']),
                expandedBytes=sum(row['bytes'] for row in value['files'].values()),
                payloadBytes=len(raw), descriptorSha256=receiver.digest(receiver.encoded(value)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args()
    print(json.dumps(create(ROOT, args.output)))
