"""Native serialized round evidence: original slots first, readiness second.

The existing strict physical/network reader consumes an exact projection that
omits only this extension's result file. No original bytes or events are edited.
READY is an observed internal boundary, not authority for future public reads.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import native_dispatch_evidence as d
from . import carried_slot_evidence as carried

f, e, c, need = d.f, d.e, d.c, d.need


def projection(root):
    """Reject links before copying; the underlying reader checks exact inventory."""
    need(root.is_dir() and not root.is_symlink(), 'round original regular inventory')
    total=0
    for count,p in enumerate(root.rglob('*'),1):
        need(not p.is_symlink() and (p.is_dir() or p.is_file()), 'round original regular inventory')
        if p.is_file():total+=p.stat().st_size
        need(count<=65536 and total<=512*e.MIB, 'round bounded original inventory')
    result = d.read(root/'round-result.json')
    need(result in [dict(status='PASS', mode=mode, internalReady=True, publicReady=False) for mode in ('stable', 'carried-applied')], 'round result scope')
    return result


def lifecycle(root, mode):
    rows = d.read(root/'events.json')
    held = [(i, row) for i, row in enumerate(rows) if row['event'].startswith('ROUND_')]
    names = ['INSTALLED', 'SLOT_BEGIN', 'SLOT_COMPLETE', 'BEFORE_READY', 'SLOT_BEGIN', 'SLOT_COMPLETE'] if mode == 'stable' else [
        'INSTALLED', 'SLOT_BEGIN', 'SLOT_COMPLETE', 'SLOT_BEGIN', 'SLOT_COMPLETE', 'BEFORE_READY']
    need([row['event'] for _, row in held] == ['ROUND_'+n for n in names], 'round exact lifecycle order')
    selected_raw = d.b.t.plans.read(root/'selected.gsr', 65536); selected = f.decode(selected_raw, 'records', 'SELECTED')
    local_files = c.inventory(root/'installed/node-1'); identity = d.future.identity(local_files)
    completions = {}; entries = {}; cursor = 0; previous_complete = held[0][0]
    for at, row in held:
        need(set(row) == {'node','event','record','bytes'} and row['node'] == 'node-1', 'round local event owner')
        raw = base64.b64decode(row['bytes'], validate=True)
        need(e.digest(raw) == row['record'], 'round event digest')
        event = row['event']
        if event == 'ROUND_INSTALLED':
            need(raw == selected_raw, 'round installed original selection')
            need(all(any(v['node']==node and v['event']=='INSTALL_BEFORE_RETURN' for v in rows[:at]) for node in d.VOTERS), 'round installed after original force')
        elif event == 'ROUND_SLOT_BEGIN':
            cursor += 1; entry = f.decode(raw, 'records', 'ENTRY')
            # The physical reader already derived the exact accepted entry. Use
            # its actual independently validated publication cut to bind events.
            _, _, packet = c.current(c.inventory(root/f'published-{cursor}/node-1'))
            need(entry['index'] == cursor and e.digest(raw) == packet['capsule']['cut']['entry'], 'round exact slot entry')
            entries[cursor] = entry
            if mode == 'carried-applied' and cursor == 1:
                need(e.digest(raw) == selected['nextEntry'] and entry['origin'] != selected['ballot'], 'round exact carried entry')
            else: need(entry['origin'] == selected['ballot'], 'round current ballot entry')
            need(at > previous_complete, 'round serialized slot')
            begin = next((i for i in range(at+1, len(rows)) if rows[i]['event']=='SLOT_BEGIN'), None)
            need(begin is not None and rows[begin]['index']==cursor, 'round actual slot admission')
        elif event == 'ROUND_SLOT_COMPLETE':
            ack = f.decode(raw, 'wire', 'PUBLISH_ACK')
            files = c.inventory(root/f'published-{cursor}/node-1'); directory, _, packet = c.current(files)
            applied = c.inventory(root/f'applied-{cursor}/node-1')
            expected = dict(certificate=e.digest(applied['applied-end/certificate.gsr']), selection=e.digest(selected_raw),
                published=c.anchor(packet['capsule']), generation=e.digest(files[directory+'generation.gsr']))
            need(ack['root']==selected['root'] and ack['view']==selected['view'] and ack['ballot']==selected['ballot']
                 and ack['sender']==ack['recipient']==identity and ack['sequence']==1 and ack['payload']==expected,
                 'round original publication acknowledgement')
            for node in d.VOTERS:
                d.s.ordered([v['event'] for v in rows[previous_complete:at] if v['node']==node],
                    ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'], 'round completion '+node)
            completions[cursor]=raw;previous_complete=at
        else:
            barrier_index = 1 if mode=='stable' else 2
            need(cursor==barrier_index and raw==completions.get(barrier_index), 'round readiness after fresh publication')
            entry=entries[barrier_index]
            need(entry['kind']=='BARRIER' and entry['origin']==selected['ballot'], 'round readiness fresh barrier')
    need(cursor==2, 'round exact completed slot count')


def validate(root):
    root=Path(root); result=projection(root)
    with tempfile.TemporaryDirectory(prefix='v53-round-original-') as temp:
        path=Path(temp)/'raw';shutil.copytree(root,path);(path/'round-result.json').unlink()
        original=(d.validate if result['mode']=='stable' else carried.validate)(path)
    if result['mode']=='carried-applied': need(original['phase']=='APPLIED', 'round original carried phase')
    lifecycle(root,result['mode'])
    return dict(status='PASS',mode=result['mode'],slots=2,original=original,internalReady=True,publicReady=False,phase3Complete=False)


NEGATIVES = {
    'missing-ready': 'round exact lifecycle order',
    'early-ready': 'round exact lifecycle order',
    'wrong-ready-ack': 'round readiness after fresh publication',
    'forged-completion': 'round original publication acknowledgement',
    'extra-result': 'round result scope',
    'forged-selection': 'round installed original selection',
    'wrong-parent': 'round exact slot entry',
    'physical-selector': 'admitted exact published-2: node-1',
}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-round-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);rows=d.read(path/'events.json')
            def event(kind): return next(row for row in rows if row['event']=='ROUND_'+kind)
            def change(row, kind, mutation):
                family='records' if kind in ('SELECTED','ENTRY') else 'wire'
                value=f.decode(base64.b64decode(row['bytes']),family,kind);mutation(value);raw=f.encode(family,kind,value)
                row['record']=e.digest(raw);row['bytes']=base64.b64encode(raw).decode()
            if name=='missing-ready': rows.remove(event('BEFORE_READY'))
            elif name=='early-ready':
                row=event('BEFORE_READY');rows.remove(row);rows.insert(next(i for i,v in enumerate(rows) if v['event']=='ROUND_SLOT_COMPLETE'),row)
            elif name=='wrong-ready-ack':
                row=event('BEFORE_READY');change(row,'PUBLISH_ACK',lambda v:v['payload'].update(certificate='0'*64))
            elif name=='forged-completion':change(event('SLOT_COMPLETE'),'PUBLISH_ACK',lambda v:v['payload'].update(certificate='0'*64))
            elif name=='extra-result':
                value=d.read(path/'round-result.json');value['publicReady']=True;(path/'round-result.json').write_text(json.dumps(value))
            elif name=='forged-selection':change(event('INSTALLED'),'SELECTED',lambda v:v['ballot'].update(counter=v['ballot']['counter']+1))
            elif name=='wrong-parent':change(event('SLOT_BEGIN'),'ENTRY',lambda v:v.update(previous='0'*64))
            else:(path/'published-2/node-1/selector.gsr').write_bytes(b'changed')
            (path/'events.json').write_text(json.dumps(rows))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'round negative wrong reason: '+name+': '+str(error))
            else:raise ValueError('round mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
