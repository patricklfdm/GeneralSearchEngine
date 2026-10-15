"""One ordered published-core replay for M01 query cuts; no replica inference.

Callers must separately prove each requested cut from physical observations.
Deduplication is by exact application sequence AND canonical query descriptor;
it never merges different calls in the offered/completed history ledger.
"""
from . import measurement_model as model
from .evidence import need,digest,encoded
from scripts.v51.performance_model import strict_json

SCHEMA='gse-v52-measurement-query-input-v1'
MAX_REQUESTS=4096
MAX_INPUT_BYTES=1<<20
MAX_OUTPUT_BYTES=32<<20
MAX_ROW_BYTES=64<<10


def key(sequence,query):return digest(encoded(dict(sequence=sequence,query=query)))


def prepare(cuts,updates):
    need(type(cuts) is list and 0<len(cuts)<=MAX_REQUESTS,'measurement oracle cut bound')
    requests={}
    for cut in cuts:
        need(type(cut) is dict and set(cut)=={'sequence','query'},'measurement query cut fields')
        identity=key(cut['sequence'],cut['query']);requests[identity]=dict(key=identity,**cut)
        need(len(requests)<=MAX_REQUESTS,'measurement oracle request bound')
    value=dict(schema=SCHEMA,corpus=model.corpus(),updates=updates,
               requests=sorted(requests.values(),key=lambda r:(r['sequence'],r['key'])))
    validate(value);return value


def validate(value):
    need(type(value) is dict and set(value)=={'schema','corpus','updates','requests'} and value['schema']==SCHEMA,'measurement oracle input fields')
    need(len(encoded(value))<=MAX_INPUT_BYTES,'measurement oracle input byte bound')
    need(encoded(value['corpus'])==encoded(model.corpus()),'measurement oracle corpus')
    expected=[r['document'] for r in model.program() if r['kind']=='update'];updates=value['updates']
    need(type(updates) is list and len(updates)<=len(expected) and encoded(updates)==encoded(expected[:len(updates)]),
         'measurement oracle update prefix')
    requests=value['requests'];need(type(requests) is list and 0<len(requests)<=MAX_REQUESTS,'measurement oracle request bound')
    allowed={encoded(q) for q in model.queries()};seen=set();previous=None
    for row in requests:
        need(type(row) is dict and set(row)=={'key','sequence','query'},'measurement oracle request fields')
        sequence=row['sequence'];need(type(sequence) is int and 1<=sequence<=len(updates)+1,'measurement oracle sequence')
        need(encoded(row['query']) in allowed,'measurement oracle undeclared query')
        need(row['key']==key(sequence,row['query']) and row['key'] not in seen,'measurement oracle query identity')
        position=sequence,row['key'];need(previous is None or position>previous,'measurement oracle replay order')
        previous=position;seen.add(row['key'])
    return value


def states(value):
    validate(value);current=model.corpus();sequence=1;result={1:dict(sequence=1,documents=current.copy())}
    for update in value['updates']:
        current=[update if item['id']==update['id'] else item for item in current];sequence+=1
        result[sequence]=dict(sequence=sequence,documents=current.copy())
    return result


def validate_output(value,path):
    """Require every requested result at its independently reconstructed application."""
    state=states(value);expected=value['requests'];result={};total=0
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=MAX_OUTPUT_BYTES,'measurement oracle output bound/type')
    with path.open('rb') as source:
        for index,request in enumerate(expected):
            raw=source.readline(MAX_ROW_BYTES+1);total+=len(raw)
            need(0<len(raw)<=MAX_ROW_BYTES and raw.endswith(b'\n') and total<=MAX_OUTPUT_BYTES,'measurement oracle output row bound/completeness')
            row=strict_json(raw)
            need(type(row) is dict and set(row)=={'key','sequence','query','stateSha256','answer'},'measurement oracle result fields')
            need(all(encoded(row[k])==encoded(request[k]) for k in ('key','sequence','query')),'measurement oracle returned wrong request')
            need(row['stateSha256']==digest(encoded(state[request['sequence']])),'measurement oracle wrong application state')
            result[row['key']]=row['answer']
        need(source.read(1)==b'' and total==path.stat().st_size,'measurement oracle extra/changed results')
    return result
