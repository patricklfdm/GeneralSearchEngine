package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exclusive coordinator for the immutable plan only. No replica prepare, decision,
 * receipt or seal. A torn plan is retained and refused, never completed from arguments. */
final class MembershipBootstrapPlanFiles implements AutoCloseable {
    @FunctionalInterface interface Check {void run(MembershipBootstrapPlanData plan)throws IOException;}
    static final String LOCK="operation.lock",IMAGE="application.image",FILE="plan.gsbp",NEXT="plan.next.gsbp";
    private final Path directory;
    private final Map<String,Object> binding;
    private final Object directoryKey,lockKey;
    private final MembershipOwnership owner;
    private final MembershipBallotAllocator.Cut cut;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private final MembershipBootstrapPlanData plan;
    private boolean closed,failed;
    private MembershipBootstrapPlanFiles(Path directory,MembershipOwnership owner,MembershipBootstrapPlanData plan,MembershipBallotAllocator.Cut cut)throws IOException {
        this.directory=directory;this.owner=owner;this.plan=plan;this.cut=cut;binding=AdmissionPaths.binding(directory);
        directoryKey=key(directory);lockKey=key(directory.resolve(LOCK));
    }
    static MembershipBootstrapPlanFiles create(MembershipBootstrapPlanData plan,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(plan);Objects.requireNonNull(cut);Path path=plan.operation();recheck(plan);AdmissionPaths.absent(path);
        Files.createDirectory(path);Object createdKey=key(path);AdmissionPaths.forceDirectory(path.getParent());cut.at("BOOTSTRAP_OPERATION_CREATED");
        require(createdKey.equals(key(path)),"bootstrap newly created operation replaced");
        var owner=MembershipOwnership.own(path.resolve(LOCK),true);MembershipBootstrapPlanFiles result=null;
        try {
            result=new MembershipBootstrapPlanFiles(path,owner,plan,cut);result.point("BOOTSTRAP_OPERATION_LOCKED");
            result.write(IMAGE,plan.seed.application(),"BOOTSTRAP_IMAGE");result.write(NEXT,plan.bytes(),"BOOTSTRAP_PLAN");
            result.seal();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    static MembershipBootstrapPlanFiles open(Path requested,MembershipBootstrapPlan expected,MembershipBallotAllocator.Cut cut)throws IOException {
        return open(requested,expected,cut,p->{});
    }
    static MembershipBootstrapPlanFiles open(Path requested,MembershipBootstrapPlan expected,MembershipBallotAllocator.Cut cut,Check check)throws IOException {
        Objects.requireNonNull(expected);Objects.requireNonNull(cut);Objects.requireNonNull(check);Path path=AdmissionPaths.safe(requested);
        require(path.equals(expected.operationDirectory()),"bootstrap plan requested path");
        Object originalKey=key(path);var names=children(path,4);require(names.containsAll(Set.of(LOCK,IMAGE)) && Set.of(LOCK,IMAGE,FILE,NEXT).containsAll(names)
                && (names.contains(FILE)||names.contains(NEXT)),"bootstrap original plan inventory incomplete");
        var owner=MembershipOwnership.own(path.resolve(LOCK),false);MembershipBootstrapPlanFiles result=null;
        try {
            byte[] image=AdmissionPaths.read(path.resolve(IMAGE),MembershipApplicationImage.MAXIMUM);
            byte[] raw=AdmissionPaths.read(path.resolve(names.contains(FILE)?FILE:NEXT),MembershipBootstrapPlanData.MAXIMUM);
            var plan=MembershipBootstrapPlanData.decode(raw,image);require(plan.summary().equals(expected),"bootstrap retained plan differs from reviewed summary");
            // A corrupt active plan is never repaired using a valid candidate.
            if(names.contains(FILE)&&names.contains(NEXT))AdmissionPaths.exact(path.resolve(NEXT),raw);
            recheck(plan);require(originalKey.equals(key(path)),"bootstrap operation replaced during open");result=new MembershipBootstrapPlanFiles(path,owner,plan,cut);
            for(String name:names)if(!name.equals(LOCK))result.remember(name,name.equals(IMAGE)?image:raw);
            result.check();check.run(plan);result.check();result.seal();return result;
        }catch(IOException|RuntimeException|Error error){if(result!=null)result.failed=true;try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static void recheck(MembershipBootstrapPlanData plan)throws IOException {
        for(var bound:plan.bindings())AdmissionPaths.recheck(bound);
        for(var path:plan.summary().absentTargets())AdmissionPaths.absent(path);
    }
    private void check()throws IOException {
        require(!closed && !failed && owner.lock().isValid(),"bootstrap plan owner closed or failed");AdmissionPaths.recheck(binding);recheck(plan);
        require(directoryKey.equals(key(directory)) && lockKey.equals(key(directory.resolve(LOCK))),"bootstrap plan owner identity changed");
        AdmissionPaths.regular(directory.resolve(LOCK));require(Files.size(directory.resolve(LOCK))==0,"bootstrap plan nonempty owner lock");
        var names=new TreeSet<>(files.keySet());names.add(LOCK);require(children(directory,4).equals(names),"bootstrap plan inventory changed");
        for(var row:files.entrySet())require(row.getValue().equals(inspect(directory.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"bootstrap plan member identity changed");
    }
    private void point(String name)throws IOException {check();cut.at(name);check();}
    private void remember(String name,byte[] bytes)throws IOException {
        var next=inspect(directory.resolve(name),bytes.length,hash(bytes));var old=files.get(name);
        require(old==null || old.key().equals(next.key()),"bootstrap plan written inode changed");files.put(name,next);
    }
    private void write(String name,byte[] bytes,String prefix)throws IOException {
        check();Path path=directory.resolve(name);AdmissionPaths.absent(path);
        try(var channel=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(name,new byte[0]);point(prefix+"_CREATED");int half=bytes.length/2;
            AdmissionPaths.write(channel,Arrays.copyOf(bytes,half));remember(name,Arrays.copyOf(bytes,half));point(prefix+"_PREFIX_WRITTEN");
            AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,half,bytes.length));remember(name,bytes);point(prefix+"_WRITTEN");
            channel.force(true);point(prefix+"_FORCED");AdmissionPaths.forceDirectory(directory);point(prefix+"_PARENT_FORCED");
        }
    }
    private void force(String name,String point)throws IOException {
        check();try(var channel=FileChannel.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}point(point);
    }
    private void seal()throws IOException {
        try {
            force(IMAGE,"BOOTSTRAP_RESEAL_IMAGE_FORCED");AdmissionPaths.forceDirectory(directory);point("BOOTSTRAP_RESEAL_IMAGE_PARENT_FORCED");
            if(!files.containsKey(FILE)) {
                force(NEXT,"BOOTSTRAP_RESEAL_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("BOOTSTRAP_RESEAL_PLAN_PARENT_FORCED");
                check();AdmissionPaths.absent(directory.resolve(FILE));Files.move(directory.resolve(NEXT),directory.resolve(FILE),StandardCopyOption.ATOMIC_MOVE);
                files.put(FILE,files.remove(NEXT));point("BOOTSTRAP_PLAN_RENAMED");
            }
            force(FILE,"BOOTSTRAP_ACTIVE_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("BOOTSTRAP_ACTIVE_PLAN_PARENT_FORCED");
            if(files.containsKey(NEXT)) {
                require(files.get(NEXT).bytes()==plan.bytes().length && files.get(NEXT).digest().equals(plan.digest()),"bootstrap redundant plan differs");
                check();Files.delete(directory.resolve(NEXT));files.remove(NEXT);point("BOOTSTRAP_REDUNDANT_PLAN_DELETED");
                AdmissionPaths.forceDirectory(directory);point("BOOTSTRAP_REDUNDANT_PLAN_PARENT_FORCED");
            }
            point("BOOTSTRAP_PLAN_BEFORE_RETURN");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipBootstrapPlan summary()throws IOException {check();return plan.summary();}
    MembershipBootstrapPlanData retained()throws IOException {check();return plan;}
    @Override public void close()throws IOException {if(!closed){closed=true;owner.close();}}
}
