"""One native owner finishes REMOVE before its internal readiness boundary.

The shared physical reduction reads original files without rewriting projections.
This additionally binds every owner handoff and completion to those validated
selections, entries, forced images and original acknowledgements. Public service,
all membership profiles and whole Phase 3 acceptance remain separate obligations.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import continuous_transition_evidence as continuous

d,c,e,f,need=continuous.d,continuous.c,continuous.e,continuous.f,continuous.need
RESULT=dict(status='PASS',kind='REMOVE',activations=3,internalReady=True,publicReady=False,originalBudgetSeconds=600)


def lifecycle(root):
    rows=d.read(root/'events.json')
    held=[(at,row) for at,row in enumerate(rows) if row['event'].startswith('ROUND_')]
    names=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*3+['BEFORE_READY']
    need([row['event'] for _,row in held]==['ROUND_'+name for name in names],'transition round exact lifecycle')
    ordinal=0;cursor=4;selected=None;last_complete=-1;last_ack=None
    for at,row in held:
        need(set(row)=={'node','event','record','bytes'} and row['node']=='node-1','transition round original owner')
        raw=base64.b64decode(row['bytes'],validate=True)
        need(e.digest(raw)==row['record'],'transition round record digest')
        event=row['event']
        if event=='ROUND_INSTALLED':
            ordinal+=1;selected_raw=(root/f'selected-{ordinal}.gsr').read_bytes()
            need(raw==selected_raw,'transition round original selection')
            selected=f.decode(raw,'records','SELECTED');voters=continuous.PROFILES[ordinal-1][1]
            for node in voters:
                need(any(v['node']==node and v['event']=='INSTALL_BEFORE_RETURN' for v in rows[last_complete+1:at]),
                     'transition round fresh installed authority')
            need(selected['nextEntry'] is None,'transition round declared noncarried profile')
        elif event=='ROUND_SLOT_BEGIN':
            cursor+=1;entry=f.decode(raw,'records','ENTRY')
            need(raw==(root/f'native-entry-{cursor}.gsr').read_bytes() and entry['index']==cursor,
                 'transition round original entry')
            need(entry['origin']==selected['ballot'] and entry['authority']==selected['view'] and
                 entry['kind']==continuous.PROFILES[ordinal-1][0],'transition round active authority')
            need(any(v['event']=='SLOT_BEGIN' and v['index']==cursor for v in rows[at+1:]),'transition round real slot admission')
        elif event=='ROUND_SLOT_COMPLETE':
            ack=f.decode(raw,'wire','PUBLISH_ACK')
            files=c.inventory(root/f'published-{cursor}/node-1');prefix,_,packet=c.current(files)
            applied=c.inventory(root/f'applied-{cursor}/node-1');identity=d.future.identity(files)
            expected=dict(certificate=e.digest(applied['applied-end/certificate.gsr']),selection=e.digest(selected_raw),
                published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr']))
            need(ack['root']==selected['root'] and ack['view']==selected['view'] and ack['ballot']==selected['ballot'] and
                 ack['sender']==ack['recipient']==identity and ack['sequence']==1 and ack['payload']==expected,
                 'transition round original completion')
            for node in voters:
                d.s.ordered([v['event'] for v in rows[last_complete+1:at] if v['node']==node],
                    ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],
                    'transition round completion '+node)
            need(any(v['event']=='DRIVER_PUBLISHED' and v['index']==cursor for v in rows[last_complete+1:at]),
                 'transition round completion after driver')
            last_complete=at;last_ack=raw
        else:
            need(cursor==7 and ordinal==3 and raw==last_ack,'transition round readiness after fresh barrier')
            _,_,packet=c.current(c.inventory(root/'published-7/node-1'))
            need(packet['capsule']['cut']['view']['operation'] is None,'transition round stable readiness')


def validate(root):
    root=Path(root)
    need(d.read(root/'transition-round-result.json')==RESULT,'transition round scope')
    original=continuous.history(root,'transition-round-result.json')
    lifecycle(root)
    return dict(status='PASS',kind='REMOVE',internalReady=True,publicReady=False,phase3Complete=False,
                original=original,automaticOperationCompletion=True)


NEGATIVES={
    'missing-reactivation':'transition round exact lifecycle',
    'early-ready':'transition round exact lifecycle',
    'wrong-ready':'transition round readiness after fresh barrier',
    'old-selection':'transition round original selection',
    'old-ballot':'transition round original completion',
    'wrong-completion':'transition round original completion',
    'wrong-entry':'transition round original entry',
    'public-service':'transition round scope',
    'wrong-budget':'transition round scope',
    'physical-selector':'admitted exact published-7: node-1',
}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-transition-round-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);rows=d.read(path/'events.json')
            def event(kind,ordinal=0):return [v for v in rows if v['event']=='ROUND_'+kind][ordinal]
            def change(row,family,kind,mutation):
                value=f.decode(base64.b64decode(row['bytes']),family,kind);mutation(value);raw=f.encode(family,kind,value)
                row.update(record=e.digest(raw),bytes=base64.b64encode(raw).decode())
            if name=='missing-reactivation':rows.remove(event('INSTALLED',1))
            elif name=='early-ready':
                row=event('BEFORE_READY');rows.remove(row);rows.insert(rows.index(event('INSTALLED',1)),row)
            elif name=='wrong-ready':change(event('BEFORE_READY'),'wire','PUBLISH_ACK',lambda v:v['payload'].update(certificate='0'*64))
            elif name=='old-selection':
                row=event('INSTALLED',1);old=event('INSTALLED');row.update(record=old['record'],bytes=old['bytes'])
            elif name=='old-ballot':change(event('SLOT_COMPLETE',1),'wire','PUBLISH_ACK',lambda v:v['ballot'].update(counter=3))
            elif name=='wrong-completion':change(event('SLOT_COMPLETE'),'wire','PUBLISH_ACK',lambda v:v['payload'].update(generation='0'*64))
            elif name=='wrong-entry':change(event('SLOT_BEGIN'),'records','ENTRY',lambda v:v.update(previous='0'*64))
            elif name in ('public-service','wrong-budget'):
                value=dict(RESULT);value['publicReady' if name=='public-service' else 'originalBudgetSeconds']=True if name=='public-service' else 180
                (path/'transition-round-result.json').write_text(json.dumps(value))
            else:(path/'published-7/node-1/selector.gsr').write_bytes(b'changed')
            (path/'events.json').write_text(json.dumps(rows))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'transition round unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transition round mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
