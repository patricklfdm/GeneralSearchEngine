"""Original node-1 disk extents at the joint queue-pressure checkpoints.

The complete physical history is the prerequisite. Captured files must equal
its installed joint authority; producer hashes cannot authorize other files.
"""
from pathlib import Path
from . import publication_resource_evidence as publication

need=publication.need
DIRECTORY='queue-storage-captures'
SCHEMA='gse-v53-queue-pressure-storage-v1'


def names(rehearsal=False):
    return ('SEVEN_SENDS_HELD','EIGHTH_SEND_DELIVERED' if rehearsal else 'EIGHTH_SEND_REFUSED')


def file_rows(files):
    return [dict(path=name,sha256=digest) for name,digest in sorted(files.items())]


def describe(files):
    inventory={n:publication.sha(v) for n,v in files.items() if v is not None}
    images=[v for n,v in files.items() if n.endswith('.image') and v is not None]
    need(images and all(images),'queue storage nonempty physical images')
    return dict(files=inventory,physicalBytes=sum(len(v) for v in files.values() if v is not None),
                physicalApplicationBytes=sum(map(len,images)),imageCopies=len(images))


def load(root,original,*,rehearsal=False):
    root=Path(root)/DIRECTORY;expected=names(rehearsal)
    need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={'index.json',*expected},
         'queue storage complete captures')
    index=publication.history.read_json(root,'index.json',1024*1024)
    need(type(index) is dict and set(index)=={'schema','points'} and
         index['schema']=='gse-v53-queue-storage-captures-v1' and type(index['points']) is list and
         len(index['points'])==2 and all(type(p) is dict for p in index['points']) and
         [p.get('event') for p in index['points']]==list(expected),'queue storage exact index')
    copies={}
    for name in expected:
        files=publication.native.c.inventory(root/name)
        need(files==original,'queue storage differs from original joint authority')
        copies[name]=describe(files)
    return dict(points=index['points'],copies=copies,original=describe(original),storage=publication.baseline(original))


def replay(value,markers,trace,*,rehearsal=False):
    expected=names(rehearsal)
    need(type(value) is dict and set(value)=={'points','copies','original','storage'} and
         type(value['points']) is list and len(value['points'])==2 and set(value['copies'])==set(expected),
         'queue storage complete captures')
    observations=[]
    for name,point in zip(expected,value['points']):
        need(type(point) is dict and set(point)=={'event','node','eventIndex','beforeSequence','afterSequence','files'} and
             point['event']==name and point['node']=='node-1','queue storage original owner')
        marker=markers[name];before=point['beforeSequence'];after=point['afterSequence']
        need(all(type(point[k]) is int for k in ('eventIndex','beforeSequence','afterSequence')) and
             before==marker['sequence'] and point['eventIndex']==marker['eventIndex'] and
             0<=before<=after<len(trace['changes']),'queue storage exact resource interval')
        actual=value['copies'][name]
        need(actual==value['original'] and point['files']==file_rows(actual['files']),'queue storage original inventory')
        # CONTROL/WAITER callbacks may run while files are copied. Storage may
        # not change at any resource transition in the original interval.
        for row in trace['changes'][before:after+1]:
            need(publication.usage(row['usage'])==value['storage'],'queue storage original reservations')
        original=value['original']
        observations.append(dict(event=name,node='node-1',eventIndex=point['eventIndex'],beforeSequence=before,afterSequence=after,
            inventorySha256=publication.sha(publication.f.canonical(original['files'])),
            physicalBytes=original['physicalBytes'],physicalApplicationBytes=original['physicalApplicationBytes'],
            imageCopies=original['imageCopies'],reservedMetadataBytes=value['storage']['metadata'],
            reservedStagingBytes=value['storage']['staging'],queuedBytes=marker['queued']))
    return dict(schema=SCHEMA,status='PASS',sameOwnerStorageObserved=True,points=observations,
                combinedMaximumQualified=False,phase3Complete=False)


def check_result(value,*,image_bytes=None):
    need(type(value) is dict and set(value)=={'schema','status','sameOwnerStorageObserved','points','combinedMaximumQualified','phase3Complete'} and
         value['schema']==SCHEMA and value['status']=='PASS' and value['sameOwnerStorageObserved'] is True and
         value['combinedMaximumQualified'] is False and value['phase3Complete'] is False and
         type(value['points']) is list and len(value['points'])==2,'queue storage result scope')
    numbers=('eventIndex','beforeSequence','afterSequence','physicalBytes','physicalApplicationBytes','imageCopies',
             'reservedMetadataBytes','reservedStagingBytes','queuedBytes')
    for name,row in zip(names(),value['points']):
        need(type(row) is dict and set(row)=={'event','node','inventorySha256',*numbers} and row['event']==name and row['node']=='node-1' and
             all(type(row[k]) is int and row[k]>=0 for k in numbers) and row['beforeSequence']<=row['afterSequence'] and
             type(row['inventorySha256']) is str and len(row['inventorySha256'])==64 and
             all(c in '0123456789abcdef' for c in row['inventorySha256']) and
             1<=row['imageCopies']<=7 and 0<row['physicalApplicationBytes']<row['physicalBytes'] and
             row['physicalApplicationBytes']<=row['reservedStagingBytes'] and
             row['physicalBytes']-row['physicalApplicationBytes']<=row['reservedMetadataBytes']<=384*publication.MIB and
             0<row['queuedBytes']<=64*publication.MIB,'queue storage result observation')
        if image_bytes is not None:
            need(row['physicalApplicationBytes']==row['imageCopies']*image_bytes,'queue storage maximum original images')
    need(value['points'][0]['inventorySha256']==value['points'][1]['inventorySha256'], 'queue storage result original inventory')
