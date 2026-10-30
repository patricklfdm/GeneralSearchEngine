package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exclusive original nonvoting admission. No allocator, local promise, journal,
 * readiness receipt or joint vote is created by this owner. */
final class MembershipLearnerStore implements AutoCloseable {
    static final String LOCK="replica.lock",ADMISSION="learner-admission.gslp";
    private final MembershipLearnerAdmissionFiles operation;
    private final MembershipLearnerAdmissionPlan plan;
    private final MembershipLearnerRetention decision;
    private final MembershipBallotAllocator.Cut cut;
    private final Path path;
    private final Map<String,byte[]> expected;
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private final Map<String,MembershipReceiveFile.Retained> received=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private MembershipLearnerMaterialization<?> typed;
    private MembershipResources.Lease typedImage;
    private MembershipResources.Lease resumedMetadata;
    private boolean preparedGeneration;
    private MembershipLearnerSuccessor successor;
    private MembershipLearnerSlot slot;
    private MembershipLearnerDisposition cancellation,intent,pendingIntent;
    private MembershipLearnerRetirement retirement;
    private boolean predecessorReleased;
    private MembershipLearnerPlacement.Recovery placementRecovery;
    private MembershipOwnership owner;
    private Object directoryKey,lockKey;
    private boolean closed,failed,complete;
    private MembershipLearnerStore(MembershipLearnerAdmissionFiles operation,MembershipLearnerRetention decision,MembershipBallotAllocator.Cut cut)throws IOException {
        this.operation=operation;this.plan=operation.retained();this.decision=decision;this.cut=cut;path=plan.request.replicaDirectory();
        expected=expected(plan,decision);retirement=MembershipLearnerRetirement.load(plan,decision);
    }
    private static Map<String,byte[]> expected(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention decision) {
        return Map.of("root.gsr",plan.root.bytes(),"node.gsr",encode("records","NODE",Map.of("root",plan.request.root().manifestDigest(),
                "identity",MembershipBootstrapSeed.identity(plan.request.identity()))),ADMISSION,decision.bytes());
    }
    /** Validate retained source and any partial local metadata before resealing or
     * removing redundant decision files. Invalid originals remain fully intact. */
    static void preflight(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention decision)throws IOException {
        preflight(plan,decision,null);
    }
    static void preflight(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention decision,MembershipLearnerPlacement.Recovery recovery)throws IOException {
        var retirement=MembershipLearnerRetirement.load(plan,decision);
        Path replica=plan.request.replicaDirectory();
        if(retirement!=null) {
            retirement.check();decision.checkRemaining();var names=recovery==null?children(replica,5):recovery.replicaNames();
            var required=Set.of(LOCK,"root.gsr","node.gsr",ADMISSION);
            require(names.containsAll(required) && Set.of(LOCK,"root.gsr","node.gsr",ADMISSION,"learner").containsAll(names),"learner retirement replica inventory");
            AdmissionPaths.exact(replica.resolve(LOCK),new byte[0]);
            for(var file:expected(plan,decision).entrySet())AdmissionPaths.exact(replica.resolve(file.getKey()),file.getValue());
            return;
        }
        Path location=decision.locate();
        if(location.equals(decision.destination)) {
            if(Files.exists(decision.staging.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.recheck(decision.stagingBinding);
            else AdmissionPaths.exact(replica.resolve(ADMISSION),decision.bytes());
        }
        if(!Files.exists(replica,LinkOption.NOFOLLOW_LINKS))return;
        var allowed=expected(plan,decision);var names=recovery==null?children(replica,5):recovery.replicaNames();
        require(Set.of(LOCK,"root.gsr","node.gsr",ADMISSION,"learner").containsAll(names),"learner replica unexpected files");
        if(names.contains(LOCK)){AdmissionPaths.regular(replica.resolve(LOCK));require(Files.size(replica.resolve(LOCK))==0,"learner replica nonempty lock");}
        for(var file:allowed.entrySet())if(names.contains(file.getKey()))
            require(prefix(AdmissionPaths.read(replica.resolve(file.getKey()),file.getValue().length),file.getValue()),"learner replica differs from original plan");
    }
    /** Takes ownership of operation and the existing receiver leases. After
     * detachment all failures preserve source files for explicit recovery. */
    static MembershipLearnerStore install(MembershipLearnerAdmissionFiles operation,MembershipSourceReceive source,
            MembershipFloor.Copy original,MembershipBallotAllocator.Cut cut)throws IOException {
        MembershipLearnerStore result=null;
        try {
            var plan=operation.retained();operation.requireFreshRetention();source.requireResources(operation.resources());plan.checkOriginal(original);operation.reserveAdmission();
            Path staging=source.completeLearnerDirectory(original);var decision=MembershipLearnerRetention.create(plan,staging);
            result=new MembershipLearnerStore(operation,decision,cut);
            result.received.putAll(source.detachLearner(original));
            operation.retainSource(decision);result.finish();return result;
        }catch(IOException|RuntimeException|Error error){
            try{if(result!=null)result.close();else operation.close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    static MembershipLearnerStore resume(MembershipLearnerPlan summary,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws IOException {
        var operation=MembershipLearnerAdmissionFiles.openAdmission(summary,resources,cut);MembershipLearnerStore result=null;
        try {
            result=new MembershipLearnerStore(operation,operation.retention(),cut);result.reserve(resources);result.finish();return result;
        }catch(IOException|RuntimeException|Error error){
            try{if(result!=null)result.close();else operation.close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    static MembershipLearnerStore reopenPlacement(MembershipLearnerPlan summary,MembershipResources resources,
            MembershipLearnerPlacement.Recovery recovery)throws IOException {
        var operation=MembershipLearnerAdmissionFiles.openPlacement(summary,resources,recovery);MembershipLearnerStore result=null;
        try {
            result=new MembershipLearnerStore(operation,operation.retention(),e->{});result.placementRecovery=recovery;
            result.reserve(resources);result.openReplica();result.complete=true;
            if(result.retirement==null) {
                result.capsule();result.successor=MembershipLearnerSuccessor.restore(result,e->{});
            }else if(MembershipLearnerSlot.hasCommittedHead(summary)) {
                result.slot=MembershipLearnerSlot.restore(result,e->{});result.slot.restorePlacementHead();
                result.requireOriginalRetiredFilesAbsent();result.releaseOriginalLeases();result.slot.reserve();
            }else {
                result.successor=MembershipLearnerSuccessor.restore(result,e->{});
                require(result.successor!=null,"learner placement original successor missing");
                result.successor.restorePlacementHead();result.requireOriginalRetiredFilesAbsent();result.releaseOriginalLeases();
                result.slot=MembershipLearnerSlot.restore(result,e->{});if(result.slot!=null)result.slot.reserve();
            }
            result.check();return result;
        }catch(IOException|RuntimeException|Error error) {
            try{if(result!=null)result.close();else operation.close();}catch(Exception close){error.addSuppressed(close);}throw error;
        }
    }
    boolean recoveringPlacement()throws IOException {check();return placementRecovery!=null;}
    MembershipLearnerPlacement.Recovery placementRecovery()throws IOException {
        check();require(placementRecovery!=null,"learner requires original placement recovery");return placementRecovery;
    }
    private Set<String> replicaNames()throws IOException {return placementRecovery==null?children(path,5):placementRecovery.replicaNames();}
    private void reserve(MembershipResources resources)throws IOException {
        operation.checkOwner();checkSource();long metadata=0;
        for(var row:plan.inventory())if(!((String)row.get("path")).endsWith(".image"))metadata=Math.addExact(metadata,number(row.get("size")));
        resumedMetadata=resources.reserve(MembershipResources.Unit.LEARNER,"learner-store",metadata);leases.add(resumedMetadata);
        for(var row:plan.inventory())if(((String)row.get("path")).endsWith(".image"))
            leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-store:"+row.get("path"),number(row.get("size"))));
    }
    private void check()throws IOException {
        require(!closed && !failed,"learner store owner closed or failed");operation.checkOwner();plan.recheckPaths(false);
        checkSource();Path source=retirement==null?decision.locate():decision.destination;
        for(var file:received.entrySet())if(retirement==null || Files.exists(source.resolve(file.getKey()),LinkOption.NOFOLLOW_LINKS))file.getValue().check(source.resolve(file.getKey()));
        if(directoryKey!=null) {
            require(directoryKey.equals(key(path)),"learner replica directory replaced");
            var names=new TreeSet<>(metadata.keySet());if(owner!=null)names.add(LOCK);if(source.equals(decision.destination) && Files.exists(source,LinkOption.NOFOLLOW_LINKS))names.add("learner");
            require(replicaNames().equals(names),"learner replica inventory changed");
            if(owner!=null){AdmissionPaths.regular(path.resolve(LOCK));require(owner.lock().isValid() && lockKey.equals(key(path.resolve(LOCK))) && Files.size(path.resolve(LOCK))==0,"learner replica lock changed");}
            for(var row:metadata.entrySet())require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"learner replica original member changed");
        }
    }
    private void checkSource()throws IOException {
        if(retirement==null)decision.locate();else {retirement.check();decision.checkRemaining();}
    }
    private void point(String event)throws IOException {check();cut.at(event);check();}
    private void openReplica()throws IOException {
        operation.checkOwner();checkSource();
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)) {
            require(placementRecovery==null,"learner placement original replica missing");
            Files.createDirectory(path);directoryKey=key(path);AdmissionPaths.forceDirectory(path.getParent());point("LEARNER_REPLICA_CREATED");
        }else {
            directoryKey=key(path);var names=replicaNames();
            require(Set.of(LOCK,"root.gsr","node.gsr",ADMISSION,"learner").containsAll(names),"learner replica unexpected files");
            for(String name:expected.keySet())if(names.contains(name)) {
                byte[] bytes=AdmissionPaths.read(path.resolve(name),expected.get(name).length);
                require(prefix(bytes,expected.get(name)),"learner replica differs from original plan");remember(name,bytes);
            }
        }
        owner=MembershipOwnership.own(path.resolve(LOCK),placementRecovery==null && !Files.exists(path.resolve(LOCK),LinkOption.NOFOLLOW_LINKS));lockKey=key(path.resolve(LOCK));
        if(placementRecovery!=null)check();else point("LEARNER_REPLICA_LOCKED");
    }
    private void remember(String name,byte[] bytes)throws IOException {
        var next=inspect(path.resolve(name),bytes.length,hash(bytes));var previous=metadata.get(name);
        require(previous==null || previous.key().equals(next.key()),"learner replica written inode changed");metadata.put(name,next);
    }
    private static boolean prefix(byte[] actual,byte[] expected) {
        return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));
    }
    private void write(String name,String label)throws IOException {
        check();byte[] bytes=expected.get(name);Path file=path.resolve(name);
        boolean exists=metadata.containsKey(name);
        try(var channel=MembershipFileAccess.open(file,exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            if(!exists){remember(name,new byte[0]);point(label+"_CREATED");}
            int offset=Math.toIntExact(metadata.get(name).bytes());channel.position(offset);
            if(offset<bytes.length) {
                int middle=offset+(bytes.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));
                remember(name,Arrays.copyOf(bytes,middle));point(label+"_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,middle,bytes.length));remember(name,bytes);point(label+"_WRITTEN");
            }
            channel.force(true);point(label+"_FORCED");AdmissionPaths.forceDirectory(path);point(label+"_PARENT_FORCED");
        }
    }
    private void finish()throws IOException {
        try {
            require(Arrays.equals(operation.retention().bytes(),decision.bytes()),"learner admission decision changed");
            // A retained typed sidecar is a real extra backup even before its
            // codec is reopened. Reserve its worst-case image before any writes.
            if(Files.exists(AdmissionPaths.safe(MembershipLearnerMaterialization.directory(plan.summary())),LinkOption.NOFOLLOW_LINKS))
                reserveTypedImage(MembershipApplicationImage.MAXIMUM);
            if(retirement!=null) {
                // No old-source move or metadata repair is legal in this state.
                // Authenticate the independent current source before resuming removal.
                preflight(plan,decision);openReplica();complete=true;
                if(MembershipLearnerSlot.hasCommittedHead(plan.summary())) {
                    slot=MembershipLearnerSlot.restore(this,cut);slot.resealHead();
                    finishOriginalForSlot();slot.reserve();slot.retireSeed();
                    point("LEARNER_STORE_BEFORE_RETURN");return;
                }
                successor=MembershipLearnerSuccessor.restore(this,cut);
                require(successor!=null,"learner retirement current source missing");
                // Validate a retained inactive source before any reseal/deletion.
                // A slot can exist only after original retirement was complete.
                slot=MembershipLearnerSlot.restore(this,cut);successor.finishRetirement();
                if(slot!=null)slot.reserve();
                point("LEARNER_STORE_BEFORE_RETURN");return;
            }
            openReplica();write("root.gsr","LEARNER_ROOT");write("node.gsr","LEARNER_NODE");
            if(decision.locate().equals(decision.staging)) {
                check();AdmissionPaths.absent(decision.destination);Files.move(decision.staging,decision.destination,StandardCopyOption.ATOMIC_MOVE);
                point("LEARNER_SOURCE_MOVED");
            }
            AdmissionPaths.forceDirectory(decision.destination);point("LEARNER_SOURCE_RETAINED_DIRECTORY_FORCED");
            // The original staging parent is required until its removal is forced.
            if(Files.exists(decision.staging.getParent(),LinkOption.NOFOLLOW_LINKS)) {
                AdmissionPaths.recheck(decision.stagingBinding);AdmissionPaths.forceDirectory(decision.staging.getParent());
            }else require(metadata.containsKey(ADMISSION) && metadata.get(ADMISSION).digest().equals(hash(expected.get(ADMISSION))),
                    "incomplete learner source move lost original staging parent");
            AdmissionPaths.forceDirectory(path);point("LEARNER_SOURCE_MOVE_PARENTS_FORCED");
            write(ADMISSION,"LEARNER_ADMISSION");check();complete=true;capsule();
            successor=MembershipLearnerSuccessor.restore(this,cut);point("LEARNER_STORE_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipCapsule capsule()throws IOException {
        check();require(complete && retirement==null,"learner source store incomplete or retired");var files=new TreeMap<String,byte[]>();
        for(var row:plan.inventory())files.put((String)row.get("path"),AdmissionPaths.read(decision.destination.resolve((String)row.get("path")),Math.toIntExact(number(row.get("size")))));
        var packet=MembershipSourcePacket.decode(files.get("source.gscp"));var images=new TreeMap<String,byte[]>();
        for(String digest:packet.images().keySet())images.put(digest,files.get(digest+".image"));
        var token=new RetainedCopy(this,files);MembershipCapsule capsule;
        try{capsule=MembershipCapsule.verifyStored(plan.root,packet,images,token);}finally{token.active=false;}
        MembershipFloor.Copy.validateMaterialization(plan.generation,capsule,plan.source,files);
        MembershipLearnerPrefixExport.originalReservation(capsule.context,plan.request,plan.source);check();return capsule;
    }
    static final class RetainedCopy implements MembershipCapsule.StoredCopy {
        private final MembershipLearnerStore owner;private final Map<String,byte[]> files;private boolean active=true;
        private RetainedCopy(MembershipLearnerStore owner,Map<String,byte[]> files){this.owner=owner;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            owner.check();require(active && owner.complete && Arrays.equals(root.bytes(),owner.plan.root.bytes())
                    && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner stored copy lifetime/original");
            for(var row:owner.plan.inventory())require(files.get(row.get("path")).length==number(row.get("size"))
                    && hash(files.get(row.get("path"))).equals(row.get("sha256")),"learner stored copy original inventory");
            for(var name:owner.expected.keySet())AdmissionPaths.exact(owner.path.resolve(name),owner.expected.get(name));
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    MembershipLearnerPlan summary()throws IOException {check();require(complete,"learner source store incomplete");return plan.summary();}
    /** Immutable original terminal, never a replacement source capability. */
    Map<String,Object> originalAnchor()throws IOException {
        check();var value=plan.generation.value();String source=(String)plan.inventory().stream().filter(f->f.get("path").equals("source.gscp")).findFirst().orElseThrow().get("sha256");
        return Map.of("source",source,"cut",value.get("cut"),"catalog",value.get("catalog"),"application",value.get("application"));
    }
    boolean retiring()throws IOException {check();return retirement!=null;}
    void requireRetiredPredecessor()throws IOException {
        check();require(retirement!=null && predecessorReleased,"learner refresh requires forced predecessor retirement");
        AdmissionPaths.absent(decision.destination);AdmissionPaths.absent(MembershipLearnerMaterialization.directory(plan.summary()));
    }
    byte[] retirementBytes()throws IOException {check();return MembershipLearnerRetirement.bytes(plan,decision);}
    void requirePredecessorClosed()throws IOException {check();require(typed==null || typed.closed(),"learner predecessor typed owner still live");}
    void beginRetirement()throws IOException {
        requirePredecessorClosed();
        retirement=MembershipLearnerRetirement.load(plan,decision);require(retirement!=null,"learner retirement decision missing");check();
    }
    List<Path> predecessorRemovalOrder()throws IOException {
        check();require(retirement!=null,"learner retirement decision missing");return decision.remainingRemovalOrder();
    }
    void releasePredecessor(MembershipLearnerSuccessor child)throws IOException {
        check();require(retirement!=null && successor==child,"learner retirement foreign owner");
        AdmissionPaths.absent(decision.destination);AdmissionPaths.absent(MembershipLearnerMaterialization.directory(plan.summary()));
        // The caller has already forced every removal and both surviving parents.
        releaseOriginalLeases();
    }
    private void releaseOriginalLeases()throws IOException {
        var originals=new ArrayList<AutoCloseable>();originals.addAll(received.values());originals.addAll(leases);
        MembershipLearnerSource.closeChildren(originals.toArray(AutoCloseable[]::new));
        received.clear();leases.clear();typedImage=null;resumedMetadata=null;preparedGeneration=false;
        predecessorReleased=true;
    }
    /** Read only an already-retained original image under this exclusive owner.
     * No independent reservation or materialized application is manufactured. */
    byte[] originalImage(String digest,long size)throws IOException {
        var capsule=capsule();require(Objects.equals(capsule.packet.images().get(digest),size),"learner original image binding");
        byte[] bytes=AdmissionPaths.read(decision.destination.resolve(digest+".image"),Math.toIntExact(size));
        require(bytes.length==size && hash(bytes).equals(digest),"learner original image bytes");check();return bytes;
    }
    void reserveTypedImage(long bytes)throws IOException {
        check();require(bytes>0 && bytes<=MembershipApplicationImage.MAXIMUM,"learner typed image capacity");
        if(typedImage==null){typedImage=operation.reserveTypedImage(MembershipApplicationImage.MAXIMUM);leases.add(typedImage);}
    }
    void attachTyped(MembershipLearnerMaterialization<?> next)throws IOException {
        check();require(typed==null || typed.closed(),"learner typed preparation already owned");typed=Objects.requireNonNull(next);
    }
    MembershipResources.GenerationClaim prepareGeneration()throws IOException {
        check();require(complete && !preparedGeneration,"learner generation already selected/incomplete");
        String name="learner-prepared:"+plan.summary().planDigest();
        return resumedMetadata==null?received.get("source.gscp").prepareGeneration(decision.destination.resolve("source.gscp"),name):
                resumedMetadata.prepareGeneration(name);
    }
    void selectedGeneration(MembershipLearnerMaterialization<?> selected,MembershipResources.GenerationClaim claim)throws IOException {
        check();require(typed==selected,"learner generation foreign typed owner");selected.checkPreparedSelection();
        if(resumedMetadata!=null)claim.requireSource(resumedMetadata);
        else received.get("source.gscp").requireGenerationClaim(decision.destination.resolve("source.gscp"),claim);
        claim.commit();preparedGeneration=true;
    }
    boolean preparedGeneration()throws IOException{check();return preparedGeneration;}
    MembershipResources resources()throws IOException{check();return operation.resources();}
    Decoded root()throws IOException{check();return plan.root;}
    void requireNewSuccessor()throws IOException {requireActive();require(successor==null,"learner successor requires original resume or retirement");}
    void attachSuccessor(MembershipLearnerSuccessor child)throws IOException{requireNewSuccessor();successor=Objects.requireNonNull(child);}
    boolean ownsSuccessor(MembershipLearnerSuccessor child){return successor==child;}
    MembershipLearnerSuccessor.View successor(MembershipLearnerMaterialization.PreparedGeneration prepared)throws IOException {
        check();require(successor!=null,"learner successor missing");return successor.open(prepared);
    }
    MembershipLearnerSuccessor.View promotedSuccessor()throws IOException {
        check();require(slot==null || !slot.committed(),"learner seed superseded by selected slot");
        require(successor!=null,"learner successor missing");return successor.promoted();
    }
    MembershipLearnerImageSource currentSource()throws IOException {
        check();return slot!=null && slot.committed()?slot.promoted():promotedSuccessor();
    }
    MembershipLearnerSuccessor seedOwner()throws IOException {
        requireOriginalRetiredFilesAbsent();require(successor!=null,"learner original seed owner missing");successor.slotAnchor();return successor;
    }
    void requireOriginalRetiredFilesAbsent()throws IOException {
        check();require(retirement!=null,"learner original retirement missing");
        AdmissionPaths.absent(decision.destination);AdmissionPaths.absent(MembershipLearnerMaterialization.directory(plan.summary()));
    }
    private void finishOriginalForSlot()throws IOException {
        requireOriginalRetiredFilesAbsent();require(slot!=null && slot.committed(),"learner original retirement requires selected slot");
        Path seed=MembershipLearnerSuccessor.directory(plan.summary());
        for(String name:List.of(MembershipLearnerSuccessor.HEAD,MembershipLearnerRetirement.FILE)) {
            try(var file=MembershipFileAccess.open(seed.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){file.force(true);}
        }
        AdmissionPaths.forceDirectory(seed);AdmissionPaths.forceDirectory(path);
        AdmissionPaths.forceDirectory(MembershipLearnerMaterialization.directory(plan.summary()).getParent());
        point("LEARNER_SLOT_INITIAL_RETIREMENT_FORCED");releaseOriginalLeases();
    }
    void requireNewSlot()throws IOException {
        requireActive();requireRetiredPredecessor();if(slot!=null){slot.requireReusable();return;}
        AdmissionPaths.absent(MembershipLearnerSlot.directory(summary()));
        AdmissionPaths.absent(MembershipLearnerSlot.typedDirectory(summary()));
    }
    Map<String,Object> slotAnchor()throws IOException {
        check();require(retirement!=null && successor!=null,"learner slot requires original retirement");
        AdmissionPaths.absent(decision.destination);AdmissionPaths.absent(MembershipLearnerMaterialization.directory(plan.summary()));
        return successor.slotAnchor();
    }
    void attachSlot(MembershipLearnerSlot value)throws IOException {check();require(slot==null,"learner inactive slot already owned");slot=Objects.requireNonNull(value);}
    MembershipLearnerSlot slotOwner()throws IOException {check();return slot;}
    boolean ownsSlot(MembershipLearnerSlot value){return slot==value;}
    MembershipLearnerSlot.View resumeSlot(MembershipLearnerMaterialization.CurrentHead current)throws IOException {
        check();require(slot!=null,"learner inactive slot missing");return slot.open(current);
    }
    void requireActive()throws IOException {check();MembershipLearnerCancellation.requireActive(plan.summary());}
    void attachDisposition(MembershipLearnerDisposition value)throws IOException {
        check();Objects.requireNonNull(value);
        for(var kind:MembershipLearnerDisposition.Kind.values())if(kind!=value.kind)
            MembershipLearnerDisposition.requireAbsent(MembershipLearnerDisposition.directory(plan.summary(),kind),kind);
        if(value.kind==MembershipLearnerDisposition.Kind.CANCEL) {
            require(cancellation==null || cancellation.closed(),"learner cancellation already owned");
            MembershipLearnerDisposition.requireAbsent(MembershipLearnerIntent.directory(plan.summary()),MembershipLearnerDisposition.Kind.INTENT);cancellation=value;
        }else if(value.kind==MembershipLearnerDisposition.Kind.INTENT) {
            require(intent==null || intent.closed(),"learner INTENT already owned");
            MembershipLearnerDisposition.requireAbsent(MembershipLearnerCancellation.directory(plan.summary()),MembershipLearnerDisposition.Kind.CANCEL);intent=value;
        }else {
            require(pendingIntent==null || pendingIntent.closed(),"learner pending INTENT already owned");pendingIntent=value;
        }
    }
    void collectCustody(MembershipLearnerCustody.Collected result)throws IOException {
        check();require(complete && intent!=null && !intent.closed(),"learner custody needs matching INTENT");
        result.roots.add(path);owner.collectCustody(result);operation.collectCustody(result);
        result.leases.addAll(leases);for(var value:received.values())value.collectCustody(result);
        if(typed!=null)typed.collectCustody(result);
        if(successor!=null)successor.collectCustody(result);
        if(slot!=null)slot.collectCustody(result);
        intent.collectCustody(result);
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.add(pendingIntent);children.add(intent);children.add(cancellation);children.add(slot);children.add(successor);children.add(typed);children.addAll(received.values());children.addAll(leases);
        children.add(owner);children.add(operation);MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
