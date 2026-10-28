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
    private MembershipOwnership owner;
    private Object directoryKey,lockKey;
    private boolean closed,failed,complete;
    private MembershipLearnerStore(MembershipLearnerAdmissionFiles operation,MembershipLearnerRetention decision,MembershipBallotAllocator.Cut cut)throws IOException {
        this.operation=operation;this.plan=operation.retained();this.decision=decision;this.cut=cut;path=plan.request.replicaDirectory();
        expected=expected(plan,decision);
    }
    private static Map<String,byte[]> expected(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention decision) {
        return Map.of("root.gsr",plan.root.bytes(),"node.gsr",encode("records","NODE",Map.of("root",plan.request.root().manifestDigest(),
                "identity",MembershipBootstrapSeed.identity(plan.request.identity()))),ADMISSION,decision.bytes());
    }
    /** Validate retained source and any partial local metadata before resealing or
     * removing redundant decision files. Invalid originals remain fully intact. */
    static void preflight(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention decision)throws IOException {
        Path location=decision.locate(),replica=plan.request.replicaDirectory();
        if(location.equals(decision.destination)) {
            if(Files.exists(decision.staging.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.recheck(decision.stagingBinding);
            else AdmissionPaths.exact(replica.resolve(ADMISSION),decision.bytes());
        }
        if(!Files.exists(replica,LinkOption.NOFOLLOW_LINKS))return;
        var allowed=expected(plan,decision);var names=children(replica,5);
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
            var plan=operation.retained();operation.requireFreshRetention();plan.checkOriginal(original);operation.reserveAdmission();
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
    private void reserve(MembershipResources resources)throws IOException {
        operation.checkOwner();decision.locate();long metadata=0;
        for(var row:plan.inventory())if(!((String)row.get("path")).endsWith(".image"))metadata=Math.addExact(metadata,number(row.get("size")));
        leases.add(resources.reserve(MembershipResources.Unit.LEARNER,"learner-store",metadata));
        for(var row:plan.inventory())if(((String)row.get("path")).endsWith(".image"))
            leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-store:"+row.get("path"),number(row.get("size"))));
    }
    private void check()throws IOException {
        require(!closed && !failed,"learner store owner closed or failed");operation.checkOwner();plan.recheckPaths(false);
        Path source=decision.locate();for(var file:received.entrySet())file.getValue().check(source.resolve(file.getKey()));
        if(directoryKey!=null) {
            require(directoryKey.equals(key(path)),"learner replica directory replaced");
            var names=new TreeSet<>(metadata.keySet());if(owner!=null)names.add(LOCK);if(source.equals(decision.destination))names.add("learner");
            require(children(path,5).equals(names),"learner replica inventory changed");
            if(owner!=null){AdmissionPaths.regular(path.resolve(LOCK));require(owner.lock().isValid() && lockKey.equals(key(path.resolve(LOCK))) && Files.size(path.resolve(LOCK))==0,"learner replica lock changed");}
            for(var row:metadata.entrySet())require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"learner replica original member changed");
        }
    }
    private void point(String event)throws IOException {check();cut.at(event);check();}
    private void openReplica()throws IOException {
        operation.checkOwner();decision.locate();
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)) {
            Files.createDirectory(path);directoryKey=key(path);AdmissionPaths.forceDirectory(path.getParent());point("LEARNER_REPLICA_CREATED");
        }else {
            directoryKey=key(path);var names=children(path,5);
            require(Set.of(LOCK,"root.gsr","node.gsr",ADMISSION,"learner").containsAll(names),"learner replica unexpected files");
            for(String name:expected.keySet())if(names.contains(name)) {
                byte[] bytes=AdmissionPaths.read(path.resolve(name),expected.get(name).length);
                require(prefix(bytes,expected.get(name)),"learner replica differs from original plan");remember(name,bytes);
            }
        }
        owner=MembershipOwnership.own(path.resolve(LOCK),!Files.exists(path.resolve(LOCK),LinkOption.NOFOLLOW_LINKS));lockKey=key(path.resolve(LOCK));
        point("LEARNER_REPLICA_LOCKED");
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
        try(var channel=FileChannel.open(file,exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
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
            write(ADMISSION,"LEARNER_ADMISSION");check();complete=true;capsule();point("LEARNER_STORE_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipCapsule capsule()throws IOException {
        check();require(complete,"learner source store incomplete");var files=new TreeMap<String,byte[]>();
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
    MembershipLearnerPlan summary()throws IOException {capsule();return plan.summary();}
    /** Read only an already-retained original image under this exclusive owner.
     * No independent reservation or materialized application is manufactured. */
    byte[] originalImage(String digest,long size)throws IOException {
        var capsule=capsule();require(Objects.equals(capsule.packet.images().get(digest),size),"learner original image binding");
        byte[] bytes=AdmissionPaths.read(decision.destination.resolve(digest+".image"),Math.toIntExact(size));
        require(bytes.length==size && hash(bytes).equals(digest),"learner original image bytes");check();return bytes;
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.addAll(received.values());children.addAll(leases);
        children.add(owner);children.add(operation);MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
