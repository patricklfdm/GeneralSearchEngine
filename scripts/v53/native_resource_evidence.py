"""Bind original native events and disk identities to complete budget journals.

Accounting peaks include successful temporary reservations between callbacks.
Publication bytes still require their independent physical reader; this does
not establish every non-publication physical ownership/queue lifetime.
"""
import argparse
import json
from pathlib import Path

from . import native_resource_policy as resource_policy
from . import wire_archive
from . import bootstrap_replay_contract as source_policy
from . import resource_transitions as transitions
from . import publication_resource_evidence as publication

collection,need=transitions.collection,transitions.need
DIRECTORY='resource-transition-captures'


def load(root):
    root=Path(root);directory=root/DIRECTORY
    need(directory.is_dir() and not directory.is_symlink(),'native resources missing collection')
    index=collection.read_json(directory,'index.json',16384)
    fields={'schema','root','eventsSha256','boundariesSha256','owners'}
    need(type(index) is dict and index.get('schema') in ('gse-v53-resource-capture-index-v1','gse-v53-resource-capture-index-v2'),
         'native resources index schema')
    if index['schema']=='gse-v53-resource-capture-index-v2':fields.add('closingOwners')
    need(set(index)==fields and type(index['owners']) is list and
         1<=len(index['owners'])<=6,'native resources index')
    event_raw=collection.snapshot.s.regular(root/'events.json',collection.EVENT_BYTES)
    boundary_raw=collection.snapshot.s.regular(directory/'boundaries.json',collection.EVENT_BYTES)
    need(collection.digest(event_raw)==index['eventsSha256'] and collection.digest(boundary_raw)==index['boundariesSha256'],
         'native resources original event/boundary digest')
    events=collection.read_json(root,'events.json',collection.EVENT_BYTES)
    boundaries=collection.read_json(directory,'boundaries.json',collection.EVENT_BYTES)
    traces={};names={'index.json','boundaries.json'};total=len(boundary_raw)
    for owner in index['owners']:
        need(type(owner) is dict and set(owner)=={'identity','path','sha256','registeredAt'} and
             type(owner['identity']) is dict and type(owner['identity'].get('node')) is str,
             'native resources owner reference')
        node=owner['identity']['node'];name=node+'.json'
        need(node in {'node-'+str(i) for i in range(1,7)} and owner['path']==name and node not in traces,
             'native resources unique owner path')
        raw,value=transitions.read(directory/name);total+=len(raw)
        need(total<=256*transitions.MIB and collection.digest(raw)==owner['sha256'],'native resources trace digest/capacity')
        traces[node]=value;names.add(name)
    need({p.name for p in directory.iterdir()}==names,'native resources unobserved member')
    return index,traces,boundaries,events


def replay(index,traces,boundaries,events,identities,root,*,resource_profile=resource_policy.SMALL):
    staging=resource_policy.check(resource_profile)
    owners=index['owners'];nodes=[v['identity']['node'] for v in owners]
    need(index['root']==root and nodes==sorted(identities) and set(traces)==set(identities) and
         all(v['identity']==identities[v['identity']['node']] for v in owners),
         'native resources original complete identities')
    need(type(events) is list and type(boundaries) is list and 0<len(events)==len(boundaries)<=65536,
         'native resources complete event boundaries')
    registered={};results={}
    for owner in owners:
        node=owner['identity']['node'];start=owner['registeredAt']
        need(type(start) is int and 0<=start<len(events),'native resources registration position')
        registered[node]=start
        trace=traces[node]
        need((trace.get('metadataLimit'),trace.get('stagingLimit'),trace.get('queueLimit'))==
             (384*transitions.MIB,staging,64*transitions.MIB),'native resources original limits')
        results[node]=transitions.replay(trace)
        need(results[node]['transitions']>1,'native resources unobserved budget lifetime')
    previous={n:0 for n in nodes};counts={n:0 for n in nodes}
    for at,(event,boundary) in enumerate(zip(events,boundaries)):
        need(type(event) is dict and event.get('node') in identities and type(event.get('event')) is str,
             'native resources original event owner')
        node=event['node'];rows=traces[node]['changes']
        need(type(boundary) is dict and set(boundary)=={'eventIndex','node','sequence','usage'} and
             type(boundary['eventIndex']) is int and boundary['eventIndex']==at and boundary['node']==node and
             type(boundary['sequence']) is int and previous[node]<=boundary['sequence']<len(rows) and at>=registered[node],
             'native resources exact event sequence')
        sequence=boundary['sequence'];transitions.same_usage(boundary['usage'],rows[sequence]['usage'])
        previous[node]=sequence;counts[node]+=1
    need(all(counts.values()),'native resources omitted owner events')
    return resource_policy.receipt(dict(status='PASS',owners=results,eventBoundaries=len(boundaries),ownerEvents=counts,
                nativeBudgetAccountingQualified=True,wholeRuntimeResourcesQualified=False,phase3Complete=False),resource_profile)


def bind_publications(transactions,boundaries):
    count=0
    for transaction in transactions:
        for row in transaction:
            point=boundaries[row['eventIndex']]
            need(point['node']==row['node'] and publication.usage(point['usage'])==row['storage'],
                 'native resources original publication storage boundary')
            count+=1
    return count


def validate(directory,profile='stable',progress=None,*,source_control=False,control_closes=False,export_ownership=False,direct_exports=False,joining_requests=False,joining_extents=False,published_probe=False,session_extents=False,complete_exports=False,voting_control=False,slot_control=False,activation_control=False,joined_files=False,joined_closes=False,export_bindings_out=None, bootstrap_source='EMPTY', wire_layout='JSON', resource_profile=resource_policy.SMALL):
    resource_policy.scope(resource_profile,bootstrap_source,wire_layout)
    resource_args=resource_policy.options(resource_profile)
    source_args = source_policy.options(bootstrap_source,wire_layout)
    need(bootstrap_source==source_policy.EMPTY or profile=='5-REPLACE-required-four', 'native resources bootstrap source profile')
    need(export_bindings_out is None or type(export_bindings_out) is dict and not export_bindings_out and complete_exports is True,
         'native resources empty complete-export output only')
    need(type(joined_closes) is bool and (not joined_closes or profile=='5-REPLACE-required-four'), 'native resources joined closes policy')
    need(type(joined_files) is bool and (not joined_files or profile=='5-REPLACE-required-four'), 'native resources joined files policy')
    need(type(activation_control) is bool and (not activation_control or profile in ('stable','5-REPLACE-required-four')), 'native resources activation control policy')
    need(type(slot_control) is bool and (not slot_control or profile in ('stable','5-REPLACE-required-four')), 'native resources slot control policy')
    if activation_control:slot_control=True
    need(type(voting_control) is bool and (not voting_control or profile in ('stable','5-REPLACE-required-four')), 'native resources voting control policy')
    if slot_control:voting_control=True
    need(type(complete_exports) is bool and (not complete_exports or profile=='5-REPLACE-required-four'),
         'native resources complete export policy')
    if complete_exports:
        source_control=control_closes=export_ownership=direct_exports=published_probe=session_extents=True
    need(type(session_extents) is bool and (not session_extents or export_ownership and control_closes and profile=='5-REPLACE-required-four'),
         'native resources session extents policy')
    need(type(published_probe) is bool and (not published_probe or export_ownership and control_closes and profile=='5-REPLACE-required-four'),
         'native resources published probe policy')
    need(type(joining_extents) is bool and (not joining_extents or joining_requests),'native resources joining extents policy')
    need(type(joining_requests) is bool and (not joining_requests or export_ownership and control_closes and profile=='5-REPLACE-required-four'),
         'native resources joining requests policy')
    need(type(source_control) is bool and type(control_closes) is bool,'native resources source-control policy')
    need(type(export_ownership) is bool and (not export_ownership or control_closes),'native resources export-ownership policy')
    need(type(direct_exports) is bool and (not direct_exports or export_ownership and profile in ('stable','5-REPLACE-required-four')),
         'native resources direct-export policy')
    root=Path(directory);before=source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)
    if joined_closes:
        from . import joining_owner_close
        # Reject a historical unobserved original before expensive physical replay.
        joining_owner_close.intervals(collection.read_json(root,'events.json',collection.EVENT_BYTES),'node-6')
    if joined_files:
        from . import storage_transfer_evidence
        captured=root/storage_transfer_evidence.DIRECTORY
        need(captured.is_dir() and not captured.is_symlink(),'storage transfer missing original capture')
    if control_closes:need((root/'control-close-captures').is_dir(),'native resources missing control close observations')
    physical=publication.validate(root,profile,progress,resource_transitions=True,control_closes=control_closes,**source_args)
    if profile=='stable':
        states,rounds,selection,identities=publication.native.physical(root,confirmed_retention=True)
        authority=selection['root'];preceding=physical;closing=set(identities)
    elif profile=='5-REPLACE-required-four':
        from . import required_four_ledgers as ledgers
        preceding=ledgers.validate(root,progress,**source_args)
        controls=ledgers.maintenance.exports.control_reader(root,**source_args);model=controls.model
        network=ledgers.maintenance.exports.network.network
        identities=network.s.catalog.identities(model.states[-1]['identities']);authority=model.root
        closing=set(identities)-{model.joining}
    else:raise ValueError('native resources unknown profile')
    index,traces,boundaries,events=load(root)
    result=replay(index,traces,boundaries,events,identities,authority,**resource_args)
    from . import owner_close_evidence
    closed=owner_close_evidence.replay(index,traces,boundaries,events,closing)
    joining_closed=None
    if joined_closes:
        need(closed['status']=='PASS','native resources all network close intervals required')
        joining_closed=joining_owner_close.replay(events,traces,boundaries,model.joining)
    transactions=publication.collect(root,events)
    count=bind_publications(transactions,boundaries)
    from . import publication_generation_resources
    generations=publication_generation_resources.replay(transactions,traces,boundaries)
    from . import native_source_resources
    wires=wire_archive.read(root,'wire.json',bootstrap_source=bootstrap_source,layout=wire_layout)
    cleanup=None;export_bindings={} if complete_exports else None
    if control_closes:
        from . import control_close_evidence,native_control_closes
        expected_extents=None
        if joining_extents:
            from . import joining_metadata_extents
            expected_extents=joining_metadata_extents.derive(controls)
        expected_sessions=None
        if session_extents:
            from . import session_content_extents
            expected_sessions=session_content_extents.derive(controls)
        cleanup=native_control_closes.replay(events,wires,traces,boundaries,identities,authority,control_close_evidence.load(root,index),
                                           export_ownership=export_ownership,joining_requests=joining_requests,joining_extents=expected_extents,session_extents=expected_sessions,bindings=export_bindings)
        source_result=cleanup['precondition']
    else:source_result=native_source_resources.replay(events,wires,traces,boundaries,identities,authority,require_complete=source_control)
    direct=None
    if direct_exports and profile=='stable':
        from . import direct_export_evidence
        direct=direct_export_evidence.replay(traces,control_close_evidence.load(root,index),
                direct_export_evidence.derive(states,rounds,selection,events,boundaries))
    transport=None;floors=None;receiving=None;bases=None;published=None;joined=None;files=None
    if profile=='5-REPLACE-required-four':
        from . import transport_resource_evidence
        # Attempts that never reached a connected wire boundary must remain
        # explicit gaps, not be assigned to a later identical connected retry.
        transport=transport_resource_evidence.replay(events,wires,traces,boundaries,identities,authority,require_all_frames=False)
        from . import floor_resource_evidence, receive_resource_evidence, basis_resource_evidence
        reader=floor_resource_evidence.maintenance.Replay(root,**source_args);reader.run()
        need(reader.events==events,'native resources original maintenance event input')
        floors=floor_resource_evidence.replay(floor_resource_evidence.plans(reader),events,traces,boundaries)
        receiving=receive_resource_evidence.replay(receive_resource_evidence.derive(reader),events,traces,boundaries)
        bases=basis_resource_evidence.replay(basis_resource_evidence.derive(reader),events,traces,boundaries)
        from . import joined_handoff_resources
        handoff=joined_handoff_resources.original(root,**source_args)
        joined=joined_handoff_resources.replay(joined_handoff_resources.project(handoff),events,traces,boundaries,**resource_args)
        if joined_files:
            from . import joined_file_resources
            files=joined_file_resources.replay(joined_file_resources.derive(handoff.owner,reader),events,traces,boundaries,
                                              joined_file_resources.transfers.load(root,index))
        if direct_exports:
            from . import required_four_direct_exports
            direct=required_four_direct_exports.replay(traces,control_close_evidence.load(root,index),reader,boundaries,bindings=export_bindings)
        if published_probe:
            from . import published_prefix_probe_evidence
            # Derive the permit from the original quorum/head confirmations.
            # Local probe markers never synthesize a network exchange or permit.
            controls.run(ledgers.maintenance.exports.content(root,**source_args))
            need(controls.events==events,'native resources original published probe event input')
            published=published_prefix_probe_evidence.replay(traces,control_close_evidence.load(root,index),controls,boundaries,bindings=export_bindings)
    export_coverage=None
    if complete_exports:
        from . import export_allocation_coverage
        export_coverage=export_allocation_coverage.replay(traces,control_close_evidence.load(root,index),export_bindings)
    voting=None
    if voting_control:
        from . import voting_control_resources
        voting=voting_control_resources.replay(events,wires,traces,boundaries,identities,authority)
    slots=None
    if slot_control:
        from . import slot_control_resources
        expected_publications=(slot_control_resources.publications(rounds,selection,identities) if profile=='stable' else
                               slot_control_resources.required_four_publications(model,identities))
        slots=slot_control_resources.replay(events,wires,traces,boundaries,identities,authority,
                expected_publications,transactions)
    activation=None
    if activation_control:
        from . import activation_control_resources
        activation=activation_control_resources.replay(events,wires,traces,boundaries,identities,authority,
                expected_publications,transactions)
    need(source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)==before,'native resources original changed')
    if export_bindings_out is not None:
        need(result['status']=='PASS' and cleanup['status']=='PASS','native resources complete original before binding output')
        # Output only after all original readers and final immutability pass.
        # No caller-supplied proof is accepted; failures publish nothing.
        export_allocation_coverage.publish(export_bindings_out,list(export_bindings.values()))
    return resource_policy.receipt(source_policy.receipt(dict(result,status=cleanup['status'] if cleanup else result['status'],scope='native-owner-accounting-with-original-publication-boundaries',profile=profile,
                precondition=preceding,publicationResources=physical,publicationBoundaries=count,publicationGenerationResources=generations,transportResources=transport,
                floorResources=floors,receivingResources=receiving,basisResources=bases,ownerCloseResources=closed,joinedOwnerCloses=joining_closed,joinedHandoffResources=joined,joinedFileResources=files,
                sourceControlResources=source_result,sourceCleanupIntervals=cleanup,directExportOwnership=direct,publishedPrefixProbe=published,exportAllocationCoverage=export_coverage,
                votingControlResources=voting,slotControlResources=slots,activationControlResources=activation,physicalPeakQualified=False,controlLifetimesQualified=False,finalSourceCohortQualified=False),bootstrap_source,wire_layout),resource_profile)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root')
    p.add_argument('--profile',choices=('stable','5-REPLACE-required-four'),default='stable')
    p.add_argument('--source-control',action='store_true');p.add_argument('--control-closes',action='store_true')
    p.add_argument('--export-ownership',action='store_true');p.add_argument('--direct-exports',action='store_true');p.add_argument('--joining-requests',action='store_true')
    p.add_argument('--joining-extents',action='store_true');p.add_argument('--published-probe',action='store_true');p.add_argument('--session-extents',action='store_true');p.add_argument('--complete-exports',action='store_true');p.add_argument('--voting-control',action='store_true');p.add_argument('--slot-control',action='store_true');p.add_argument('--activation-control',action='store_true');p.add_argument('--joined-files',action='store_true');p.add_argument('--joined-closes',action='store_true');a=p.parse_args()
    print(json.dumps(validate(a.root,a.profile,source_control=a.source_control,control_closes=a.control_closes,export_ownership=a.export_ownership,direct_exports=a.direct_exports,joining_requests=a.joining_requests,joining_extents=a.joining_extents,published_probe=a.published_probe,session_extents=a.session_extents,complete_exports=a.complete_exports,voting_control=a.voting_control,slot_control=a.slot_control,activation_control=a.activation_control,joined_files=a.joined_files,joined_closes=a.joined_closes),sort_keys=True))
