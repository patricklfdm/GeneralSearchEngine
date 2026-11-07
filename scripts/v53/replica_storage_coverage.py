"""Simultaneous replica-file coverage by original resource charges.

The caller first admits every file inventory. This checks complete file bytes at
one owner's one callback, not disk blocks, RAM, unobserved writes, other scratch
directories or a cross-node simultaneous peak. No content hash deduplication.
"""
from collections import defaultdict
import re
from . import resource_transitions as t
need=t.need
HEX=r'[0-9a-f]{64}'
UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
JOURNAL=('JOURNAL','membership-grants')
MISC=('MISC','current-authority')
JOURNAL_FILES={'grants.gsr','grants.rotation.gsr','pending.accept','pending.accept.next',
               'peer-retention.gspr','peer-retention.next.gspr','future-retention.gsft','future-retention.next.gsft',
               'learner-retention.gslr','learner-retention.next.gslr','joining-retention.gsjr','joining-retention.next.gsjr',
               'joining-retention.done.gsjr','joining-retention.done.next.gsjr'}
MISC_FILES={'root.gsr','node.gsr','replica.lock','genesis.gsr','selector.gsr','selector.pending.gsr',
            'allocator.gsr','allocator.pending.gsr','bootstrap-admission.gsbp','bootstrap-prepared.gsbp',
            'bootstrap-seal.gsbp','source.capture.gsr','sources.retirement.gsr'}
GENERATION_MEMBERS={'generation.gsr','source.gscp','promise.gsr','basis.gsr','selected.gsr','ancestry.gsr',
                    'owned-tail.gsr','selected-sources.gsr','selected-coverage.json','adoption.gsr','adopted-certificate.gsr'}
END_MEMBERS={'plan.json','selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr',
             'parent-statement.gsr','parent-ack.gsr','retirement.gsat','retirement.gsat.next',
             *(f'ancestor-{i}-{kind}.gsr' for i in range(5) for kind in ('statement','ack'))}
BACKUP={'gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata'}


def inventory(files):
    need(type(files) is dict and 0<len(files)<=512,'storage coverage bounded inventory')
    for name,value in files.items():
        need(type(name) is str and len(name)<=1024 and not name.startswith('/') and
             all(part not in ('','.', '..') for part in name.split('/')),'storage coverage relative path')
        parent=name.rpartition('/')[0]
        need(not parent or files.get(parent)=={'directory':True},'storage coverage directory parent')
        need(type(value) is dict,'storage coverage file identity')
        if value=={'directory':True}:need(type(value['directory']) is bool,'storage coverage directory identity')
        else:need(set(value)=={'bytes','sha256'} and type(value['bytes']) is int and 0<=value['bytes']<=64*t.MIB and
                  type(value['sha256']) is str and re.fullmatch(HEX,value['sha256']), 'storage coverage exact file extent')


def owners(files,ordinals):
    """Map every physical file to one exclusive original owner, including empty files."""
    inventory(files);result={}
    def image_owner(prefix,name):
        names=ordinals.get(prefix,())
        need(type(names) in (list,tuple) and list(names)==sorted(set(names)) and
             all(type(v) is str and re.fullmatch(HEX+r'\.image',v) for v in names),
             'storage coverage ordered original images')
        need(name in names,'storage coverage original image ordinal')
        return ('APPLICATION',('retirement' if prefix=='retirement/source' else 'floor:'+prefix.split('/')[1])+':'+str(names.index(name)))
    for path,value in files.items():
        parts=path.split('/');key=None;directory=False
        if len(parts)==1:
            if path in JOURNAL_FILES:key=JOURNAL
            elif path in MISC_FILES:key=MISC
            else:need(path in {'generations','sources','floor-copies','retirement','application-replay','applied-end'} and
                      value=={'directory':True},'storage coverage unclassified root')
            directory=key is None
        elif parts[0] in ('generations','floor-copies'):
            base,identifier=parts[:2]
            if base=='floor-copies' and len(parts)==2 and identifier in {'proposal.gsr','floor.gsr','release.gsr','local.gsr'}:key=MISC
            else:
                need(identifier in ('a','b') if base=='generations' else re.fullmatch(HEX,identifier), 'storage coverage storage group name')
                key=('GENERATION',identifier) if base=='generations' else ('SOURCE','floor:'+identifier)
                if len(parts)==2:directory=True
                else:
                    need(len(parts)==3,'storage coverage flat storage group');name=parts[2]
                    if re.fullmatch(HEX+r'\.image',name):
                        key=('APPLICATION','generation-'+identifier+':'+name) if base=='generations' else image_owner(base+'/'+identifier,name)
                    else:need(name in GENERATION_MEMBERS,'storage coverage generation member')
        elif parts[0]=='sources':
            need(len(parts) in (2,3) and re.fullmatch(UUID,parts[1]),'storage coverage original source name')
            key=('SOURCE',parts[1])
            if len(parts)==2:directory=True
            elif re.fullmatch(HEX+r'\.image',parts[2]):key=('APPLICATION',parts[1]+':'+parts[2][:-6])
            else:need(parts[2]=='source.gscp','storage coverage source member')
        elif parts[0]=='retirement':
            if len(parts)==2 and parts[1] in ('proposal.gsr','retirement.gsr'):key=MISC
            elif path=='retirement/images.json':key=('SOURCE','retirement')
            else:
                need(parts[1]=='source' and len(parts) in (2,3),'storage coverage retirement member');key=('SOURCE','retirement')
                if len(parts)==2:directory=True
                elif re.fullmatch(HEX+r'\.image',parts[2]):key=image_owner('retirement/source',parts[2])
                else:need(parts[2] in GENERATION_MEMBERS,'storage coverage retirement source member')
        elif parts[0]=='applied-end':
            need(len(parts)==2 and (parts[1] in END_MEMBERS or parts[1]=='application.image'),'storage coverage applied member')
            key=('APPLICATION','applied-end') if parts[1]=='application.image' else JOURNAL
        elif parts[0]=='application-replay':
            if path=='application-replay/claim.json':key=JOURNAL
            else:
                need(parts[1]=='work' and 2<=len(parts)<=4 and (len(parts)==2 or parts[2]=='input') and
                     (len(parts)!=4 or parts[3] in BACKUP),'storage coverage control replay member')
                key=('APPLICATION','application-replay-input')
                if len(parts)<4:directory=True
        else:raise ValueError('storage coverage unclassified path')
        need((value=={'directory':True})==directory,'storage coverage exact file or directory')
        if key is not None:
            result[path]=key
    return result


def compare(files,charges,ordinals):
    need(type(charges) is dict and all(t.key(v)==k for k,v in charges.items()),'storage coverage charge keys')
    t.charges(sorted(charges.values(),key=t.order_key))
    mapping=owners(files,ordinals);required=defaultdict(int);paths=defaultdict(list)
    for path,key in mapping.items():
        required[key]+=files[path].get('bytes',0);paths[key].append(path)
    for key,size in required.items():
        value=charges.get(key)
        need(value is not None and not value['claimSource'],'storage coverage original charge owner')
        need(value['bytes']>=max(1,size),'storage coverage simultaneous owner extent')
    total=sum(v['bytes'] for v in files.values() if 'bytes' in v)
    need(total==sum(required.values()),'storage coverage every file counted once')
    return dict(physicalBytes=total,physicalFiles=sum('bytes' in v for v in files.values()),
        physicalDirectories=sum('directory' in v for v in files.values()),
        required=[dict(unit=k[0],owner=k[1],bytes=v,paths=sorted(paths[k])) for k,v in sorted(required.items())],
        unboundCharges=[v for k,v in sorted(charges.items()) if k not in required])


def ordinal_plans(rows):
    """Original model rows, never a surviving-file list from a partial deletion.

    Floor copies are immutable and content addressed. Retirement reuses a path;
    its image order must reset for each complete original retirement operation.
    The caller independently validates the transactions that produced these rows.
    """
    need(type(rows) is list and all(type(v) is dict and type(v.get('life')) is int and v['life'] in (1,2) and
         type(v.get('node')) is str and v['node'] in ('node-1','node-2','node-3','node-4') and
         type(v.get('eventIndex')) is int and v['eventIndex']>=0 and type(v.get('point')) is str for v in rows),
         'storage coverage original row identity')
    need(all((a['life'],a['eventIndex'])<(b['life'],b['eventIndex']) for a,b in zip(rows,rows[1:])),
         'storage coverage ordered unique callbacks')
    floors=defaultdict(set);operations={};active={};row_operations={}
    for row in rows:
        inventory(row['files'])
        owner=(row['life'],row['node']);at=row['eventIndex'];point=row['point']
        if point=='RETIREMENT_OLD_FILES_FORCED':
            need(owner not in active,'storage coverage overlapping retirement')
            active[owner]=(*owner,at);operations[active[owner]]=set()
        row_operations[(*owner,at)]=active.get(owner)
        for path in row['files']:
            if not path.endswith('.image'):continue
            prefix,_,name=path.rpartition('/')
            if prefix.startswith('floor-copies/'):
                floors[(*owner,prefix)].add(name)
            elif prefix=='retirement/source':
                need(owner in active,'storage coverage retirement without original operation')
                operations[active[owner]].add(name)
        if point=='RETIREMENT_BEFORE_RETURN':
            need(owner in active,'storage coverage retirement without original beginning')
            del active[owner]
    need(not active,'storage coverage incomplete original retirement')
    result={}
    for row in rows:
        owner=(row['life'],row['node']);key=(*owner,row['eventIndex'])
        need(key not in result,'storage coverage duplicate callback')
        result[key]={k[2]:sorted(v) for k,v in floors.items() if k[:2]==owner}
        if row_operations[key] is not None:result[key]['retirement/source']=sorted(operations[row_operations[key]])
    return result


def bind(rows,trace,events,boundaries,node,life,*,closed,ordinals):
    """Join one owner's complete trace to the same callback's entire inventory."""
    accounting=t.replay(trace,require_closed=closed)
    need(type(events) is list and type(boundaries) is list and len(events)==len(boundaries),
         'storage coverage exact event checkpoints')
    last=0
    for at,(event,point) in enumerate(zip(events,boundaries)):
        need(type(event) is dict and type(point) is dict and set(point)=={'eventIndex','node','sequence','usage'} and
             type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==event.get('node'),
             'storage coverage original checkpoint owner')
        if point['node']!=node:continue
        seq=point['sequence']
        need(type(seq) is int and last<=seq<len(trace['changes']),'storage coverage checkpoint order');last=seq
        t.same_usage(point['usage'],trace['changes'][seq]['usage'])
    selected=[v for v in rows if v['life']==life and v['node']==node]
    need(all(type(v['eventIndex']) is int and 0<=v['eventIndex']<len(events) for v in selected) and
         all(a['eventIndex']<b['eventIndex'] for a,b in zip(selected,selected[1:])),
         'storage coverage ordered unique callbacks')
    state={};cursor=0;snapshots=[]
    for row in selected:
        at=row['eventIndex'];event=events[at];point=boundaries[at]
        need(event.get('node')==node and event.get('event')==row['point'],'storage coverage original file callback')
        while cursor<=point['sequence']:
            change=trace['changes'][cursor]
            for old in change['removed']:del state[t.key(old)]
            for new in change['added']:state[t.key(new)]=new
            cursor+=1
        need((life,node,at) in ordinals,'storage coverage original ordinal plan')
        value=compare(row['files'],state,ordinals[life,node,at])
        snapshots.append(dict(life=life,node=node,eventIndex=at,point=row['point'],sequence=point['sequence'],
                              usage=point['usage'],**value))
    peak=max(snapshots,key=lambda v:v['physicalBytes']) if snapshots else None
    return dict(life=life,node=node,callbacks=len(snapshots),snapshots=snapshots,physicalBytePeak=peak,
        accounting=accounting,peakScope='one-owner-observed-callback-file-extents',
        crossNodeSimultaneousPeak=False,unobservedWritesQualified=False,wholeRuntimeResourcesQualified=False)
