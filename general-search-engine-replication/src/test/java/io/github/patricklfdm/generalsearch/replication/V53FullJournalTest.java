package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Full shared-journal boundary; abandoned PROMISE history is a declared byte fixture. */
class V53FullJournalTest {
    @TempDir Path temp;
    static final int ALLOWANCE=MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+2*MembershipPendingAccept.PREFIX;
    static final int LIMIT=MembershipGrantJournal.MAXIMUM-ALLOWANCE;
    static byte[] promise(Map<String,Object> base,long counter) {
        var fields=new TreeMap<>(base);var ballot=new TreeMap<>(object(fields.get("ballot")));ballot.put("counter",counter);fields.put("ballot",ballot);
        fields.put("basisId",new UUID(0x1353000000000000L,counter).toString());return encode("records","PROMISE",fields);
    }
    static byte[] filled(byte[] original,Map<String,Object> base,int limit) {
        int first=promise(base,1_000_000).length,second=promise(base,10_000_000).length;
        assertEquals(first+1,second);int remaining=limit-original.length,large=-1,small=-1;
        for(int n=1;n<=first;n++)if(remaining>=n*second && (remaining-n*second)%first==0){large=n;small=(remaining-n*second)/first;break;}
        assertTrue(small>0 && small<9_000_000 && large>0);var out=new java.io.ByteArrayOutputStream(limit);out.writeBytes(original);
        for(int i=0;i<small;i++)out.writeBytes(promise(base,1_000_000L+i));
        for(int i=0;i<large;i++)out.writeBytes(promise(base,10_000_000L+i));
        assertEquals(limit,out.size());return out.toByteArray();
    }
    @Test void exactSharedBoundaryCompactsAndRecoversWithoutLosingOriginalSource()throws Exception {
        Path out=Path.of("target/v53-full-journal/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53FullJournalEvidence="+out.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(temp,Files.createDirectory(out.resolve("reference")),3,false);f.campaign(1);
        var target=f.request.targets().getFirst();Path node=target.replicaDirectory(),seed=temp.resolve("full-seed");
        byte[] original=Files.readAllBytes(node.resolve("grants.gsr"));Map<String,Object> base;
        try(var owner=f.open(target,"full-boundary-base")){base=owner.promised().orElseThrow().value();}
        byte[] full=filled(original,base,LIMIT);Files.write(node.resolve("grants.gsr"),full);V53JournalApplicationTest.copy(node,seed);
        Files.write(out.resolve("full-journal.gsr"),full);
        var next=new TreeMap<>(object(base.get("ballot")));next.put("counter",20_000_000L);
        Path inputs=out.resolve("inputs.json");Files.write(inputs,canonical(Map.of("node",node.toString(),"materialization",target.materialization().directory().toString(),
                "observations",V53JournalApplicationTest.observations(f.observations),"next",next,"sharedMaximum",MembershipGrantJournal.MAXIMUM,"reservedBytes",ALLOWANCE,
                "fixtureHistory","preconstructed-complete-abandoned-promises"),1024*1024));
        // Valid frames exceed the complete-owner allowance by exactly one byte.
        for(int limit:List.of(LIMIT+1,MembershipGrantJournal.MAXIMUM+1)) {
            Path rejected=Files.createDirectory(out.resolve("refused-"+limit));byte[] bytes=filled(original,base,limit);Files.write(node.resolve("grants.gsr"),bytes);
            V53JournalApplicationTest.copy(node,rejected.resolve("before"));
            var failure=assertThrows(RuntimeException.class,()->{try(var owner=f.open(target,"refuse-"+limit)) {fail("oversize journal opened");}});
            assertEquals(limit==LIMIT+1?IllegalArgumentException.class:ReplicationException.class,failure.getClass());
            assertEquals(limit==LIMIT+1?"combined pending/grant journal capacity":"authority member exceeds bound",failure.getMessage());
            assertEquals(0,f.resources.usage().leases());V53JournalApplicationTest.copy(node,rejected.resolve("after"));
            Files.write(rejected.resolve("result.json"),canonical(Map.of("type",failure.getClass().getSimpleName(),"message",failure.getMessage()),16384));
        }
        Files.write(node.resolve("grants.gsr"),full);Path clean=Files.createDirectory(out.resolve("clean"));
        V53RetirementSourceProcessTest.child(V53FullJournalWorker.class,inputs,node,clean,"first","none","none");V53JournalApplicationTest.copy(node,clean.resolve("first"));
        V53RetirementSourceProcessTest.child(V53FullJournalWorker.class,inputs,node,clean,"duplicate","none","none");V53JournalApplicationTest.copy(node,clean.resolve("duplicate"));
        var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        for(String mode:List.of("halt","kill"))for(String cut:V53JournalRotationTest.CUTS) {
            Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);Path path=Files.createDirectory(out.resolve(mode+"-"+cut));
            int first=V53RetirementSourceProcessTest.child(V53FullJournalWorker.class,inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
            String second=V53JournalRotationTest.CUTS.indexOf(cut)<3?"JOURNAL_ROTATION_FORCED":"ACCEPT_ACTIVE_FORCED";
            int again=V53RetirementSourceProcessTest.child(V53FullJournalWorker.class,inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
            int last=V53RetirementSourceProcessTest.child(V53FullJournalWorker.class,inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
            rows.add(Map.of("case",mode+"-"+cut,"cut",cut,"mode",mode,"second",second,"exitCodes",List.of(first,again,last),"status","PASS"));
            System.out.println("v53FullJournalCase="+mode+"-"+cut+" PASS");System.out.flush();
        }
        Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-full-journal-v1","status","PASS","cases",rows,"freshProcesses",38,"lockProbes",6,
                "journalBytes",LIMIT,"sharedMaximum",MembershipGrantJournal.MAXIMUM,"reservedBytes",ALLOWANCE,"publicRuntime",false,"powerLoss",false),65536));
    }
}
