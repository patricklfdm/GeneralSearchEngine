package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Forced original plan and optional source-retention decision. Replica authority
 * must remain absent until that decision is forced. Incomplete original decisions
 * are preserved and refused, never rebuilt from call arguments. */
final class MembershipLearnerAdmissionFiles implements AutoCloseable {
    static final String LOCK="operation.lock",FILE="learner.gslp",NEXT="learner.next.gslp",RETAIN="learner-source.gslp",RETAIN_NEXT="learner-source.next.gslp";
    private final MembershipLearnerAdmissionPlan plan;
    private final Path directory;
    private final Object directoryKey,lockKey;
    private final MembershipOwnership owner;
    private final MembershipResources.Lease lease;
    private final MembershipResources resources;
    private final MembershipBallotAllocator.Cut cut;
    private final MembershipGenerationFiles.Guard source;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private boolean closed,failed,replicaAllowed;
    private MembershipLearnerRetention retention;
    private MembershipLearnerAdmissionFiles(MembershipLearnerAdmissionPlan plan,MembershipOwnership owner,MembershipResources resources,MembershipResources.Lease lease,
            MembershipBallotAllocator.Cut cut,MembershipGenerationFiles.Guard source)throws IOException {
        this.plan=plan;directory=plan.request.operationDirectory();this.owner=owner;this.resources=resources;this.lease=lease;this.cut=cut;this.source=source;
        directoryKey=key(directory);lockKey=key(directory.resolve(LOCK));
    }
    static MembershipLearnerAdmissionFiles create(MembershipLearnerAdmissionPlan plan,MembershipResources resources,
            MembershipBallotAllocator.Cut cut,MembershipGenerationFiles.Guard source)throws IOException {
        Objects.requireNonNull(cut);Objects.requireNonNull(source);source.check();plan.recheckPaths();Path directory=plan.request.operationDirectory();AdmissionPaths.absent(directory);
        var lease=resources.reserve(MembershipResources.Unit.MISC,"learner-plan",plan.bytes().length);MembershipOwnership owner=null;MembershipLearnerAdmissionFiles result=null;
        try {
            Files.createDirectory(directory);Object created=key(directory);AdmissionPaths.forceDirectory(directory.getParent());cut.at("LEARNER_OPERATION_CREATED");
            source.check();plan.recheckPaths();require(created.equals(key(directory)),"learner new operation replaced");
            owner=MembershipOwnership.own(directory.resolve(LOCK),true);result=new MembershipLearnerAdmissionFiles(plan,owner,resources,lease,cut,source);
            result.point("LEARNER_OPERATION_LOCKED");result.write();result.seal();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;
            try{if(owner!=null)owner.close();}catch(IOException close){error.addSuppressed(close);}finally{lease.close();}throw error;}
    }
    static MembershipLearnerAdmissionFiles open(MembershipLearnerPlan expected,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws IOException {
        return open(expected,resources,cut,false);
    }
    static MembershipLearnerAdmissionFiles openAdmission(MembershipLearnerPlan expected,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws IOException {
        return open(expected,resources,cut,true);
    }
    static MembershipLearnerAdmissionFiles openPlacement(MembershipLearnerPlan expected,MembershipResources resources,
            MembershipLearnerPlacement.Recovery recovery)throws IOException {
        recovery.check();return open(expected,resources,e->{},true,recovery);
    }
    private static MembershipLearnerAdmissionFiles open(MembershipLearnerPlan expected,MembershipResources resources,MembershipBallotAllocator.Cut cut,boolean admission)throws IOException {
        return open(expected,resources,cut,admission,null);
    }
    private static MembershipLearnerAdmissionFiles open(MembershipLearnerPlan expected,MembershipResources resources,MembershipBallotAllocator.Cut cut,
            boolean admission,MembershipLearnerPlacement.Recovery recovery)throws IOException {
        Objects.requireNonNull(expected);Objects.requireNonNull(cut);Path directory=AdmissionPaths.safe(expected.request().operationDirectory());Object originalKey=key(directory);
        var names=children(directory,5);var allowed=admission?Set.of(LOCK,FILE,NEXT,RETAIN,RETAIN_NEXT):Set.of(LOCK,FILE,NEXT);
        require(names.contains(LOCK) && allowed.containsAll(names) && (names.contains(FILE)||names.contains(NEXT)),"learner original plan incomplete inventory");
        var owner=MembershipOwnership.own(directory.resolve(LOCK),false);MembershipResources.Lease lease=null;MembershipLearnerAdmissionFiles result=null;
        try {
            byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(FILE)?FILE:NEXT),MembershipLearnerAdmissionPlan.MAXIMUM);
            var plan=MembershipLearnerAdmissionPlan.decode(bytes);require(plan.summary().equals(expected),"learner original plan differs from reviewed summary");
            // A valid candidate never repairs a corrupt/missing committed decision.
            if(names.contains(FILE)&&names.contains(NEXT))AdmissionPaths.exact(directory.resolve(NEXT),bytes);
            boolean hasRetention=names.contains(RETAIN)||names.contains(RETAIN_NEXT);
            require(!hasRetention || names.contains(FILE),"retention lacks original active learner plan");
            MembershipLearnerRetention retained=null;byte[] retentionBytes=null;
            if(hasRetention) {
                retentionBytes=AdmissionPaths.read(directory.resolve(names.contains(RETAIN)?RETAIN:RETAIN_NEXT),MembershipLearnerRetention.MAXIMUM);
                retained=MembershipLearnerRetention.decode(retentionBytes,plan);
                if(names.contains(RETAIN)&&names.contains(RETAIN_NEXT))AdmissionPaths.exact(directory.resolve(RETAIN_NEXT),retentionBytes);
            }
            plan.recheckPaths(!names.contains(RETAIN));require(originalKey.equals(key(directory)),"learner operation replaced during open");
            if(recovery!=null) {
                recovery.check();require(names.equals(Set.of(LOCK,FILE,RETAIN)),"learner placement requires complete original admission");
                MembershipLearnerStore.preflight(plan,Objects.requireNonNull(retained),recovery);
            }else if(retained!=null)MembershipLearnerStore.preflight(plan,retained);
            lease=resources.reserve(MembershipResources.Unit.MISC,"learner-plan",bytes.length);result=new MembershipLearnerAdmissionFiles(plan,owner,resources,lease,cut,recovery==null?()->{}:recovery::readGuard);
            result.replicaAllowed=names.contains(RETAIN);result.retention=retained;
            if(hasRetention)lease.reserveMisc(MembershipResources.Unit.MISC.bytes);
            for(String name:names)if(!name.equals(LOCK))result.remember(name,(name.equals(RETAIN)||name.equals(RETAIN_NEXT))?retentionBytes:bytes);
            result.check();
            if(recovery!=null)return result; // Original read-only validation; no seal or repair.
            if(retained!=null && MembershipLearnerRetirement.load(plan,retained)!=null) {
                require(names.contains(FILE) && names.contains(RETAIN) && !names.contains(NEXT) && !names.contains(RETAIN_NEXT),
                        "learner retirement incomplete original admission");
                // Recovery must validate the independently retained successor
                // before any writes; the original decisions are already active.
                return result;
            }
            result.seal();if(hasRetention)result.sealRetention();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;
            try{owner.close();}catch(IOException close){error.addSuppressed(close);}finally{if(lease!=null)lease.close();}throw error;}
    }
    private void check()throws IOException {
        require(!closed && !failed && owner.lock().isValid(),"learner plan owner closed or failed");source.check();plan.recheckPaths(!replicaAllowed);
        require(directoryKey.equals(key(directory)) && lockKey.equals(key(directory.resolve(LOCK))),"learner plan owner identity changed");
        AdmissionPaths.regular(directory.resolve(LOCK));require(Files.size(directory.resolve(LOCK))==0,"learner plan nonempty lock");
        var names=new TreeSet<>(files.keySet());names.add(LOCK);require(children(directory,5).equals(names),"learner plan inventory changed");
        for(var file:files.entrySet())require(file.getValue().equals(inspect(directory.resolve(file.getKey()),file.getValue().bytes(),file.getValue().digest())),"learner plan original member changed");
    }
    private void point(String name)throws IOException {check();cut.at(name);check();}
    private void remember(String name,byte[] bytes)throws IOException {
        var next=inspect(directory.resolve(name),bytes.length,hash(bytes));var old=files.get(name);
        require(old==null || old.key().equals(next.key()),"learner plan written inode changed");files.put(name,next);
    }
    private void write()throws IOException {write(NEXT,plan.bytes(),"LEARNER_PLAN");}
    private void write(String name,byte[] bytes,String prefix)throws IOException {
        check();AdmissionPaths.absent(directory.resolve(name));
        try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(name,new byte[0]);point(prefix+"_CREATED");int half=bytes.length/2;
            AdmissionPaths.write(channel,Arrays.copyOf(bytes,half));remember(name,Arrays.copyOf(bytes,half));point(prefix+"_PREFIX_WRITTEN");
            AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,half,bytes.length));remember(name,bytes);point(prefix+"_WRITTEN");
            channel.force(true);point(prefix+"_FORCED");AdmissionPaths.forceDirectory(directory);point(prefix+"_PARENT_FORCED");
        }
    }
    private void force(String name,String point)throws IOException {
        check();try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}point(point);
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
    void collectCustody(MembershipLearnerCustody.Collected result)throws IOException {
        check();result.roots.add(directory);owner.collectCustody(result);result.leases.add(lease);
    }
    void reserveAdmission()throws IOException {check();lease.reserveMisc(MembershipResources.Unit.MISC.bytes);}
    MembershipResources.Lease reserveTypedImage(long bytes)throws IOException {
        check();require(replicaAllowed && retention!=null,"typed learner requires retained admission");reserveAdmission();
        return resources.reserve(MembershipResources.Unit.APPLICATION,"learner-typed-backup",bytes);
    }
    MembershipResources resources()throws IOException {check();return resources;}
    void requireFreshRetention()throws IOException {check();require(retention==null && !replicaAllowed,"retained learner source requires explicit resume");}
    void retainSource(MembershipLearnerRetention decision)throws IOException {
        check();require(decision.plan.summary().equals(plan.summary()),"learner retention foreign plan");reserveAdmission();
        try {
            if(retention!=null)require(Arrays.equals(retention.bytes(),decision.bytes()),"learner retention decision changed");
            else {require(!files.containsKey(RETAIN)&&!files.containsKey(RETAIN_NEXT),"learner retention unexpected files");retention=decision;write(RETAIN_NEXT,decision.bytes(),"LEARNER_RETENTION");}
            sealRetention();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void sealRetention()throws IOException {
        try {
            if(!files.containsKey(RETAIN)) {
                force(RETAIN_NEXT,"LEARNER_RETENTION_RESEAL_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_RETENTION_RESEAL_PARENT_FORCED");
                check();AdmissionPaths.absent(directory.resolve(RETAIN));Files.move(directory.resolve(RETAIN_NEXT),directory.resolve(RETAIN),StandardCopyOption.ATOMIC_MOVE);
                files.put(RETAIN,files.remove(RETAIN_NEXT));point("LEARNER_RETENTION_RENAMED");
            }
            force(RETAIN,"LEARNER_RETENTION_ACTIVE_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_RETENTION_ACTIVE_PARENT_FORCED");
            if(files.containsKey(RETAIN_NEXT)) {
                require(files.get(RETAIN_NEXT).digest().equals(hash(retention.bytes())),"learner redundant retention differs");
                check();Files.delete(directory.resolve(RETAIN_NEXT));files.remove(RETAIN_NEXT);point("LEARNER_RETENTION_REDUNDANT_DELETED");
                AdmissionPaths.forceDirectory(directory);point("LEARNER_RETENTION_REDUNDANT_PARENT_FORCED");
            }
            replicaAllowed=true;point("LEARNER_RETENTION_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipLearnerRetention retention()throws IOException {check();require(replicaAllowed && retention!=null && files.containsKey(RETAIN),"learner retention not forced");return retention;}
    void checkOwner()throws IOException {check();}
    MembershipLearnerPlan summary()throws IOException {check();return plan.summary();}
    MembershipLearnerAdmissionPlan retained()throws IOException {check();return plan;}
    @Override public void close()throws IOException {if(!closed){closed=true;try{owner.close();}finally{lease.close();}}}
}
