package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Shared immutable-source transaction for certified CANCEL or matching INTENT.
 * This consumes the receiving slot, never a voting generation or deletion grant.
 * A partial transaction blocks further acquisition; only exact original recovery
 * may finish it. Closing releases leases, but never removes retained evidence. */
final class MembershipLearnerDisposition implements AutoCloseable {
    enum Kind { CANCEL, INTENT, PENDING_INTENT }
    final Kind kind;
    private final String planName,nextName;
    static final String PLAN="cancellation.json",NEXT="cancellation.next.json",SOURCE="source";
    static final int MAXIMUM=64*1024;
    static final int PENDING_MAXIMUM=MAXIMUM+MembershipJoiningIntentMetadata.MAXIMUM;
    static final String PENDING_ACK="joining-ack.gsr";
    static final String PENDING_SOURCE="retained-source.json";
    static final int PENDING_SOURCE_MAXIMUM=32*1024;
    private final int maximum;
    private final MembershipLearnerHead head;
    private final MembershipLearnerStore store;
    private final MembershipLearnerPlan summary;
    private final MembershipBallotAllocator.Cut cut;
    private final Path directory,staging,destination;
    private final byte[] plan;
    private final Map<String,Object> value,binding,stagingBinding;
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private final Map<String,MembershipReceiveFile.Retained> retained=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private Object directoryKey;
    private volatile boolean closed;
    private boolean failed,complete,released;
    private Map<String,Object> terminal;
    private MembershipCapsule verified;
    private MembershipLearnerVoterStage voterStage;
    private MembershipLearnerCheckpointEndpoint checkpointEndpoint;
    private MembershipResources.Lease resumedMetadata;
    private boolean pendingSourceRetained;
    private static String schema(Kind kind){return switch(kind){case CANCEL->"gse-v53-learner-cancellation/1.3";case INTENT->"gse-v53-learner-intent/1.3";case PENDING_INTENT->"gse-v53-learner-pending-intent/1.3";};}
    private static String planName(Kind kind){return switch(kind){case CANCEL->PLAN;case INTENT->"intent.json";case PENDING_INTENT->"pending-intent.json";};}
    private static String nextName(Kind kind){return switch(kind){case CANCEL->NEXT;case INTENT->"intent.next.json";case PENDING_INTENT->"pending-intent.next.json";};}
    private static int maximum(Kind kind){return kind==Kind.PENDING_INTENT?PENDING_MAXIMUM:MAXIMUM;}
    private static MembershipResources.Lease reservePending(MembershipLearnerHead head,Kind kind)throws IOException {
        return kind==Kind.PENDING_INTENT?head.resources().reserve(MembershipResources.Unit.JOURNAL,"learner-pending-intent",2L*PENDING_MAXIMUM+2048+PENDING_SOURCE_MAXIMUM):null;
    }

    static Path directory(MembershipLearnerPlan plan,Kind kind) {
        return plan.request().operationDirectory().resolveSibling(".gse-v53-learner-"+switch(kind){case CANCEL->"cancel";case INTENT->"intent";case PENDING_INTENT->"pending-intent";}+"-"+plan.planDigest());
    }
    static MembershipLearnerStore store(MembershipLearnerHead head)throws IOException {
        return head instanceof MembershipLearnerMaterialization.PreparedGeneration prepared?prepared.store():
                ((MembershipLearnerMaterialization.CurrentHead)head).store();
    }
    static void requireActive(MembershipLearnerHead head)throws IOException {store(head).requireActive();}
    static void requireActive(MembershipLearnerPlan plan) {
        for(var kind:Kind.values())requireAbsent(directory(plan,kind),kind);
    }
    static boolean present(MembershipLearnerPlan plan) {
        return Arrays.stream(Kind.values()).anyMatch(kind->Files.exists(AdmissionPaths.safe(directory(plan,kind)),LinkOption.NOFOLLOW_LINKS));
    }
    static void requireAbsent(Path directory,Kind kind) {
        require(!Files.exists(AdmissionPaths.safe(directory),LinkOption.NOFOLLOW_LINKS),
                kind==Kind.CANCEL?"learner cancellation requires original recovery; preparation stopped":
                kind==Kind.INTENT?"learner INTENT requires original recovery; preparation stopped":
                "learner pending INTENT requires original recovery; preparation stopped");
    }
    private static Map<String,Object> anchor(MembershipCapsule capsule) {
        return Map.of("source",hash(capsule.packet.bytes()),"cut",capsule.context.cut,
                "catalog",capsule.terminal().catalog(),"application",capsule.terminal().application());
    }
    static Map<String,Object> cancellation(MembershipLearnerHead head,MembershipFloor.Copy copy)throws IOException {
        head.check();copy.check();MembershipLearnerProgressAccess.original(copy.capsule.context,head.request(),copy.owner);
        MembershipLearnerSource.successor(head.source(),copy);
        var row=MembershipLearnerProgressAccess.operation(copy.capsule.context,head.request().identity());
        require(row.get("phase").equals("CANCELLED"),"learner requires certified CANCEL, not timeout or nonterminal progress");
        return row;
    }
    private MembershipLearnerDisposition(MembershipLearnerHead head,byte[] plan,MembershipBallotAllocator.Cut cut,Kind kind)throws IOException {
        this.kind=kind;planName=planName(kind);nextName=nextName(kind);maximum=maximum(kind);
        this.head=head;this.store=store(head);summary=store.summary();this.cut=Objects.requireNonNull(cut);this.plan=plan.clone();
        value=object(parse(plan,maximum));require(Arrays.equals(plan,canonical(value,maximum)),"learner cancellation canonical plan");
        var fields=new HashSet<>(Set.of("schema","plan","request","learner","anchor","peer","path","staging","sourceKey","files"));
        if(kind!=Kind.CANCEL)fields.add("receipt");if(kind==Kind.PENDING_INTENT)fields.add("pending");
        require(value.keySet().equals(fields)
                && value.get("schema").equals(schema(kind)) && value.get("plan").equals(summary.planDigest())
                && value.get("request").equals(MembershipLearnerDiscovery.request(head.request().change()))
                && value.get("learner").equals(MembershipBootstrapSeed.identity(head.request().identity()))
                && value.get("anchor").equals(anchor(head.source())),"learner cancellation original prepared owner");
        require(kind==Kind.CANCEL || value.get("receipt").equals(head.receipt().digest()),"learner INTENT original typed receipt");
        require(kind==Kind.PENDING_INTENT?2L*maximum+2048+PENDING_SOURCE_MAXIMUM<=MembershipResources.Unit.JOURNAL.bytes:
                MembershipLearnerSlot.METADATA_MAXIMUM+2L*MAXIMUM<=MembershipResources.Unit.MISC.bytes,"learner cancellation metadata capacity");
        binding=MembershipLearnerAdmissionPlan.binding(object(value.get("path")));
        stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));
        directory=directory(summary,kind);staging=MembershipLearnerAdmissionPlan.path(stagingBinding);destination=directory.resolve(SOURCE);
        require(directory.equals(MembershipLearnerAdmissionPlan.path(binding)),"learner cancellation fixed path");
        head.requireDisjoint(directory,staging);AdmissionPaths.recheck(binding);AdmissionPaths.recheck(stagingBinding);
        var rows=list(value.get("files"));require(!rows.isEmpty() && rows.size()<=32,"learner cancellation inventory capacity");
        String previous=null;long metadataBytes=0;int images=0;
        for(Object item:rows) {
            var row=object(item);String name=(String)row.get("path");
            require(row.keySet().equals(Set.of("path","size","sha256","key")) && name.matches("[a-z0-9-]+\\.(gsr|gscp|image|json)")
                    && (previous==null || previous.compareTo(name)<0),"learner cancellation inventory order/path");previous=name;
            MembershipValidation.digest((String)row.get("sha256"));
            require(row.get("key") instanceof String && !((String)row.get("key")).isBlank() && ((String)row.get("key")).length()<=4096
                    && number(row.get("size"))>0 && number(row.get("size"))<=MembershipGenerationFiles.limit(name),"learner cancellation member capacity");
            if(name.endsWith(".image"))images++;else metadataBytes=Math.addExact(metadataBytes,number(row.get("size")));
        }
        require(metadataBytes<=MembershipResources.Unit.LEARNER.bytes && images<=MembershipResources.Unit.APPLICATION.count,"learner cancellation resource envelope");
    }
    static MembershipLearnerDisposition install(MembershipLearnerHead head,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut,Kind kind)throws IOException {
        require(kind!=Kind.PENDING_INTENT,"pending INTENT requires original progress exchange");
        return install(head,receiver,copy,cut,kind,null);
    }
    static MembershipLearnerDisposition installPending(MembershipLearnerProgress.PendingIntent original,MembershipBallotAllocator.Cut cut)throws IOException {
        var head=original.head();var copy=original.source();var receiver=original.receiver(cut);byte[] metadata=original.metadata();original.check();
        return install(head,receiver,copy,cut,Kind.PENDING_INTENT,metadata);
    }
    private static MembershipLearnerDisposition install(MembershipLearnerHead head,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut,Kind kind,byte[] pending)throws IOException {
        requireActive(head);
        if(kind==Kind.CANCEL)cancellation(head,copy);else if(kind==Kind.INTENT)MembershipLearnerIntent.match(head,copy);
        else {head.check();copy.check();MembershipLearnerSource.successor(head.source(),copy);
            MembershipJoiningIntentMetadata.inspect(head.request(),copy.owner,copy.capsule,head.receipt(),pending);}
        receiver.requireResources(head.resources());
        Path staging=receiver.completeLearnerDirectory(copy);var summary=store(head).summary();Path directory=directory(summary,kind);
        var rows=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(copy.fileNames())) {
            byte[] bytes=copy.fileBytes(name);var identity=inspect(staging.resolve(name),bytes.length,hash(bytes));
            rows.add(Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes),"key",identity.key().toString()));
        }
        var values=new TreeMap<String,Object>(Map.of("schema",schema(kind),"plan",summary.planDigest(),
                "request",MembershipLearnerDiscovery.request(head.request().change()),"learner",MembershipBootstrapSeed.identity(head.request().identity()),
                "anchor",anchor(head.source()),"peer",MembershipBootstrapSeed.identity(copy.owner),"path",AdmissionPaths.binding(directory),
                "staging",AdmissionPaths.binding(staging),"sourceKey",key(staging).toString(),"files",rows));
        if(kind!=Kind.CANCEL)values.put("receipt",head.receipt().digest());
        var journal=reservePending(head,kind);MembershipLearnerDisposition result=null;
        try {
            if(kind==Kind.PENDING_INTENT)values.put("pending",parse(pending,MembershipJoiningIntentMetadata.MAXIMUM));
            byte[] plan=canonical(values,maximum(kind));result=new MembershipLearnerDisposition(head,plan,cut,kind);
            if(journal!=null)result.leases.add(journal);
            AdmissionPaths.absent(directory);result.validate();result.store.attachDisposition(result);
            result.retained.putAll(receiver.detachLearner(copy));
            Files.createDirectory(directory);result.directoryKey=key(directory);AdmissionPaths.forceDirectory(directory.getParent());result.point("LEARNER_CANCEL_DIRECTORY_FORCED");
            result.writePlan();result.finish();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null){result.failed=true;try{result.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}}
            else if(journal!=null)journal.close();throw error;}
    }
    static MembershipLearnerDisposition resume(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut,Kind kind)throws IOException {
        String planName=planName(kind),nextName=nextName(kind);
        for(var other:Kind.values())if(other!=kind)requireAbsent(directory(store(head).summary(),other),other);
        var summary=store(head).summary();Path directory=AdmissionPaths.safe(directory(summary,kind));
        var allowed=new HashSet<>(Set.of(planName,nextName,SOURCE));if(kind==Kind.PENDING_INTENT)allowed.addAll(Set.of(PENDING_ACK,PENDING_SOURCE));
        var names=children(directory,allowed.size());require(allowed.containsAll(names) && (names.contains(planName)||names.contains(nextName)),"learner cancellation original plan missing");
        var journal=reservePending(head,kind);MembershipLearnerDisposition result=null;
        try {
            byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(planName)?planName:nextName),maximum(kind));
            if(names.contains(planName)&&names.contains(nextName))AdmissionPaths.exact(directory.resolve(nextName),bytes);
            result=new MembershipLearnerDisposition(head,bytes,cut,kind);if(journal!=null)result.leases.add(journal);
            result.directoryKey=key(directory);
            for(String name:List.of(planName,nextName))if(names.contains(name))result.remember(name,bytes);
            if(names.contains(PENDING_ACK))result.remember(PENDING_ACK,AdmissionPaths.read(directory.resolve(PENDING_ACK),2048));
            if(names.contains(PENDING_SOURCE))result.remember(PENDING_SOURCE,AdmissionPaths.read(directory.resolve(PENDING_SOURCE),PENDING_SOURCE_MAXIMUM));
            result.reserve();result.validate();result.store.attachDisposition(result);
            if(result.store.recoveringPlacement()) {
                require(kind==Kind.INTENT && names.equals(Set.of(planName,SOURCE)) && result.location().equals(result.destination),
                        "learner placement incomplete original INTENT");
                result.store.placementRecovery().check();result.complete=true;
            }else result.finish();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null){result.failed=true;try{result.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}}
            else if(journal!=null)journal.close();throw error;}
    }
    private void reserve()throws IOException {
        long bytes=0;var resources=head.resources();
        for(Object item:list(value.get("files"))) {
            var row=object(item);String name=(String)row.get("path");
            if(name.endsWith(".image"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"cancel:"+name,number(row.get("size"))));
            else bytes=Math.addExact(bytes,number(row.get("size")));
        }
        resumedMetadata=resources.reserve(MembershipResources.Unit.LEARNER,"learner-cancellation",bytes);leases.add(resumedMetadata);
    }
    private Path location()throws IOException {
        AdmissionPaths.recheck(binding);AdmissionPaths.recheck(stagingBinding);
        boolean a=Files.exists(staging,LinkOption.NOFOLLOW_LINKS),b=Files.exists(destination,LinkOption.NOFOLLOW_LINKS);
        require(a!=b,"learner cancellation missing/duplicate original source");Path location=a?staging:destination;
        require(key(location).toString().equals(value.get("sourceKey")),"learner cancellation source replaced");
        var names=new TreeSet<String>();
        for(Object item:list(value.get("files"))) {
            var row=object(item);String name=(String)row.get("path");names.add(name);
            require(inspect(location.resolve(name),number(row.get("size")),(String)row.get("sha256")).key().toString().equals(row.get("key")),"learner cancellation member replaced");
        }
        require(children(location,32).equals(names),"learner cancellation original inventory changed");return location;
    }
    private void check()throws IOException {
        require(!closed && !failed,"learner cancellation owner closed/failed");head.check();location();
        if(directoryKey!=null) {
            require(directoryKey.equals(key(directory)),"learner cancellation directory replaced");var names=new TreeSet<>(metadata.keySet());
            if(Files.exists(destination,LinkOption.NOFOLLOW_LINKS))names.add(SOURCE);
            require(children(directory,kind==Kind.PENDING_INTENT?5:3).equals(names),"learner cancellation metadata inventory changed");
            for(var row:metadata.entrySet())require(row.getValue().equals(inspect(directory.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"learner cancellation metadata replaced");
        }
    }
    private void validate()throws IOException {
        check();Path source=location();var files=new TreeMap<String,byte[]>();
        for(Object item:list(value.get("files"))) {var row=object(item);files.put((String)row.get("path"),AdmissionPaths.read(source.resolve((String)row.get("path")),Math.toIntExact(number(row.get("size")))));}
        var packet=MembershipSourcePacket.decode(Objects.requireNonNull(files.get("source.gscp")));var images=new TreeMap<String,byte[]>();
        for(String digest:packet.images().keySet())images.put(digest,files.get(digest+".image"));
        var original=head.source();var root=decode(original.packet.objectBytes(original.context.recordRootDigest()),"records","ROOT");
        var token=new Stored(this,files);MembershipCapsule capsule;
        try{capsule=MembershipCapsule.verifyStored(root,packet,images,token);}finally{token.active=false;}
        var peer=MembershipContext.identity(object(value.get("peer")));
        MembershipFloor.Copy.validateMaterialization(decode(files.get("generation.gsr"),"records","GENERATION"),capsule,peer,files);
        MembershipLearnerProgressAccess.original(capsule.context,head.request(),peer);
        MembershipLearnerSource.successor(original,capsule,files.getOrDefault("ancestry.gsr",new byte[0]));
        var row=MembershipLearnerProgressAccess.operation(capsule.context,head.request().identity());
        if(kind==Kind.CANCEL)require(row.get("phase").equals("CANCELLED"),"learner cancellation original terminal proof missing");
        else if(kind==Kind.INTENT)MembershipLearnerIntent.match(head,capsule,peer,files.getOrDefault("ancestry.gsr",new byte[0]));
        else {
            var pending=MembershipJoiningIntentMetadata.inspect(head.request(),peer,capsule,head.receipt(),canonical(value.get("pending"),MembershipJoiningIntentMetadata.MAXIMUM));
            if(metadata.containsKey(PENDING_ACK)) {
                byte[] ack=AdmissionPaths.read(directory.resolve(PENDING_ACK),2048),expected=pendingAcknowledgement(pending).bytes();
                require(ack.length<=expected.length && Arrays.equals(ack,Arrays.copyOf(expected,ack.length)),"joining original acknowledgement prefix changed");
            }
            if(metadata.containsKey(PENDING_SOURCE)) {
                require(metadata.containsKey(planName) && metadata.containsKey(PENDING_ACK) && source.equals(destination),"joining retained source needs complete original end");
                AdmissionPaths.exact(directory.resolve(PENDING_ACK),pendingAcknowledgement(pending).bytes());
                byte[] marker=AdmissionPaths.read(directory.resolve(PENDING_SOURCE),PENDING_SOURCE_MAXIMUM),expected=sourceMarker();
                require(marker.length<=expected.length && Arrays.equals(marker,Arrays.copyOf(expected,marker.length)),"joining retained source original prefix changed");
            }
        }
        terminal=row;verified=capsule;check();
    }
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final MembershipLearnerDisposition owner;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(MembershipLearnerDisposition owner,Map<String,byte[]> files){this.owner=owner;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            require(active,"learner cancellation stored verification expired");owner.check();
            require(Arrays.equals(root.bytes(),owner.head.source().packet.objectBytes(owner.head.source().context.recordRootDigest()))
                    && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner cancellation stored originals");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    private void remember(String name,byte[] bytes)throws IOException {metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));}
    private void point(String event)throws IOException {check();cut.at(kind==Kind.CANCEL?event:event.replace("LEARNER_CANCEL_",kind==Kind.INTENT?"LEARNER_INTENT_":"LEARNER_JOINING_"));check();}
    private void force(Path path)throws IOException {
        check();try(var channel=MembershipFileAccess.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
    }
    private void writePlan()throws IOException {
        check();AdmissionPaths.absent(directory.resolve(nextName));
        try(var channel=MembershipFileAccess.open(directory.resolve(nextName),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(nextName,new byte[0]);point("LEARNER_CANCEL_PLAN_CREATED");int half=plan.length/2;
            AdmissionPaths.write(channel,Arrays.copyOf(plan,half));remember(nextName,Arrays.copyOf(plan,half));point("LEARNER_CANCEL_PLAN_PREFIX_WRITTEN");
            AdmissionPaths.write(channel,Arrays.copyOfRange(plan,half,plan.length));remember(nextName,plan);point("LEARNER_CANCEL_PLAN_WRITTEN");
            channel.force(true);point("LEARNER_CANCEL_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_PLAN_PARENT_FORCED");
        }
    }
    private void finish()throws IOException {
        validate();
        if(!metadata.containsKey(planName)) {
            force(directory.resolve(nextName));AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_RESEAL_FORCED");
            Files.move(directory.resolve(nextName),directory.resolve(planName),StandardCopyOption.ATOMIC_MOVE);metadata.put(planName,metadata.remove(nextName));point("LEARNER_CANCEL_PLAN_RENAMED");
        }
        force(directory.resolve(planName));AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_ACTIVE_PLAN_FORCED");
        if(location().equals(staging)) {
            Files.move(staging,destination,StandardCopyOption.ATOMIC_MOVE);point("LEARNER_CANCEL_SOURCE_MOVED");
        }
        // A complete write observed before death still requires its original
        // force on recovery; revalidate before any such write/rename.
        for(Object item:list(value.get("files"))){force(destination.resolve((String)object(item).get("path")));point("LEARNER_CANCEL_SOURCE_MEMBER_FORCED");}
        AdmissionPaths.forceDirectory(destination);AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(staging.getParent());
        point("LEARNER_CANCEL_SOURCE_PARENTS_FORCED");
        if(metadata.containsKey(nextName)) {
            AdmissionPaths.exact(directory.resolve(nextName),plan);Files.delete(directory.resolve(nextName));metadata.remove(nextName);
            AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_REDUNDANT_PLAN_REMOVED");
        }
        validate();point("LEARNER_CANCEL_BEFORE_RETURN");complete=true;
    }
    Map<String,Object> result()throws IOException {
        check();require(complete,"learner cancellation not forced");return object(parse(canonical(terminal,16384),16384));
    }
    private MembershipJoiningIntentMetadata pendingMetadata()throws IOException {
        require(kind==Kind.PENDING_INTENT && complete,"joining original retention not forced");validate();
        return MembershipJoiningIntentMetadata.inspect(head.request(),MembershipContext.identity(object(value.get("peer"))),verified,head.receipt(),
                canonical(value.get("pending"),MembershipJoiningIntentMetadata.MAXIMUM));
    }
    private Decoded pendingAcknowledgement(MembershipJoiningIntentMetadata pending)throws IOException {
        var statement=pending.record("CHECKPOINT");var identity=head.request().identity();
        return decode(encode("records","CHECKPOINT_ACK",Map.of("root",statement.value().get("root"),"cut",statement.value().get("end"),
                "statement",statement.digest(),"voter",identity.nodeId().value(),"incarnation",identity.storageId().toString())),"records","CHECKPOINT_ACK");
    }
    /** Only the fully forced original pending transaction may endorse its exact
     * new-side end. No selector, election vote or published view is fabricated. */
    synchronized MembershipAppliedEndFiles.Endorsement endorsePending()throws IOException {
        var pending=pendingMetadata();byte[] expected=pendingAcknowledgement(pending).bytes();
        try {
            boolean exists=metadata.containsKey(PENDING_ACK);var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
            if(!exists)options.add(StandardOpenOption.CREATE_NEW);
            try(var channel=MembershipFileAccess.open(directory.resolve(PENDING_ACK),options)) {
                if(!exists){remember(PENDING_ACK,new byte[0]);point("LEARNER_CANCEL_ACK_CREATED");}
                var original=metadata.get(PENDING_ACK);int offset=Math.toIntExact(original.bytes());channel.position(offset);
                int middle=offset+(expected.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));
                remember(PENDING_ACK,Arrays.copyOf(expected,middle));require(original.key().equals(metadata.get(PENDING_ACK).key()),"joining acknowledgement write target changed");
                point("LEARNER_CANCEL_ACK_PREFIX_WRITTEN");AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));
                remember(PENDING_ACK,expected);require(original.key().equals(metadata.get(PENDING_ACK).key()),"joining acknowledgement write target changed");
                point("LEARNER_CANCEL_ACK_WRITTEN");channel.force(true);point("LEARNER_CANCEL_ACK_FORCED");
            }
            AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_ACK_PARENT_FORCED");
            pendingMetadata();var ack=decode(expected,"records","CHECKPOINT_ACK");var identity=head.request().identity();
            var observation=new MembershipContext.Owned(identity.nodeId().value(),identity.storageId(),ack.digest(),
                    MembershipContext.cutDigest(object(ack.value().get("cut"))));
            point("LEARNER_CANCEL_ACK_BEFORE_RETURN");return new MembershipAppliedEndFiles.Endorsement(ack,observation,Optional.empty());
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    synchronized MembershipCapsule pendingSource()throws IOException {pendingMetadata();return verified;}
    synchronized MembershipJoiningIntentMetadata pendingOriginals()throws IOException {return pendingMetadata();}
    private byte[] sourceMarker()throws IOException {
        return canonical(Map.of("schema","gse-v53-joining-retained-source/1.3","plan",hash(plan),
                "planKey",metadata.get(planName).key().toString(),"sourceKey",value.get("sourceKey"),
                "receipt",value.get("receipt"),"ack",hash(AdmissionPaths.read(directory.resolve(PENDING_ACK),2048)),
                "ackKey",metadata.get(PENDING_ACK).key().toString(),"markerKey",metadata.get(PENDING_SOURCE).key().toString()),PENDING_SOURCE_MAXIMUM);
    }
    /** Unforgeable local retention provenance; not a head selector or vote. */
    final class RetainedSource {
        private RetainedSource()throws IOException {check();}
        void check()throws IOException {
            synchronized(MembershipLearnerDisposition.this) {
                require(kind==Kind.PENDING_INTENT && complete && pendingSourceRetained,"joining source not retained");
                MembershipLearnerDisposition.this.check();AdmissionPaths.exact(directory.resolve(PENDING_SOURCE),sourceMarker());
            }
        }
        MembershipCapsule source()throws IOException {check();return verified;}
        MembershipLearnerHead head()throws IOException {check();return head;}
        void requireAcquisition()throws IOException {
            check();requireAbsent(directory(summary,Kind.CANCEL),Kind.CANCEL);requireAbsent(directory(summary,Kind.INTENT),Kind.INTENT);check();
        }
        void requireScratch(Path scratch)throws IOException {
            requireAcquisition();head.requireDisjoint(scratch);AdmissionPaths.disjoint(List.of(directory,staging,scratch));
        }
        void matchPublished(MembershipFloor.Copy copy)throws IOException {
            requireAcquisition();copy.check();MembershipLearnerIntent.match(head,copy);
            MembershipLearnerSource.successor(verified,copy);
            var pending=pendingMetadata();
            // The ACK binds the immutable entry/application/checkpoint, not the
            // ballot of its certificate. A later valid old quorum may certify
            // the same value; the complete source independently verifies it.
            for(String kind:List.of("ENTRY","CHECKPOINT")) {
                var original=pending.record(kind);
                require(Arrays.equals(original.bytes(),copy.capsule.packet.objectBytes(original.digest())),"joining published original "+kind+" changed");
            }
            String entry=pending.record("ENTRY").digest(),statement=pending.record("CHECKPOINT").digest();
            require(list(copy.capsule.packet.capsule().value().get("items")).stream().map(MembershipFormat::object)
                    .anyMatch(item->item.get("kind").equals("MEMBERSHIP") && statement.equals(item.get("statement"))
                            && entry.equals(copy.capsule.context.record((String)item.get("certificate"),"CERTIFICATE").value().get("entry"))),
                    "joining published original INTENT edge missing");
            copy.check();requireAcquisition();
        }
    }
    /** Release the single receiving category only after the same original
     * history is forced as a retained SOURCE. All physical bytes stay charged. */
    synchronized RetainedSource retainPendingSource()throws IOException {
        var pending=pendingMetadata();require(metadata.containsKey(PENDING_ACK),"joining source requires forced ACK");
        AdmissionPaths.exact(directory.resolve(PENDING_ACK),pendingAcknowledgement(pending).bytes());
        if(pendingSourceRetained)return new RetainedSource();
        String name="joining-retained:"+summary.planDigest();
        // Capacity refusal precedes marker creation; a rejected reservation
        // does not damage the live pending owner or its checkpoint listener.
        try(var claim=resumedMetadata==null?retained.get("source.gscp").prepareSource(destination.resolve("source.gscp"),name):resumedMetadata.prepareSource(name)) {
            try {
                boolean exists=metadata.containsKey(PENDING_SOURCE);
                var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
                if(!exists)options.add(StandardOpenOption.CREATE_NEW);
                try(var channel=MembershipFileAccess.open(directory.resolve(PENDING_SOURCE),options)) {
                    if(!exists){remember(PENDING_SOURCE,new byte[0]);point("LEARNER_CANCEL_RETAIN_CREATED");}
                    byte[] expected=sourceMarker();var original=metadata.get(PENDING_SOURCE);int offset=Math.toIntExact(original.bytes());
                    AdmissionPaths.exact(directory.resolve(PENDING_SOURCE),Arrays.copyOf(expected,offset));channel.position(offset);
                    int middle=offset+(expected.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));
                    remember(PENDING_SOURCE,Arrays.copyOf(expected,middle));require(original.key().equals(metadata.get(PENDING_SOURCE).key()),"joining source marker replaced");
                    point("LEARNER_CANCEL_RETAIN_PREFIX_WRITTEN");AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));
                    remember(PENDING_SOURCE,expected);require(original.key().equals(metadata.get(PENDING_SOURCE).key()),"joining source marker replaced");
                    point("LEARNER_CANCEL_RETAIN_WRITTEN");channel.force(true);point("LEARNER_CANCEL_RETAIN_FORCED");
                }
                AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_RETAIN_PARENT_FORCED");
                if(resumedMetadata==null)retained.get("source.gscp").requireSourceClaim(destination.resolve("source.gscp"),claim);else claim.requireSource(resumedMetadata);
                point("LEARNER_CANCEL_RETAIN_BEFORE_TRANSFER");claim.commit();pendingSourceRetained=true;
                point("LEARNER_CANCEL_RETAIN_TRANSFERRED");return new RetainedSource();
            }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
        }
    }
    /** Private live provenance for serving only the actual forced pending ACK.
     * The caller cannot construct this from decoded record/observation values. */
    final class PendingCheckpoint {
        final MembershipCapsule source;
        final MembershipIdentity identity;
        final MembershipResources resources;
        final Decoded acknowledgement;
        private PendingCheckpoint()throws IOException {
            acknowledgement=endorsePending().acknowledgement();pendingMetadata();
            source=verified;identity=head.request().identity();resources=head.resources();
            check();
        }
        void check()throws IOException {
            synchronized(MembershipLearnerDisposition.this) {
                // Construction already validated/forced this immutable plan
                // and complete source. Recheck the actual head, original paths,
                // inodes and every byte digest on reads; unchanged bytes do not
                // require replaying the entire semantic history per wire chunk.
                require(kind==Kind.PENDING_INTENT && complete,"joining checkpoint original retention");
                MembershipLearnerDisposition.this.check();
                require(metadata.containsKey(PENDING_ACK),"joining checkpoint original ACK missing");
                AdmissionPaths.exact(directory.resolve(PENDING_ACK),acknowledgement.bytes());
            }
        }
    }
    synchronized MembershipLearnerCheckpointEndpoint servePending(ReplicationBounds bounds,MembershipTransport.Events events,
            java.util.function.LongSupplier clock,long started,long budget)throws IOException {
        Objects.requireNonNull(bounds);Objects.requireNonNull(events);Objects.requireNonNull(clock);
        long elapsed=clock.getAsLong()-started;
        require(budget>0 && budget<Long.MAX_VALUE/2 && elapsed>=0 && elapsed<budget
                && Math.min(FRAME,bounds.maxFrameBytes())>=4096 && bounds.snapshotChunkBytes()>0,"joining checkpoint original limits");
        pendingMetadata();require(checkpointEndpoint==null || checkpointEndpoint.closed(),"joining checkpoint endpoint already owned");
        checkpointEndpoint=new MembershipLearnerCheckpointEndpoint(new PendingCheckpoint(),bounds,events,clock,started,budget);
        return checkpointEndpoint;
    }
    MembershipCapsule forcedIntent()throws IOException {
        require(kind==Kind.INTENT && complete,"learner INTENT not forced");validate();return verified;
    }
    synchronized void guardIntent()throws IOException {require(kind==Kind.INTENT && complete,"learner INTENT not forced");check();}
    MembershipLearnerHead intentHead()throws IOException {guardIntent();return head;}
    MembershipLearnerPlan intentPlan()throws IOException {guardIntent();return summary;}
    byte[] intentMember(String name)throws IOException {
        guardIntent();var row=list(value.get("files")).stream().map(MembershipFormat::object)
                .filter(v->name.equals(v.get("path"))).findFirst().orElseThrow();
        byte[] bytes=AdmissionPaths.read(destination.resolve(name),Math.toIntExact(number(row.get("size"))));guardIntent();return bytes;
    }
    byte[] intentAncestry()throws IOException {
        guardIntent();return list(value.get("files")).stream().map(MembershipFormat::object).anyMatch(v->v.get("path").equals("ancestry.gsr"))?
                intentMember("ancestry.gsr"):new byte[0];
    }
    synchronized void attachVoterStage(MembershipLearnerVoterStage stage)throws IOException {
        guardIntent();require(voterStage==null || voterStage.closed(),"learner voter stage already owned");voterStage=stage;
    }
    void collectCustody(MembershipLearnerCustody.Collected result)throws IOException {
        guardIntent();result.roots.add(directory);result.leases.addAll(leases);
        for(var value:retained.values())value.collectCustody(result);
        require(voterStage!=null && !voterStage.closed(),"learner custody needs live staged voter");voterStage.collectCustody(result);
    }
    boolean closed(){return closed;}
    @Override public void close()throws IOException {
        MembershipLearnerCheckpointEndpoint endpoint;
        synchronized(this){closed=true;endpoint=checkpointEndpoint;}
        // Readers take the original owner monitor. Revoke first, but never
        // drain transport workers while holding that monitor. Keep reservations
        // for a retry if transport draining itself fails.
        if(endpoint!=null)endpoint.close();
        var children=new ArrayList<AutoCloseable>();
        synchronized(this) {
            if(released)return;released=true;if(voterStage!=null)children.add(voterStage);children.addAll(retained.values());children.addAll(leases);
        }
        MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
