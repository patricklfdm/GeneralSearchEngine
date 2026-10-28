package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Forced original plan only. Replica authority must still be absent. Incomplete
 * original plan bytes are preserved and refused, never rebuilt from call arguments. */
final class MembershipLearnerAdmissionFiles implements AutoCloseable {
    static final String LOCK="operation.lock",FILE="learner.gslp",NEXT="learner.next.gslp";
    private final MembershipLearnerAdmissionPlan plan;
    private final Path directory;
    private final Object directoryKey,lockKey;
    private final MembershipOwnership owner;
    private final MembershipResources.Lease lease;
    private final MembershipBallotAllocator.Cut cut;
    private final MembershipGenerationFiles.Guard source;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private boolean closed,failed;
    private MembershipLearnerAdmissionFiles(MembershipLearnerAdmissionPlan plan,MembershipOwnership owner,MembershipResources.Lease lease,
            MembershipBallotAllocator.Cut cut,MembershipGenerationFiles.Guard source)throws IOException {
        this.plan=plan;directory=plan.request.operationDirectory();this.owner=owner;this.lease=lease;this.cut=cut;this.source=source;
        directoryKey=key(directory);lockKey=key(directory.resolve(LOCK));
    }
    static MembershipLearnerAdmissionFiles create(MembershipLearnerAdmissionPlan plan,MembershipResources resources,
            MembershipBallotAllocator.Cut cut,MembershipGenerationFiles.Guard source)throws IOException {
        Objects.requireNonNull(cut);Objects.requireNonNull(source);source.check();plan.recheckPaths();Path directory=plan.request.operationDirectory();AdmissionPaths.absent(directory);
        var lease=resources.reserve(MembershipResources.Unit.MISC,"learner-plan",plan.bytes().length);MembershipOwnership owner=null;MembershipLearnerAdmissionFiles result=null;
        try {
            Files.createDirectory(directory);Object created=key(directory);AdmissionPaths.forceDirectory(directory.getParent());cut.at("LEARNER_OPERATION_CREATED");
            source.check();plan.recheckPaths();require(created.equals(key(directory)),"learner new operation replaced");
            owner=MembershipOwnership.own(directory.resolve(LOCK),true);result=new MembershipLearnerAdmissionFiles(plan,owner,lease,cut,source);
            result.point("LEARNER_OPERATION_LOCKED");result.write();result.seal();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;
            try{if(owner!=null)owner.close();}catch(IOException close){error.addSuppressed(close);}finally{lease.close();}throw error;}
    }
    static MembershipLearnerAdmissionFiles open(MembershipLearnerPlan expected,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(expected);Objects.requireNonNull(cut);Path directory=AdmissionPaths.safe(expected.request().operationDirectory());Object originalKey=key(directory);
        var names=children(directory,3);require(names.contains(LOCK) && Set.of(LOCK,FILE,NEXT).containsAll(names) && (names.contains(FILE)||names.contains(NEXT)),"learner original plan incomplete inventory");
        var owner=MembershipOwnership.own(directory.resolve(LOCK),false);MembershipResources.Lease lease=null;MembershipLearnerAdmissionFiles result=null;
        try {
            byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(FILE)?FILE:NEXT),MembershipLearnerAdmissionPlan.MAXIMUM);
            var plan=MembershipLearnerAdmissionPlan.decode(bytes);require(plan.summary().equals(expected),"learner original plan differs from reviewed summary");
            // A valid candidate never repairs a corrupt/missing committed decision.
            if(names.contains(FILE)&&names.contains(NEXT))AdmissionPaths.exact(directory.resolve(NEXT),bytes);
            plan.recheckPaths();require(originalKey.equals(key(directory)),"learner operation replaced during open");
            lease=resources.reserve(MembershipResources.Unit.MISC,"learner-plan",bytes.length);result=new MembershipLearnerAdmissionFiles(plan,owner,lease,cut,()->{});
            for(String name:names)if(!name.equals(LOCK))result.remember(name,bytes);
            result.check();result.seal();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;
            try{owner.close();}catch(IOException close){error.addSuppressed(close);}finally{if(lease!=null)lease.close();}throw error;}
    }
    private void check()throws IOException {
        require(!closed && !failed && owner.lock().isValid(),"learner plan owner closed or failed");source.check();plan.recheckPaths();
        require(directoryKey.equals(key(directory)) && lockKey.equals(key(directory.resolve(LOCK))),"learner plan owner identity changed");
        AdmissionPaths.regular(directory.resolve(LOCK));require(Files.size(directory.resolve(LOCK))==0,"learner plan nonempty lock");
        var names=new TreeSet<>(files.keySet());names.add(LOCK);require(children(directory,3).equals(names),"learner plan inventory changed");
        for(var file:files.entrySet())require(file.getValue().equals(inspect(directory.resolve(file.getKey()),file.getValue().bytes(),file.getValue().digest())),"learner plan original member changed");
    }
    private void point(String name)throws IOException {check();cut.at(name);check();}
    private void remember(String name,byte[] bytes)throws IOException {
        var next=inspect(directory.resolve(name),bytes.length,hash(bytes));var old=files.get(name);
        require(old==null || old.key().equals(next.key()),"learner plan written inode changed");files.put(name,next);
    }
    private void write()throws IOException {
        check();byte[] bytes=plan.bytes();
        try(var channel=FileChannel.open(directory.resolve(NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(NEXT,new byte[0]);point("LEARNER_PLAN_CREATED");int half=bytes.length/2;
            AdmissionPaths.write(channel,Arrays.copyOf(bytes,half));remember(NEXT,Arrays.copyOf(bytes,half));point("LEARNER_PLAN_PREFIX_WRITTEN");
            AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,half,bytes.length));remember(NEXT,bytes);point("LEARNER_PLAN_WRITTEN");
            channel.force(true);point("LEARNER_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_PLAN_PARENT_FORCED");
        }
    }
    private void force(String name,String point)throws IOException {
        check();try(var channel=FileChannel.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}point(point);
    }
    private void seal()throws IOException {
        try {
            if(!files.containsKey(FILE)) {
                force(NEXT,"LEARNER_RESEAL_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_RESEAL_PLAN_PARENT_FORCED");
                check();AdmissionPaths.absent(directory.resolve(FILE));Files.move(directory.resolve(NEXT),directory.resolve(FILE),StandardCopyOption.ATOMIC_MOVE);
                files.put(FILE,files.remove(NEXT));point("LEARNER_PLAN_RENAMED");
            }
            force(FILE,"LEARNER_ACTIVE_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_ACTIVE_PLAN_PARENT_FORCED");
            if(files.containsKey(NEXT)) {
                require(files.get(NEXT).digest().equals(hash(plan.bytes())),"learner redundant plan differs");
                check();Files.delete(directory.resolve(NEXT));files.remove(NEXT);point("LEARNER_REDUNDANT_PLAN_DELETED");
                AdmissionPaths.forceDirectory(directory);point("LEARNER_REDUNDANT_PLAN_PARENT_FORCED");
            }
            point("LEARNER_PLAN_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipLearnerPlan summary()throws IOException {check();return plan.summary();}
    MembershipLearnerAdmissionPlan retained()throws IOException {check();return plan;}
    @Override public void close()throws IOException {if(!closed){closed=true;try{owner.close();}finally{lease.close();}}}
}
