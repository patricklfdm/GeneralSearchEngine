package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableApplicationState;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A real typed decode followed by an exact forced LEARNER receipt. This owns
 * only a bounded nonvoting preparation sidecar, never a live engine or journal.
 * Reopen repeats semantic validation before exposing any original receipt. */
final class MembershipLearnerMaterialization<T> implements AutoCloseable {
    static final String LOCK="preparation.lock",PLAN="preparation.json",NEXT="preparation.next.json",BACKUP="backup",RECEIPT="learner.gsr",PREPARED="prepared.json";
    static final int MAXIMUM_PLAN=256*1024;
    static final int SUCCESSOR_PLAN=16*1024;
    private record Member(Object key,long bytes,String digest,boolean directory) {}
    private final MembershipLearnerPreparation input;
    private final MembershipBallotAllocator.Cut cut;
    private final Path directory;
    private final Map<String,Object> binding,materialization;
    private final Object directoryKey;
    private final byte[] plan;
    private final byte[] prepared;
    private final Decoded receipt;
    private final Map<String,byte[]> payloads;
    private final MembershipGenerationFiles.Guard configuration;
    private MembershipOwnership lock;
    private Map<String,Member> members;
    private DurableApplicationState<T> state;
    private boolean closed,failed,complete;
    private boolean selectionForced;

    static Path directory(MembershipLearnerPlan plan) {
        return plan.request().operationDirectory().resolveSibling(".gse-v53-learner-"+plan.planDigest());
    }
    static <K,T> MembershipLearnerMaterialization<T> prepare(MembershipLearnerPreparation input,
            SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerMaterialization<>(input,captured,config,cut);
    }
    private <K> MembershipLearnerMaterialization(MembershipLearnerPreparation input,
            SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        this.input=Objects.requireNonNull(input);this.cut=Objects.requireNonNull(cut);input.configuration(captured,config);
        var summary=input.summary();directory=input.directory();
        AdmissionPaths.disjoint(List.of(directory,summary.request().operationDirectory(),summary.request().replicaDirectory(),config.materialization().directory()));
        binding=AdmissionPaths.binding(directory);materialization=AdmissionPaths.binding(config.materialization().directory());
        var descriptor=Map.of("application",AdmissionConfiguration.application(captured),"core",MembershipBootstrapSeed.core(config.materialization()));
        configuration=()->{input.configuration(captured,config);require(descriptor.equals(Map.of("application",AdmissionConfiguration.application(captured),
                "core",MembershipBootstrapSeed.core(config.materialization()))),"learner typed configuration changed");};
        byte[] original=input.image();receipt=input.receiptBytes();var parts=MembershipApplicationImage.unpack(original);var values=new TreeMap<String,byte[]>();
        for(int i=0;i<parts.size();i++)values.put(BACKUP+"/"+MembershipApplicationImage.MEMBERS.get(i),parts.get(i));payloads=Map.copyOf(values);
        boolean exists=Files.exists(directory,LinkOption.NOFOLLOW_LINKS);
        // A terminal learner may reopen its exact historical typed owner for
        // proof recovery, but cannot create a new preparation sidecar.
        if(!exists)input.store().requireActive();
        // The second typed sidecar fits the remaining original MISC budget by
        // retaining descriptor/receipt digests, not duplicate large descriptors.
        // Check its worst-case directory identity before reserving or writing.
        if(input.successor()) {
            require(receipt.size()<=16384,"learner successor receipt capacity");
            successorPlan(input,summary,receipt,descriptor,binding,materialization,"x".repeat(4096));
        }
        // Reserve from the admission owner's original budget, never a caller's
        // separate resource pool. Even a complete existing backup consumes space.
        try {
            input.reserveTypedImage();
            if(!exists){AdmissionPaths.absent(directory);Files.createDirectory(directory);}
            directoryKey=key(directory);
            plan=input.successor()?successorPlan(input,summary,receipt,descriptor,binding,materialization,directoryKey.toString()):
                    canonical(Map.of("schema","gse-v53-learner-typed/1.3","plan",summary.planDigest(),"source",input.packet(),
                    "receipt",MembershipBootstrapPlanData.base(receipt.bytes()),"configuration",descriptor,
                    "path",binding,"materialization",materialization,"directoryKey",directoryKey.toString()),MAXIMUM_PLAN);
            prepared=input.successor()?null:canonical(Map.of("schema","gse-v53-learner-prepared/1.3","root",summary.request().root().manifestDigest(),
                    "identity",MembershipBootstrapSeed.identity(summary.request().identity()),"plan",summary.planDigest(),
                    "typedPlan",hash(plan),"source",input.packet(),"receipt",receipt.digest(),
                    "location",summary.request().replicaDirectory().resolve("learner").toString()),16384);
            var names=children(directory,6);
            if(exists)require(names.contains(LOCK) && (names.contains(PLAN)||names.contains(NEXT)),"learner typed original plan missing");
            else require(names.isEmpty(),"learner typed new directory changed");
            lock=MembershipOwnership.own(directory.resolve(LOCK),!exists);
            members=scan();
            if(MembershipLearnerDisposition.present(summary)) {
                // CANCEL/INTENT was admitted only after this exact prepared
                // owner was forced. Missing/torn historical preparation cannot
                // be reconstructed merely to reopen the retained proof.
                require(names.equals(input.successor()?Set.of(LOCK,PLAN,BACKUP,RECEIPT):Set.of(LOCK,PLAN,BACKUP,RECEIPT,PREPARED)),
                        "cancelled learner missing original typed inventory");
                AdmissionPaths.exact(directory.resolve(PLAN),plan);AdmissionPaths.exact(directory.resolve(RECEIPT),receipt.bytes());
                if(prepared!=null)AdmissionPaths.exact(directory.resolve(PREPARED),prepared);
                require(children(directory.resolve(BACKUP),MembershipApplicationImage.MEMBERS.size()).equals(new TreeSet<>(MembershipApplicationImage.MEMBERS)),
                        "cancelled learner missing original backup");
                for(var member:payloads.entrySet())AdmissionPaths.exact(directory.resolve(member.getKey()),member.getValue());
            }
            input.attach(this);check();
            if(!exists){AdmissionPaths.forceDirectory(directory.getParent());point("LEARNER_TYPED_DIRECTORY_FORCED");write(NEXT,plan,"LEARNER_TYPED_PLAN");}
            seal();
            if(!members.containsKey(BACKUP)){check();Files.createDirectory(directory.resolve(BACKUP));update(BACKUP);point("LEARNER_TYPED_BACKUP_CREATED");}
            for(String name:new TreeSet<>(payloads.keySet()))write(name,payloads.get(name),"LEARNER_TYPED_MEMBER");
            AdmissionPaths.forceDirectory(directory.resolve(BACKUP));AdmissionPaths.forceDirectory(directory);point("LEARNER_TYPED_BACKUP_FORCED");
            state=MembershipApplicationImage.readExisting(captured,config.materialization(),original,directory.resolve(BACKUP));
            require(state.history().equals(summary.request().root().historyId()),"learner typed application history");
            point("LEARNER_TYPED_SEMANTICS_VERIFIED");
            write(RECEIPT,receipt.bytes(),"LEARNER_TYPED_RECEIPT");complete=true;point("LEARNER_TYPED_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;try{close();}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private static byte[] successorPlan(MembershipLearnerPreparation input,MembershipLearnerPlan summary,Decoded receipt,
            Map<String,?> descriptor,Map<String,Object> binding,Map<String,Object> materialization,String key)throws IOException {
        return canonical(Map.of("schema","gse-v53-successor-typed/1.3","plan",summary.planDigest(),"source",input.packet(),
                "receipt",receipt.digest(),"configuration",hash(canonical(descriptor,MAXIMUM_PLAN)),"path",binding,
                "materialization",materialization,"directoryKey",key),SUCCESSOR_PLAN);
    }
    private Map<String,Member> scan()throws IOException {
        AdmissionPaths.recheck(binding);AdmissionPaths.recheck(materialization);
        require(directoryKey.equals(key(directory)),"learner typed directory replaced");
        var names=children(directory,6);require(Set.of(LOCK,PLAN,NEXT,BACKUP,RECEIPT,PREPARED).containsAll(names) && names.contains(LOCK)
                && (prepared!=null || !names.contains(PREPARED)),"learner typed inventory");
        var result=new TreeMap<String,Member>();file(result,LOCK,new byte[0],false);
        boolean active=names.contains(PLAN),candidate=names.contains(NEXT);
        if(active)file(result,PLAN,plan,false);
        if(candidate)file(result,NEXT,plan,!active);
        require(!(names.contains(BACKUP)||names.contains(RECEIPT)) || active,"learner typed data without active plan");
        if(names.contains(BACKUP)) {
            Path backup=directory.resolve(BACKUP);require(Files.isDirectory(AdmissionPaths.safe(backup),LinkOption.NOFOLLOW_LINKS),"learner typed backup directory");
            result.put(BACKUP,new Member(key(backup),0,"",true));var files=children(backup,3);
            require(new HashSet<>(MembershipApplicationImage.MEMBERS).containsAll(files),"learner typed backup inventory");
            for(String name:files)file(result,BACKUP+"/"+name,payloads.get(BACKUP+"/"+name),true);
        }
        if(names.contains(RECEIPT)) {
            for(var row:payloads.entrySet())require(result.containsKey(row.getKey()) && result.get(row.getKey()).bytes()==row.getValue().length,
                    "learner typed receipt without complete image");
            file(result,RECEIPT,receipt.bytes(),true);
        }
        if(names.contains(PREPARED)) {
            require(result.containsKey(RECEIPT) && result.get(RECEIPT).bytes()==receipt.size(),"learner prepared without complete receipt");
            file(result,PREPARED,prepared,true);
        }
        return result;
    }
    private void file(Map<String,Member> result,String name,byte[] expected,boolean partial)throws IOException {
        Path path=directory.resolve(name);byte[] actual=AdmissionPaths.read(path,expected.length);
        require(actual.length==expected.length || partial,"learner typed incomplete original metadata");
        require(Arrays.equals(actual,Arrays.copyOf(expected,actual.length)),"learner typed original bytes changed");
        var value=inspect(path,actual.length,hash(actual));result.put(name,new Member(value.key(),value.bytes(),value.digest(),false));
    }
    private void check()throws IOException {
        require(!closed && !failed && lock!=null && lock.lock().isValid(),"learner typed owner closed or failed");
        configuration.check();require(members.equals(scan()),"learner typed original inventory changed");
    }
    private void point(String event)throws IOException {check();cut.at(event);check();}
    private void update(String name)throws IOException {
        var after=scan();for(var row:members.entrySet())if(!row.getKey().equals(name))require(row.getValue().equals(after.get(row.getKey())),"learner typed prior member changed");
        var names=new TreeSet<>(members.keySet());names.add(name);require(after.keySet().equals(names),"learner typed unexpected writer member");
        if(members.containsKey(name))require(members.get(name).key().equals(after.get(name).key()),"learner typed written inode changed");members=after;
    }
    private void write(String name,byte[] bytes,String prefix)throws IOException {
        check();boolean exists=members.containsKey(name);
        try(var channel=MembershipFileAccess.open(directory.resolve(name),exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            if(!exists){update(name);point(prefix+"_CREATED");}
            int offset=Math.toIntExact(members.get(name).bytes());channel.position(offset);
            if(offset<bytes.length) {
                int middle=offset+(bytes.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));update(name);point(prefix+"_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,middle,bytes.length));update(name);point(prefix+"_WRITTEN");
            }
            channel.force(true);point(prefix+"_FORCED");AdmissionPaths.forceDirectory(directory.resolve(name).getParent());point(prefix+"_PARENT_FORCED");
        }
    }
    private void force(String name,String event)throws IOException {
        check();try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
        point(event);AdmissionPaths.forceDirectory(directory);point(event+"_PARENT");
    }
    private void seal()throws IOException {
        if(!members.containsKey(PLAN)) {
            require(members.containsKey(NEXT) && members.get(NEXT).bytes()==plan.length,"learner typed incomplete candidate plan");
            force(NEXT,"LEARNER_TYPED_CANDIDATE_FORCED");check();Files.move(directory.resolve(NEXT),directory.resolve(PLAN),StandardCopyOption.ATOMIC_MOVE);
            var expected=new TreeMap<>(members);expected.put(PLAN,expected.remove(NEXT));require(expected.equals(scan()),"learner typed plan rename changed originals");members=expected;
            point("LEARNER_TYPED_PLAN_RENAMED");
        }
        force(PLAN,"LEARNER_TYPED_ACTIVE_FORCED");
        if(members.containsKey(NEXT)) {
            check();Files.delete(directory.resolve(NEXT));var expected=new TreeMap<>(members);expected.remove(NEXT);
            require(expected.equals(scan()),"learner typed redundant deletion changed originals");members=expected;
            AdmissionPaths.forceDirectory(directory);point("LEARNER_TYPED_REDUNDANT_FORCED");
        }
    }
    Decoded receipt()throws IOException {check();require(complete,"learner typed receipt not forced");return receipt;}
    DurableApplicationState<T> state()throws IOException {receipt();return state;}
    /** Force the original ownership handoff before closing both typed handles.
     * No original files or storage reservations are retired by this operation. */
    MembershipLearnerSuccessor.View promoteSuccessor()throws IOException {
        receipt();input.store().requireActive();return input.promote(this);
    }
    MembershipLearnerSlot.View promoteSlot(CurrentHead previous)throws IOException {
        receipt();input.store().requireActive();return input.promoteSlot(this,previous);
    }
    /** Select these exact immutable originals as a nonvoting local generation.
     * Reserve its slot before forcing the marker, and only then release the
     * receiving category through an atomic reservation transfer. */
    PreparedGeneration retainGeneration()throws IOException {
        receipt();input.requireInitialGeneration();
        try {
            if(!input.preparedGeneration())try(var claim=input.prepareGeneration()) {
                write(PREPARED,prepared,"LEARNER_PREPARED");selectionForced=true;point("LEARNER_PREPARED_BEFORE_SELECT");
                input.selectedGeneration(this,claim);
            }else {
                require(members.containsKey(PREPARED) && members.get(PREPARED).bytes()==prepared.length,"learner selected marker missing");
                write(PREPARED,prepared,"LEARNER_PREPARED");selectionForced=true;
            }
            point("LEARNER_PREPARED_BEFORE_RETURN");return new PreparedGeneration(this);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    void checkPreparedSelection()throws IOException {
        receipt();require(selectionForced && members.containsKey(PREPARED) && members.get(PREPARED).bytes()==prepared.length,
                "learner generation selection not forced");
    }
    /** Reopening the promoted typed image does not allocate or select another
     * generation. Its original current source must already own the slot. */
    CurrentHead currentHead()throws IOException {
        receipt();input.requireCurrentTyped(this);return new CurrentHead(this);
    }
    static final class CurrentHead implements MembershipLearnerHead {
        private final MembershipLearnerMaterialization<?> owner;
        private CurrentHead(MembershipLearnerMaterialization<?> owner){this.owner=owner;}
        @Override public void check()throws IOException {owner.receipt();owner.input.requireCurrentTyped(owner);}
        MembershipLearnerStore store()throws IOException {check();return owner.input.store();}
        void requireAvailable()throws IOException {check();store().requireNewSlot();}
        @Override public MembershipLearnerRequest request()throws IOException {check();return owner.input.summary().request();}
        @Override public MembershipCapsule source()throws IOException {check();return owner.input.source();}
        @Override public Decoded receipt()throws IOException {check();return owner.receipt();}
        @Override public MembershipResources resources()throws IOException {check();return owner.input.resources();}
        @Override public void requireDisjoint(Path... paths)throws IOException {
            check();var protectedPaths=new ArrayList<>(List.of(paths));protectedPaths.add(Path.of((String)owner.materialization.get("path")));
            owner.input.requireRefreshPaths(protectedPaths.toArray(Path[]::new));
        }
    }
    static final class PreparedGeneration implements MembershipLearnerHead {
        private final MembershipLearnerMaterialization<?> owner;
        private PreparedGeneration(MembershipLearnerMaterialization<?> owner){this.owner=owner;}
        @Override public void check()throws IOException {owner.checkPreparedSelection();require(owner.input.preparedGeneration(),"learner generation not selected");}
        @Override public MembershipLearnerRequest request()throws IOException {check();return owner.input.summary().request();}
        @Override public MembershipCapsule source()throws IOException {check();return owner.input.source();}
        @Override public Decoded receipt()throws IOException {check();return owner.receipt();}
        @Override public MembershipResources resources()throws IOException {check();return owner.input.resources();}
        MembershipLearnerStore store()throws IOException {check();return owner.input.store();}
        MembershipLearnerSuccessor.View successor()throws IOException {check();return store().successor(this);}
        void closePredecessor()throws IOException {owner.close();}
        void requireCorePath(Path core)throws IOException {
            check();require(core.equals(Path.of((String)owner.materialization.get("path"))),"learner successor changed reserved core path");
        }
        @Override public void requireDisjoint(Path... paths)throws IOException {
            check();var all=new ArrayList<Path>(List.of(paths));all.add(owner.directory);
            all.add(Path.of((String)owner.materialization.get("path")));all.add(request().operationDirectory());all.add(request().replicaDirectory());
            AdmissionPaths.disjoint(all);
        }
    }
    void collectCustody(MembershipLearnerCustody.Collected result)throws IOException {
        result.roots.add(directory);if(!closed && lock!=null)lock.collectCustody(result);
    }
    boolean closed(){return closed;}
    @Override public void close()throws IOException {
        if(closed)return;closed=true;if(lock!=null)lock.close();
    }
}
