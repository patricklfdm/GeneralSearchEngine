"""Same-callback files and leases in an independently replayed native history.

The complete required-four physical/resource reader must run first. This
projection adds a simultaneous image observation; capture hashes alone cannot
authorize its files. Equal-content files remain separate physical copies.
"""
from collections import Counter, defaultdict
import re
from . import native_resource_evidence as native
from . import joining_source_retirement as retirement
from . import replica_storage_coverage as storage

t=storage.t;need=t.need
SCHEMA='gse-v53-native-retirement-storage-v1'
SCOPE='one-owner-source-retirement-callback-file-extents'
FALSES=('combinedResourcesQualified','wholeReaderMemoryQualified','finalSourceCohortQualified','phase3Complete')


def digest(value):return retirement.sha(retirement.f.canonical(value))


def image_identity(size,sha):
    need(type(size) is int and 0<size<=64*t.MIB and type(sha) is str and re.fullmatch(storage.HEX,sha),
         'native storage exact target image')


def inventory(files):
    if type(files) is retirement.capture_objects.Files:
        return {name:value if 'directory' in value else dict(bytes=value['size'],sha256=value['sha256'])
                for name,value in files.identities().items()}
    return {name:dict(directory=True) if raw is None else dict(bytes=len(raw),sha256=retirement.sha(raw))
            for name,raw in files.items()}


def rows(transactions):
    result=[dict(row,node=tx['node'],scope=tx['scope'],files=inventory(row['files']))
            for tx in transactions for row in tx['steps']]
    result.sort(key=lambda row:row['event'])
    need(result and len(result)<=retirement.MAXIMUM_CAPTURES and
         len({v['event'] for v in result})==len(result),'native storage complete unique callbacks')
    return result


def ordinal_plans(observed):
    # These callbacks delete source UUID groups, not floor copies. The complete
    # independently validated transactions supply each immutable floor's image
    # ordering, never just a surviving subset at the selected peak.
    plans=defaultdict(lambda:defaultdict(set))
    for row in observed:
        for name in row['files']:
            prefix,_,image=name.rpartition('/')
            if prefix.startswith('floor-copies/') and name.endswith('.image'):
                plans[row['node']][prefix].add(image)
    return {node:{prefix:sorted(images) for prefix,images in own.items()} for node,own in plans.items()}


def point(row,index,traces,boundaries,events,state,ordinals):
    node=row['node'];at=row['event'];end=row['capturedEvent']
    need(type(at) is int and type(end) is int and 0<=at<end<len(events), 'native storage original callback range')
    event=events[at];capture=events[end]
    need(event.get('node')==capture.get('node')==node and event.get('event')==capture.get('point')==row['point'] and
         event.get('scope','network-owner')==capture.get('scope')==row['scope'] and
         capture.get('event')==retirement.EVENT,'native storage original callback identity')
    before=boundaries[at];after=boundaries[end]
    need(before['node']==after['node']==node and before['eventIndex']==at and after['eventIndex']==end,
         'native storage original boundary identity')
    first,last=before['sequence'],after['sequence'];trace=traces[node]
    need(type(first) is int and type(last) is int and 0<=first<=last<len(trace['changes']),
         'native storage original resource interval')
    for change in trace['changes'][first+1:last+1]:
        need(all(v['unit'] in ('CONTROL','WAITER') for v in change['removed']+change['added']),
             'native storage changed during capture')
    limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
    usage=t.usage(state,limits);t.same_usage(before['usage'],usage)
    physical=storage.compare(row['files'],state,ordinals)
    image_owners={path:charge['owner'] for charge in physical['required'] if charge['unit']=='APPLICATION' for path in charge['paths']}
    images=[dict(path=name,owner=image_owners[name],**value) for name,value in sorted(row['files'].items()) if name.endswith('.image')]
    need(set(image_owners)=={v['path'] for v in images} and len({v['owner'] for v in images})==len(images),
         'native storage exclusive original images')
    extents=Counter();counts=Counter()
    for charge in physical['required']:
        extents[charge['unit']]+=charge['bytes']
        if charge['bytes']>0:counts[charge['unit']]+=1
    protected=sum(v['bytes'] for v in state.values() if v['unit'] in t.PROTECTED)
    return dict(node=node,eventIndex=at,capturedEventIndex=end,point=row['point'],scope=row['scope'],
        beforeSequence=first,afterSequence=last,captureSha256=capture['sha256'],
        resourceTraceSha256=next(v['sha256'] for v in index['owners'] if v['identity']['node']==node),
        inventorySha256=digest(row['files']),physicalBytes=physical['physicalBytes'],
        physicalFiles=physical['physicalFiles'],physicalDirectories=physical['physicalDirectories'],
        physicalApplicationBytes=extents['APPLICATION'],physicalMetadataBytes=sum(extents[k] for k in t.META),
        physicalStagingBytes=sum(extents[k] for k in t.STAGING),nonemptyPhysicalOwnerCounts=dict(sorted(counts.items())),
        images=images,usage=usage,limits=dict(zip(('metadata','staging','queued'),limits)),
        unspentProtectedHeadroomBytes=36*t.MIB-protected)


def project(observed,index,traces,boundaries,events,*,application_bytes,application_sha256,resource_profile):
    image_identity(application_bytes,application_sha256)
    identities={v['identity']['node']:v['identity'] for v in index['owners']}
    native.replay(index,traces,boundaries,events,identities,index['root'],resource_profile=resource_profile)
    need(observed and [r['event'] for r in observed]==sorted({r['event'] for r in observed}),
         'native storage ordered unique callbacks')
    plans=ordinal_plans(observed);states={node:{} for node in traces};cursors=dict.fromkeys(traces,0);points=[]
    for row in observed:
        node=row['node'];at=row['event']
        need(node in traces and type(at) is int and 0<=at<len(boundaries),'native storage callback owner')
        sequence=boundaries[at]['sequence'];state=states[node]
        while cursors[node]<=sequence:
            change=traces[node]['changes'][cursors[node]]
            for old in change['removed']:del state[t.key(old)]
            for new in change['added']:state[t.key(new)]=new
            cursors[node]+=1
        points.append(point(row,index,traces,boundaries,events,state,plans.get(node,{})))
    matches=[p for p in points if len(p['images'])==t.COUNTS['APPLICATION'] and
             all(v['bytes']==application_bytes and v['sha256']==application_sha256 for v in p['images'])]
    return dict(schema=SCHEMA,status='PARTIAL',scope=SCOPE,root=index['root'],eventsSha256=index['eventsSha256'],
        boundariesSha256=index['boundariesSha256'],callbacks=len(points),callbacksSha256=digest(points),
        requiredImageCopies=t.COUNTS['APPLICATION'],applicationBytes=application_bytes,applicationSha256=application_sha256,
        matchingCallbacks=len(matches),firstMatch=matches[0] if matches else None,**dict.fromkeys(FALSES,False))


def derive(root,*,application_bytes,application_sha256,bootstrap_source,wire_layout,resource_profile):
    index,traces,boundaries,events=native.load(root)
    observed=rows(retirement.collect(root,events,bootstrap_source=bootstrap_source,wire_layout=wire_layout))
    return project(observed,index,traces,boundaries,events,application_bytes=application_bytes,
                   application_sha256=application_sha256,resource_profile=resource_profile)


def check_result(value,*,application_bytes,application_sha256):
    """Receipt shape only. Acceptance independently derives this from the raw history."""
    image_identity(application_bytes,application_sha256)
    fields={'schema','status','scope','root','eventsSha256','boundariesSha256','callbacks','callbacksSha256',
            'requiredImageCopies','applicationBytes','applicationSha256','matchingCallbacks','firstMatch',*FALSES}
    need(type(value) is dict and set(value)==fields and value['schema']==SCHEMA and value['status']=='PARTIAL' and
         value['scope']==SCOPE and all(value[k] is False for k in FALSES), 'native storage result scope')
    for key in ('root','eventsSha256','boundariesSha256','callbacksSha256'):
        need(type(value[key]) is str and re.fullmatch(storage.HEX,value[key]),'native storage result original digest')
    need(type(value['callbacks']) is int and type(value['matchingCallbacks']) is int and
         1<=value['matchingCallbacks']<=value['callbacks']<=retirement.MAXIMUM_CAPTURES and
         type(value['requiredImageCopies']) is int and value['requiredImageCopies']==t.COUNTS['APPLICATION'] and
         type(value['applicationBytes']) is int and value['applicationBytes']==application_bytes and
         value['applicationSha256']==application_sha256,'native storage missing simultaneous original maximum images')
    row=value['firstMatch']
    numbers=('eventIndex','capturedEventIndex','beforeSequence','afterSequence','physicalBytes','physicalFiles','physicalDirectories',
             'physicalApplicationBytes','physicalMetadataBytes','physicalStagingBytes','unspentProtectedHeadroomBytes')
    hashes=('captureSha256','resourceTraceSha256','inventorySha256')
    need(type(row) is dict and set(row)=={'node','point','scope','images','usage','limits','nonemptyPhysicalOwnerCounts',*numbers,*hashes} and
         row['node'] in {'node-'+str(i) for i in range(1,7)} and type(row['scope']) is str and bool(row['scope']) and
         type(row['point']) is str and row['point'].startswith(('SOURCE_RETIREMENT_','JOURNAL_ROTATION_')) and
         all(type(row[k]) is int and row[k]>=0 for k in numbers) and
         row['eventIndex']<row['capturedEventIndex']<65536 and row['beforeSequence']<=row['afterSequence'] and
         all(type(row[k]) is str and re.fullmatch(storage.HEX,row[k]) for k in hashes), 'native storage result original point')
    images=row['images']
    need(type(images) is list and len(images)==t.COUNTS['APPLICATION'] and all(type(v) is dict and
         set(v)=={'path','owner','bytes','sha256'} and type(v['bytes']) is int and v['bytes']==application_bytes and
         v['sha256']==application_sha256 and type(v['path']) is str and v['path'].endswith('/'+application_sha256+'.image') and
         type(v['owner']) is str and bool(v['owner']) for v in images) and
         [v['path'] for v in images]==sorted({v['path'] for v in images}) and len({v['owner'] for v in images})==len(images),
         'native storage result seven original copies')
    counts=row['nonemptyPhysicalOwnerCounts'];usage=row['usage'];limits=row['limits']
    native.publication.usage(usage)  # Strict integer/accounting shape; CONTROL remains separately visible.
    need(type(counts) is dict and all(k in t.COUNTS and type(v) is int and 0<v<=t.COUNTS[k] for k,v in counts.items()) and
         counts.get('APPLICATION')==usage['counts'].get('APPLICATION')==7 and
         all(v<=usage['counts'].get(k,0) for k,v in counts.items()), 'native storage result physical owner counts')
    need(limits==dict(metadata=384*t.MIB,staging=native.resource_policy.LIMITS[native.resource_policy.DEFAULT],queued=64*t.MIB) and
         all(type(v) is int for v in limits.values()) and
         row['physicalApplicationBytes']==7*application_bytes and row['physicalMetadataBytes']>0 and
         row['physicalBytes']==row['physicalApplicationBytes']+row['physicalMetadataBytes'] and
         row['physicalMetadataBytes']<=usage['metadata']<=limits['metadata'] and
         usage['metadata']+row['unspentProtectedHeadroomBytes']<=limits['metadata'] and
         row['physicalApplicationBytes']<=row['physicalStagingBytes']<=usage['staging']<=limits['staging'] and
         0<=usage['queued']<=limits['queued'] and row['physicalFiles']>=7 and
         row['unspentProtectedHeadroomBytes']<=36*t.MIB,'native storage result simultaneous extents')
