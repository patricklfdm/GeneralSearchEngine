package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private initial projection. Only absent scratch is written; no target, plan, seal,
 * durable history allocation, election or ownership receipt is created here. */
final class MembershipBootstrapSeed {
    final Decoded rootRecord,genesis;
    final MembershipRoot root;
    final MembershipCapsule capsule;
    final long sequence;
    private final byte[] application;
    private final List<MembershipIdentity> identities;
    private final Map<String,Object> descriptor;

    private MembershipBootstrapSeed(MembershipBootstrapRequest<?,?> request,UUID history,long sequence,
            byte[] image,String schema,String indexes,String sourceDigest,Map<String,Object> descriptor) {
        this.sequence=sequence;application=image.clone();identities=request.targets().stream().map(MembershipBootstrapTarget::identity).toList();
        this.descriptor=decodeDescriptor(descriptor);
        var g=new TreeMap<String,Object>();g.put("application",hash(image));g.put("baseSequence",sequence);
        g.put("groupId",request.groupId().value().toString());g.put("historyId",history.toString());
        g.put("schema",schema);g.put("indexes",indexes);g.put("source",request.source().name());g.put("sourceDigest",sourceDigest);
        genesis=record("GENESIS",g);var r=new TreeMap<>(g);r.remove("application");r.remove("source");r.remove("sourceDigest");
        var core=object(this.descriptor.get("core"));r.put("codecId",core.get("codecId"));r.put("codecVersion",number(core.get("codecVersion")));
        r.put("configurationId",request.configurationId());r.put("genesis",genesis.digest());r.put("initial",identities.stream().map(MembershipBootstrapSeed::identity).toList());
        r.put("limits",hash(canonical(CATALOG.get("resources"),16384)));rootRecord=record("ROOT",r);
        root=new MembershipRoot(request.groupId(),history,rootRecord.rootDigest());
        capsule=initial(rootRecord,genesis,image);
    }
    /** Metadata-only restoration of an exact retained projection, not typed admission or a seal. */
    static MembershipBootstrapSeed restore(byte[] root,byte[] genesis,byte[] image,Map<String,Object> descriptor) {
        return new MembershipBootstrapSeed(decode(root,"records","ROOT"),decode(genesis,"records","GENESIS"),image,descriptor);
    }
    private MembershipBootstrapSeed(Decoded rootRecord,Decoded genesis,byte[] image,Map<String,Object> descriptor) {
        this.rootRecord=rootRecord;this.genesis=genesis;this.descriptor=decodeDescriptor(descriptor);application=image.clone();
        root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rootRecord.value().get("groupId"))),UUID.fromString((String)rootRecord.value().get("historyId")),rootRecord.rootDigest());
        sequence=number(genesis.value().get("baseSequence"));MembershipValidation.position(sequence);
        identities=list(rootRecord.value().get("initial")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
        MembershipApplicationImage.unpack(image);capsule=initial(rootRecord,genesis,image);
        require(descriptor.keySet().equals(Set.of("application","core","paths","source","sourceInventory","identities")),"bootstrap retained descriptor keys");
        var core=object(descriptor.get("core"));var config=object(descriptor.get("application"));
        require(rootRecord.value().get("codecId").equals(core.get("codecId")) && number(rootRecord.value().get("codecVersion"))==number(core.get("codecVersion"))
                && rootRecord.value().get("schema").equals(hash(canonical(Map.of("schemaIdentity",core.get("schemaIdentity"),"application",config),1024*1024)))
                && rootRecord.value().get("indexes").equals(hash(canonical(config.get("indexes"),262144))),"bootstrap retained application descriptor binding");
        require(descriptor.get("identities").equals(rootRecord.value().get("initial")) && descriptor.get("source").equals(genesis.value().get("source")),"bootstrap retained identity/source binding");
        var inventory=list(descriptor.get("sourceInventory"));boolean empty=descriptor.get("source").equals("EMPTY");
        require(empty?inventory.isEmpty() && sequence==0:inventory.size()==3 && hash(canonical(inventory,65536)).equals(genesis.value().get("sourceDigest")),"bootstrap retained source inventory binding");
        if(!empty)for(int n=0;n<inventory.size();n++) {
            var row=object(inventory.get(n));require(row.keySet().equals(Set.of("path","kind","size","sha256")) && row.get("path").equals(MembershipApplicationImage.MEMBERS.get(n))
                    && number(row.get("kind"))==1 && number(row.get("size"))>0,"bootstrap retained source member");MembershipValidation.digest((String)row.get("sha256"));
        }
        var paths=list(descriptor.get("paths"));require(paths.size()==(empty?1:2)+2*identities.size(),"bootstrap retained path count");
        MembershipValidation.disjoint(paths.stream().map(AdmissionConfiguration::path).toList());
    }
    private static MembershipCapsule initial(Decoded rootRecord,Decoded genesis,byte[] image) {
        var catalog=record("CATALOG",MembershipCapsule.initialCatalog(rootRecord,genesis.value()));
        var objects=new TreeMap<String,byte[]>();for(var frame:List.of(rootRecord,genesis,catalog))objects.put(frame.digest(),frame.bytes());
        var images=Map.of(hash(image),(long)image.length);
        var cap=record("CAPSULE",Map.of("root",rootRecord.rootDigest(),"application",hash(image),"catalog",catalog.digest(),
                "cut",catalog.value().get("cut"),"initial",genesis.digest(),"inventory",hash(MembershipSourcePacket.index(objects,images)),"items",List.of()));
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(cap,objects,images));
        return MembershipCapsule.verify(rootRecord,packet,Map.of(hash(image),image),Set.of());
    }
    private static Decoded record(String kind,Map<String,Object> value){return decode(encode("records",kind,value),"records",kind);}
    static Map<String,Object> identity(MembershipIdentity id){return Map.of("node",id.nodeId().value(),"storage",id.storageId().toString(),"host",id.endpoint().host(),"port",(long)id.endpoint().port());}
    private static Map<String,Object> decodeDescriptor(Map<String,Object> value){return object(parse(canonical(value,1024*1024),1024*1024));}
    Map<String,Object> descriptor(){return decodeDescriptor(descriptor);}
    byte[] application(){return application.clone();}
    Map<String,byte[]> images(){return Map.of(hash(application),application.clone());}

    /** Generation zero has only a local counter-one fence. No BASIS, SELECTED or vote. */
    Map<String,byte[]> payloads(MembershipIdentity local) {
        require(identities.contains(local),"bootstrap foreign target identity");String node=local.nodeId().value(),rootHash=root.manifestDigest();
        var value=new TreeMap<String,Object>();value.put("root",rootHash);value.put("view",capsule.context.authority());value.put("basisId",null);
        value.put("ballot",Map.of("counter",1L,"proposer",node,"incarnation",local.storageId().toString()));var promise=record("PROMISE",value);
        var generation=new TreeMap<String,byte[]>();generation.put("source.gscp",capsule.packet.bytes());generation.put("promise.gsr",promise.bytes());
        generation.put(hash(application)+".image",application.clone());
        var m=new TreeMap<String,Object>();m.put("root",rootHash);m.put("node",node);m.put("generation","a");m.put("cut",capsule.context.cut);
        m.put("application",hash(application));m.put("catalog",capsule.terminal().catalog());m.put("capsule",capsule.packet.capsule().digest());
        m.put("promise",promise.digest());m.put("basis",null);m.put("selection",null);m.put("ownedTail",null);
        m.put("files",generation.entrySet().stream().map(row->Map.of("path",row.getKey(),"size",(long)row.getValue().length,"sha256",hash(row.getValue()))).toList());
        var manifest=record("GENERATION",m);generation.put("generation.gsr",manifest.bytes());var files=new TreeMap<String,byte[]>();
        generation.forEach((name,bytes)->files.put("generations/a/"+name,bytes));
        files.put("replica.lock",new byte[0]);files.put("root.gsr",rootRecord.bytes());files.put("genesis.gsr",genesis.bytes());
        files.put("node.gsr",encode("records","NODE",Map.of("identity",identity(local),"root",rootHash)));
        files.put(MembershipBallotAllocator.CURRENT,encode("records","ALLOCATOR",Map.of("counter",1L,"node",node,"root",rootHash)));
        files.put("grants.gsr",promise.bytes());files.put(MembershipPendingAccept.FILE,MembershipPendingAccept.empty());
        files.put("selector.gsr",encode("records","SELECTOR",Map.of("root",rootHash,"node",node,"generation","a","digest",manifest.digest())));
        return Collections.unmodifiableMap(files);
    }
    static Set<String> directories(){return Set.of("sources","generations","generations/a");}
    long payloadBytes(){long result=0;for(var id:identities)for(byte[] bytes:payloads(id).values())result=Math.addExact(result,bytes.length);return result;}

    /** Caller must durably reserve history once in its exact coordinator plan before
     * committing any of these bytes. An occupied scratch/target is never repaired. */
    static <K,T> MembershipBootstrapSeed project(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            UUID history,Path requestedScratch)throws IOException {
        return project(captured,request,history,requestedScratch,null,0).seed();
    }
    /** Revalidate the exact retained plan under the caller's existing coordinator owner.
     * Only a fresh disjoint scratch is written; prepared replicas are never opened. */
    static <K,T> long revalidate(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlanData plan,Path scratch,long otherRetainedBytes)throws IOException {
        Objects.requireNonNull(plan);require(otherRetainedBytes>=0,"bootstrap validation retained byte count");
        require(Arrays.equals(MembershipBootstrapPlanData.create(plan.seed,request).bytes(),plan.bytes()),"bootstrap validation request differs from original plan");
        long completion=new MembershipBootstrapCommitData(plan).completionBytes;
        require(otherRetainedBytes<=request.maxOperationBytes() && completion<=request.maxOperationBytes()-otherRetainedBytes,
                "bootstrap validation completion capacity");
        long reserved=completion+otherRetainedBytes;
        require((long)request.targets().size()*MembershipApplicationImage.MAXIMUM<=request.maxOperationBytes()-reserved,
                "bootstrap validation scratch capacity");
        return project(captured,request,plan.seed.root.historyId(),scratch,plan.seed,reserved).scratchBytes();
    }
    private record Projection(MembershipBootstrapSeed seed,long scratchBytes){}
    private static <K,T> Projection project(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            UUID history,Path requestedScratch,MembershipBootstrapSeed expected,long reserved)throws IOException {
        Objects.requireNonNull(captured);Objects.requireNonNull(request);MembershipValidation.uuid(history);
        boolean planning=expected==null;
        Path scratch=AdmissionPaths.safe(requestedScratch);var paths=new ArrayList<Path>();paths.add(scratch);paths.add(request.operationDirectory());request.sourcePath().ifPresent(paths::add);
        for(var target:request.targets()){paths.add(target.replicaDirectory());paths.add(target.materialization().directory());}
        AdmissionPaths.disjoint(paths);var bindings=new ArrayList<Map<String,Object>>();for(Path path:paths)bindings.add(AdmissionPaths.binding(path));
        absent(request,scratch,planning);var config=AdmissionConfiguration.application(captured);var first=request.targets().getFirst().materialization();
        var core=core(first);for(var target:request.targets())require(core.equals(core(target.materialization())),"bootstrap materialization descriptor mismatch");
        String indexes=hash(canonical(config.get("indexes"),262144));var source=request.sourcePath().orElse(null);
        List<AdmissionFormat.Member> sourceInventory=source==null?List.of():sourceInventory(source,request.maxSourceBytes());
        var sourceKeys=source==null?Map.<String,Object>of():sourceKeys(source,sourceInventory);
        var descriptor=new TreeMap<String,Object>();descriptor.put("application",config);descriptor.put("core",core);descriptor.put("paths",bindings.subList(1,bindings.size()));
        descriptor.put("source",request.source().name());descriptor.put("sourceInventory",sourceInventory.stream().map(v->Map.of("path",v.name(),"kind",v.kind(),"size",v.size(),"sha256",v.digest())).toList());
        descriptor.put("identities",request.targets().stream().map(v->identity(v.identity())).toList());
        // Bound descriptor before the first scratch write. Source/codec rejection also
        // precedes that write for the first target; later failures retain diagnostic scratch.
        descriptor= new TreeMap<>(decodeDescriptor(descriptor));
        require(planning || Arrays.equals(canonical(descriptor,1024*1024),canonical(expected.descriptor(),1024*1024)),"bootstrap validation source/configuration/path drift");
        byte[] image=null;long sequence=-1;long used=reserved;Object scratchKey=null;
        for(int n=0;n<request.targets().size();n++) {
            var storage=request.targets().get(n).materialization();DurableApplicationState<T> imported;
            if(source==null)imported=new DurableApplicationState<>(history,0,List.of(),captured.indexes());
            else {
                imported=captured.newBuilder().readDurableBackup(source,new DurableVerificationConfig<>(storage.storageIdentity(),storage.schemaIdentity(),storage.codec(),
                        storage.codec().codecVersion(),storage.maxEncodedKeyBytes(),storage.maxEncodedDocumentBytes(),storage.maxDocuments()),request.maxSourceBytes());
                checkSource(source,request.maxSourceBytes(),sourceInventory,sourceKeys);require(!history.equals(imported.history()),"bootstrap must allocate a new history");
                require(imported.indexes().stream().map(ReplicaApplication::descriptor).toList().equals(captured.indexes().stream().map(ReplicaApplication::descriptor).toList()),"bootstrap source indexes differ from requested configuration");
            }
            MembershipValidation.position(imported.sequence());
            var state=new DurableApplicationState<>(history,imported.sequence(),imported.documents(),imported.indexes());
            if(n==0) {
                for(var bound:bindings)AdmissionPaths.recheck(bound);absent(request,scratch,planning);
                reserveScratch(used,request.maxOperationBytes());Files.createDirectory(scratch);AdmissionPaths.forceDirectory(scratch.getParent());scratchKey=MembershipBasisSources.key(scratch);
            }
            require(scratchKey.equals(MembershipBasisSources.key(scratch)),"bootstrap scratch directory changed");
            reserveScratch(used,request.maxOperationBytes());Path backup=scratch.resolve("application-"+n);
            byte[] next=MembershipApplicationImage.capture(captured,storage,state,backup);
            used=Math.addExact(used,AdmissionPaths.inventory(backup,MembershipApplicationImage.MAXIMUM).stream().mapToLong(AdmissionFormat.Member::size).sum());
            require(image==null || Arrays.equals(image,next),"bootstrap target codec bytes disagree");
            require(planning || Arrays.equals(expected.application(),next),"bootstrap validation codec/image drift");image=next;sequence=state.sequence();
            for(var bound:bindings)AdmissionPaths.recheck(bound);checkSource(source,request.maxSourceBytes(),sourceInventory,sourceKeys);
            // capture() invokes the core reader after export. No separate decode image
            // is stored and no materialization directory is opened by this projection.
        }
        if(planning)AdmissionPaths.absent(request.operationDirectory());absentTargets(request,planning);
        require(config.equals(AdmissionConfiguration.application(captured)),"bootstrap application descriptor changed");
        for(var target:request.targets())require(core.equals(core(target.materialization())),"bootstrap materialization descriptor changed");
        require(scratchKey.equals(MembershipBasisSources.key(scratch)),"bootstrap scratch directory changed");
        var seed=new MembershipBootstrapSeed(request,history,sequence,image,hash(canonical(Map.of("schemaIdentity",first.schemaIdentity(),"application",config),1024*1024)),indexes,
                source==null?null:hash(canonical(descriptor.get("sourceInventory"),65536)),descriptor);
        if(planning)require(seed.payloadBytes()<=request.maxOperationBytes()-used,"bootstrap seed and scratch exceed operation budget");
        else require(Arrays.equals(seed.rootRecord.bytes(),expected.rootRecord.bytes()) && Arrays.equals(seed.genesis.bytes(),expected.genesis.bytes()),"bootstrap validation root/genesis drift");
        return new Projection(seed,used-reserved);
    }
    private static void reserveScratch(long used,long maximum){require(used<=maximum-MembershipApplicationImage.MAXIMUM,"bootstrap scratch completion capacity");}
    private static void absent(MembershipBootstrapRequest<?,?> request,Path scratch,boolean planning){AdmissionPaths.absent(scratch);if(planning)AdmissionPaths.absent(request.operationDirectory());absentTargets(request,planning);}
    private static void absentTargets(MembershipBootstrapRequest<?,?> request,boolean planning){for(var t:request.targets()){if(planning)AdmissionPaths.absent(t.replicaDirectory());AdmissionPaths.absent(t.materialization().directory());}}
    private static List<AdmissionFormat.Member> sourceInventory(Path path,long maximum)throws IOException {
        var result=AdmissionPaths.inventory(path,Math.min(maximum,MembershipApplicationImage.MAXIMUM-MembershipApplicationImage.OVERHEAD));
        require(result.size()==3 && result.stream().allMatch(v->v.kind()==1 && v.size()>0)
                && result.stream().map(AdmissionFormat.Member::name).toList().equals(MembershipApplicationImage.MEMBERS),"bootstrap source inventory");return result;
    }
    private static Map<String,Object> sourceKeys(Path path,List<AdmissionFormat.Member> files)throws IOException {
        var result=new TreeMap<String,Object>();result.put("",MembershipBasisSources.key(path));
        for(var file:files)result.put(file.name(),Files.readAttributes(path.resolve(file.name()),java.nio.file.attribute.BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey());
        require(result.values().stream().allMatch(Objects::nonNull),"bootstrap source identity unavailable");return result;
    }
    private static void checkSource(Path path,long maximum,List<AdmissionFormat.Member> inventory,Map<String,Object> keys)throws IOException {
        if(path!=null)require(inventory.equals(sourceInventory(path,maximum)) && keys.equals(sourceKeys(path,inventory)),"bootstrap source changed during projection");
    }
    static Map<String,Object> core(DurableStorageConfig<?,?> c) {
        require(c.codec().codecVersion()>0,"bootstrap codec version");
        return Map.of("format",Map.of("family",c.format().family(),"major",c.format().major(),"minor",c.format().minor()),
                "storageIdentity",c.storageIdentity(),"schemaIdentity",c.schemaIdentity(),"codecId",c.codec().codecId(),"codecVersion",c.codec().codecVersion(),
                "bounds",Map.of("maxEncodedKeyBytes",c.maxEncodedKeyBytes(),"maxEncodedDocumentBytes",c.maxEncodedDocumentBytes(),"maxBulkElements",c.maxBulkElements(),"maxDocuments",c.maxDocuments(),
                        "checkpointWalBytes",c.checkpointWalBytes(),"maxRetainedBytes",c.maxRetainedBytes(),"maxDerivedStateBytes",c.maxDerivedStateBytes()));
    }
    private MembershipBootstrapSeed(){throw new AssertionError();}
}
