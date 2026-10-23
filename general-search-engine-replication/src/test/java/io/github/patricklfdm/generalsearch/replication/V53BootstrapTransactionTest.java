package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;

class V53BootstrapTransactionTest {
    @TempDir Path temp;
    MembershipBootstrapPlanData fixture(String name,int count,boolean backup)throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;var plan=helper.fixture(name,count,backup).plan();
        try(var owner=MembershipBootstrapPlanFiles.create(plan,e->{})){assertEquals(plan.summary(),owner.summary());}return plan;
    }
    static MembershipBootstrapResult run(MembershipBootstrapPlanData plan,boolean resume,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipBootstrapTransaction.apply(plan.summary(),resume,()->{},cut);
    }
    static Map<String,String> files(MembershipBootstrapPlanData plan)throws Exception {
        var out=new TreeMap<String,String>();out.putAll(V53ReplayFilesTest.files(plan.operation()));int i=0;
        for(Path p:plan.summary().absentTargets()){if(Files.exists(p)){final String prefix="target-"+i+"/";V53ReplayFilesTest.files(p).forEach((k,v)->out.put(prefix+k,v));}i++;}return out;
    }
    static void copy(MembershipBootstrapPlanData plan,Path dest)throws Exception {
        Files.createDirectories(dest);V53JournalApplicationTest.copy(plan.operation(),dest.resolve("operation"));int i=0;
        for(Path p:plan.summary().absentTargets()){if(Files.exists(p))V53JournalApplicationTest.copy(p,dest.resolve("target-"+i));i++;}
    }
    static void verify(MembershipBootstrapPlanData plan)throws Exception {
        var data=new MembershipBootstrapCommitData(plan);assertArrayEquals(data.journal(4),Files.readAllBytes(plan.operation().resolve(JOURNAL)));
        assertArrayEquals(data.receipt(),Files.readAllBytes(plan.operation().resolve(RECEIPT)));assertFalse(Files.exists(plan.operation().resolve(PENDING)));
        for(int i=0;i<data.targets.size();i++) {
            var expected=new TreeMap<>(data.payload(i));expected.put(PREPARED,data.preparation(i));expected.put(SEAL,data.seal(i));
            assertEquals(V53BootstrapPlanTest.hashes(expected),V53ReplayFilesTest.files(data.targets.get(i)));
            assertFalse(Files.exists(plan.summary().absentTargets().get(2*i+1)));
        }
        assertEquals(data.result(),MembershipBootstrapTransaction.read(plan.summary()));
    }
    @Test void preparesEveryVoterBeforeGlobalCommitAndLocalSealsForAllSizesAndBothSources()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var p=fixture("complete-"+size+"-"+backup,size,backup);var events=new ArrayList<String>();var data=new MembershipBootstrapCommitData(p);
            assertEquals(data.result(),run(p,false,events::add));verify(p);
            for(int i=0;i<size;i++)assertTrue(events.indexOf("BOOTSTRAP_PREPARATION_"+i+"_PARENT_FORCED")<events.indexOf("BOOTSTRAP_PREPARED_PREFIX_WRITTEN"));
            assertTrue(events.indexOf("BOOTSTRAP_COMMITTING_DURABLE")<events.indexOf("BOOTSTRAP_RECEIPT_CANDIDATE_CREATED"));
            assertTrue(events.indexOf("BOOTSTRAP_RECEIPT_ACTIVE_PARENT_FORCED")<events.indexOf("BOOTSTRAP_COMMITTED_PREFIX_WRITTEN"));
            assertTrue(events.indexOf("BOOTSTRAP_COMMITTED_DURABLE")<events.indexOf("BOOTSTRAP_SEAL_0_CANDIDATE_CREATED"));
            var before=files(p);assertEquals(data.result(),run(p,true,e->{}));assertEquals(before,files(p));
            assertThrows(IllegalArgumentException.class,()->run(p,false,e->{}));assertEquals(before,files(p));
        }
    }
    @Test void fullCompletionBudgetIncludesAllOriginalAndTemporaryMetadata()throws Exception {
        var p=fixture("budget",5,true);var data=new MembershipBootstrapCommitData(p);var body=V53BootstrapPlanTest.body(p.bytes());
        body.put("maximumOperation",2L*p.bytes().length+p.seed.application().length+p.seed.payloadBytes()+100L);
        var small=MembershipBootstrapPlanData.decode(MembershipBootstrapPlanData.encode(body),p.seed.application());
        assertThrows(IllegalArgumentException.class,()->new MembershipBootstrapCommitData(small));assertTrue(data.completionBytes<p.maximumOperation);
        assertEquals(Set.of("operation.lock","plan.gsbp","application.image"),V53ReplayFilesTest.files(p.operation()).keySet());
    }
    @Test void allSelectedPrefixDecisionAndPublicationCutsResumeAfterAnotherRecoveryInterruption()throws Exception {
        var baseline=fixture("baseline",3,false);var events=new ArrayList<String>();run(baseline,false,events::add);
        var points=events.stream().filter(e->e.endsWith("_DURABLE") || e.endsWith("_BEFORE_RETURN") || e.startsWith("BOOTSTRAP_TARGET_") ||
                e.startsWith("BOOTSTRAP_DIRECTORY_0_") || e.startsWith("BOOTSTRAP_PAYLOAD_0_") && (e.endsWith("_PREFIX_WRITTEN") || e.endsWith("_CREATED")) ||
                e.startsWith("BOOTSTRAP_PREPARATION_0_") || e.equals("BOOTSTRAP_PREPARATION_2_PARENT_FORCED") ||
                List.of("PREPARING","PREPARED","COMMITTING","COMMITTED").stream().anyMatch(s->e.startsWith("BOOTSTRAP_"+s+"_") && !e.endsWith("BEFORE_RETURN")) ||
                e.startsWith("BOOTSTRAP_RECEIPT_") || e.startsWith("BOOTSTRAP_SEAL_0_")).distinct().toList();
        Path evidence=Path.of("target/v53-bootstrap-transaction/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int n=0;n<points.size();n++) {
            String stop=points.get(n);var p=fixture("cut-"+n,3,false);Path member=Files.createDirectory(evidence.resolve(String.format("case-%03d",n)));
            Files.write(member.resolve("original-plan.gsbp"),p.bytes());Files.write(member.resolve("original-application.image"),p.seed.application());
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resumed=new ArrayList<String>();
            assertThrows(IOException.class,()->run(p,false,e->{first.add(e);if(e.equals(stop))throw new IOException(stop);}));copy(p,member.resolve("crash"));
            assertThrows(IOException.class,()->run(p,true,e->{second.add(e);if(e.equals("BOOTSTRAP_RESEAL_0_root.gsr_FORCED"))throw new IOException("recovery interrupted");}));copy(p,member.resolve("second-crash"));
            run(p,true,resumed::add);verify(p);copy(p,member.resolve("final"));
            Files.write(member.resolve("events.json"),canonical(Map.of("first",first,"second",second,"resumed",resumed),1024*1024));
            rows.add(Map.of("case",member.getFileName().toString(),"cut",stop,"plan",p.digest(),"status","PASS"));
            if((n+1)%10==0)System.out.println("v53BootstrapTransactionProgress="+(n+1)+"/"+points.size());
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-transaction-v1","status","PASS","cases",rows,"freshProcesses",false,"publicBootstrap",false),65536));
        System.out.println("v53BootstrapTransactionEvidence="+evidence.toAbsolutePath());
    }
    @Test void preparedOrPartiallyPreparedTargetsCannotBeRegeneratedFromThePlan()throws Exception {
        for(String point:List.of("BOOTSTRAP_PREPARATION_0_PREFIX_WRITTEN","BOOTSTRAP_PREPARED_PREFIX_WRITTEN","BOOTSTRAP_PREPARED_DURABLE","BOOTSTRAP_COMMITTING_DURABLE","BOOTSTRAP_COMMITTED_DURABLE")) {
            var p=fixture(point,3,false);assertThrows(IOException.class,()->run(p,false,e->{if(e.equals(point))throw new IOException(point);}));
            Files.delete(p.summary().absentTargets().getFirst().resolve("root.gsr"));var before=files(p);
            assertThrows(Exception.class,()->run(p,true,e->{}));assertEquals(before,files(p));
        }
    }
    @Test void corruptedOriginalsUnknownMembersAndOutOfOrderAuthorityStayUnchanged()throws Exception {
        for(String variant:List.of("journal","image","plan","receipt","seal","extra","early-receipt","early-seal","partial-active","copied-node","occupied-core")) {
            var p=fixture(variant,3,false);var data=new MembershipBootstrapCommitData(p);
            if(variant.startsWith("early"))assertThrows(IOException.class,()->run(p,false,e->{if(e.equals("BOOTSTRAP_PREPARING_DURABLE"))throw new IOException(e);}));else run(p,false,e->{});
            Path node=data.targets.getFirst();switch(variant) {
                case "journal"->Files.write(p.operation().resolve(JOURNAL),new byte[]{1});case "image"->Files.delete(p.operation().resolve("application.image"));
                case "plan"->Files.write(p.operation().resolve("plan.gsbp"),new byte[]{1});case "receipt"->Files.delete(p.operation().resolve(RECEIPT));
                case "seal","partial-active"->Files.write(node.resolve(SEAL),new byte[]{1});case "extra"->Files.writeString(node.resolve("keep"),"keep");
                case "early-receipt"->Files.write(p.operation().resolve(RECEIPT),data.receipt());
                case "early-seal"->{Files.createDirectory(node);Files.write(node.resolve(SEAL),data.seal(0));}
                case "copied-node"->Files.write(node.resolve("node.gsr"),data.payload(1).get("node.gsr"));
                case "occupied-core"->Files.createDirectory(p.summary().absentTargets().get(1));default->throw new AssertionError();
            }
            var before=files(p);assertThrows(Exception.class,()->run(p,true,e->{}));assertEquals(before,files(p));
        }
    }
    @Test void coordinatorAndReplicaOwnersRemainExclusiveAndIdentityChangesPoisonTheTransaction()throws Exception {
        var p=fixture("locks",3,false);run(p,false,e->{if(e.equals("BOOTSTRAP_OWNED_0")) {
            assertThrows(ReplicationException.class,()->run(p,true,x->{}));
            assertThrows(ReplicationException.class,()->MembershipOwnership.own(p.summary().absentTargets().getFirst().resolve("replica.lock"),false));
        }});
        for(String point:List.of("BOOTSTRAP_PREPARING_DURABLE","BOOTSTRAP_PAYLOAD_0_root.gsr_FORCED","BOOTSTRAP_SEAL_0_ACTIVE_FORCED")) {
            var changed=fixture(point,3,false);Path target=point.contains("PREPARING")?changed.operation().resolve(JOURNAL):changed.summary().absentTargets().getFirst().resolve(point.contains("SEAL")?SEAL:"root.gsr");
            assertThrows(IllegalArgumentException.class,()->run(changed,false,e->{if(e.equals(point)) {
                Path other=target.resolveSibling("replacement");Files.copy(target,other);Files.move(other,target,StandardCopyOption.REPLACE_EXISTING);
            }}));
        }
    }
    @Test void typedRecheckFailureBeforeCommitRetainsPreparedAuthorityAndNoReceipt()throws Exception {
        var p=fixture("recheck",3,true);var calls=new AtomicInteger();
        assertThrows(IOException.class,()->MembershipBootstrapTransaction.apply(p.summary(),false,()->{if(calls.incrementAndGet()==2)throw new IOException("typed drift");},e->{}));
        var data=new MembershipBootstrapCommitData(p);assertArrayEquals(data.journal(2),Files.readAllBytes(p.operation().resolve(JOURNAL)));
        assertFalse(Files.exists(p.operation().resolve(RECEIPT)));var before=files(p);assertThrows(IllegalArgumentException.class,()->MembershipBootstrapTransaction.read(p.summary()));assertEquals(before,files(p));
        assertEquals(data.result(),run(p,true,e->{}));verify(p);
    }
    public static final class LockProbe {
        public static void main(String[] args)throws Exception {
            for(String arg:args)try(var channel=java.nio.channels.FileChannel.open(Path.of(arg),StandardOpenOption.READ,StandardOpenOption.WRITE)) {
                try(var lock=channel.tryLock()){if(lock!=null)System.exit(2);}
            }
        }
    }
    @Test void completedForcesDoNotReleaseTheRealCrossProcessOwnershipLocks()throws Exception {
        var plan=fixture("cross-process-lock",3,false);
        run(plan,false,event->{if(event.equals("BOOTSTRAP_COMMITTED_BEFORE_RETURN")) {
            assertThrows(ReplicationException.class,()->MembershipBootstrapTransaction.read(plan.summary()));
            var command=new ArrayList<String>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),LockProbe.class.getName()));
            command.add(plan.operation().resolve("operation.lock").toString());for(int i=0;i<6;i+=2)command.add(plan.summary().absentTargets().get(i).resolve("replica.lock").toString());
            var child=new ProcessBuilder(command).redirectErrorStream(true).start();
            try {assertTrue(child.waitFor(20,java.util.concurrent.TimeUnit.SECONDS),"lock probe deadline");assertEquals(0,child.exitValue(),new String(child.getInputStream().readAllBytes()));}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}finally{if(child.isAlive())child.destroyForcibly();}
        }});
    }

}
