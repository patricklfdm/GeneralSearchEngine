package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapRevalidationTest {
    @TempDir Path temp;
    V53BootstrapPlanTest.Fixture fixture(String name,int size,boolean backup)throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;var f=helper.fixture(name,size,backup);
        try(var owner=MembershipBootstrapPlanFiles.create(f.plan(),e->{})){assertEquals(f.plan().summary(),owner.summary());}return f;
    }
    static Map<String,String> authority(MembershipBootstrapPlanData plan)throws IOException {
        var result=new TreeMap<String,String>();var paths=new ArrayList<Path>();paths.add(plan.operation());paths.addAll(plan.summary().absentTargets());
        for(int i=0;i<paths.size();i++)if(Files.exists(paths.get(i)))try(var stream=Files.walk(paths.get(i))){for(Path file:stream.filter(Files::isRegularFile).toList()) {
            byte[] bytes;if(file.getFileName().toString().endsWith(".lock")){assertEquals(0,Files.size(file));bytes=new byte[0];}else bytes=Files.readAllBytes(file);
            result.put(i+"/"+paths.get(i).relativize(file),hash(bytes));
        }}return result;
    }
    static long bytes(Path scratch)throws IOException{return AdmissionPaths.inventory(scratch,1L<<30).stream().mapToLong(AdmissionFormat.Member::size).sum();}
    @Test void realTypedCallbacksVerifyBothDecisionBoundariesForEverySizeAndSource()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-revalidation/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var f=fixture("complete-"+size+"-"+backup,size,backup);Path base=f.plan().operation().getParent();var count=new AtomicInteger();var retained=new AtomicLong(bytes(base.resolve("scratch")));
            var result=MembershipBootstrapTransaction.apply(f.plan().summary(),false,()->{
                int ordinal=count.incrementAndGet();var before=authority(f.plan());Path scratch=base.resolve("validation-"+ordinal);
                long used=MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),scratch,retained.get());assertEquals(bytes(scratch),used);retained.addAndGet(used);
                assertEquals(before,authority(f.plan()));
            },e->{});
            assertEquals(2,count.get());V53BootstrapTransactionTest.verify(f.plan());assertEquals(f.plan().seed.root,result.root());
            var before=authority(f.plan());long used=MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),base.resolve("validation-complete"),retained.get());
            assertTrue(used>0);assertEquals(before,authority(f.plan()));
            Path member=Files.createDirectory(evidence.resolve("size-"+size+"-"+(backup?"backup":"empty")));
            Files.write(member.resolve("original-plan.gsbp"),f.plan().bytes());Files.write(member.resolve("original-application.image"),f.plan().seed.application());
            V53JournalApplicationTest.copy(base.resolve("scratch"),member.resolve("planning-scratch"));
            if(backup)V53JournalApplicationTest.copy(f.request().sourcePath().orElseThrow(),member.resolve("original-source"));
            for(int i=1;i<=2;i++)V53JournalApplicationTest.copy(base.resolve("validation-"+i),member.resolve("validation-"+i));
            V53JournalApplicationTest.copy(base.resolve("validation-complete"),member.resolve("validation-complete"));
            Files.write(member.resolve("receipt.gsbp"),Files.readAllBytes(f.plan().operation().resolve(MembershipBootstrapCommitData.RECEIPT)));
            rows.add(Map.of("case",member.getFileName().toString(),"size",size,"source",f.request().source().name(),"callbacks",2,"plan",f.plan().digest(),"retainedBytes",retained.get()+used,"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-revalidation-v1","status","PASS","cases",rows,"publicBootstrap",false,"freshProcesses",false),65536));
        System.out.println("v53BootstrapRevalidationEvidence="+evidence.toAbsolutePath());
    }
    @Test void changedBuilderRequestAndSourceRejectBeforeScratchWrites()throws Exception {
        var f=fixture("drift",3,true);var p=f.plan();var r=f.request();Path scratch=temp.resolve("scratch");var before=authority(p);
        var wrong=io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class,ID).index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE)).configuration();
        assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(wrong,r,p,scratch,0));assertFalse(Files.exists(scratch));
        var budget=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes()+1);
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),budget,p,scratch,0));assertFalse(Files.exists(scratch));
        Files.writeString(r.sourcePath().orElseThrow().resolve("gse-backup-checkpoint"),"changed source");
        assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),r,p,scratch,0));assertFalse(Files.exists(scratch));assertEquals(before,authority(p));
    }
    @Test void changedCodecWithTheSameDeclaredIdentityCannotBorrowAnEarlierPlan()throws Exception {
        for(int at:List.of(0,1)) {
            var f=fixture("codec-"+at,3,true);var helper=new V53BootstrapSeedTest();var changed=helper.replace(f.request(),at,V53BootstrapSeedTest.codec(()->{},true));
            var before=authority(f.plan());Path scratch=temp.resolve("codec-check-"+at);
            assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),changed,f.plan(),scratch,0));
            assertEquals(at>0,Files.exists(scratch));assertEquals(before,authority(f.plan()));
        }
    }

    @Test void sourceInodeReplacementDuringDecodeIsRefusedAndOriginalAuthorityIsUnchanged()throws Exception {
        var f=fixture("source-inode",3,true);Path source=f.request().sourcePath().orElseThrow().resolve("gse-backup-checkpoint");var changed=new java.util.concurrent.atomic.AtomicBoolean();
        var codec=V53BootstrapSeedTest.codec(()->{if(changed.compareAndSet(false,true))try{Path other=source.resolveSibling("replacement");Files.copy(source,other);Files.move(other,source,StandardCopyOption.REPLACE_EXISTING);}catch(IOException e){throw new java.io.UncheckedIOException(e);}},false);
        var helper=new V53BootstrapSeedTest();var r=helper.replace(f.request(),0,codec);var before=authority(f.plan());Path scratch=temp.resolve("inode-check");
        assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),r,f.plan(),scratch,0));
        assertTrue(changed.get());assertFalse(Files.exists(scratch));assertEquals(before,authority(f.plan()));
    }
    @Test void completeTransactionAndEveryScratchExportAreReservedBeforeWriting()throws Exception {
        var f=fixture("capacity",5,false);var p=f.plan();long completion=new MembershipBootstrapCommitData(p).completionBytes;
        long firstInvalid=f.request().maxOperationBytes()-completion-5L*MembershipApplicationImage.MAXIMUM+1;assertTrue(firstInvalid>0);
        for(long used:List.of(-1L,Long.MAX_VALUE,firstInvalid)) {
            Path scratch=temp.resolve("capacity-"+used);var before=authority(p);
            assertThrows(IllegalArgumentException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),p,scratch,used));assertFalse(Files.exists(scratch));assertEquals(before,authority(p));
        }
    }
    @Test void occupiedOrAliasedScratchAndCorePathsAreNeverModified()throws Exception {
        var f=fixture("paths",3,false);Path scratch=temp.resolve("occupied");Files.createDirectory(scratch);Files.writeString(scratch.resolve("keep"),"keep");
        for(Path path:List.of(scratch,f.plan().operation(),f.plan().operation().resolve("nested"),f.request().targets().getFirst().replicaDirectory())) {
            var before=authority(f.plan());assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),path,0));assertEquals(before,authority(f.plan()));
        }
        assertEquals("keep",Files.readString(scratch.resolve("keep")));Path core=f.request().targets().getFirst().materialization().directory();Files.createDirectory(core);Files.writeString(core.resolve("keep"),"keep");
        assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),temp.resolve("core-check"),0));assertFalse(Files.exists(temp.resolve("core-check")));assertEquals("keep",Files.readString(core.resolve("keep")));
    }
    @Test void realSourceFailureAtPreparedLeavesNoReceiptAndNoAuthorityRepair()throws Exception {
        var f=fixture("prepared-source-drift",3,true);var count=new AtomicInteger();Path base=f.plan().operation().getParent();var retained=new AtomicLong(bytes(base.resolve("scratch")));
        assertThrows(RuntimeException.class,()->MembershipBootstrapTransaction.apply(f.plan().summary(),false,()->{
            int n=count.incrementAndGet();if(n==2)Files.writeString(f.request().sourcePath().orElseThrow().resolve("gse-backup-checkpoint"),"invalid");
            retained.addAndGet(MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),base.resolve("validation-"+n),retained.get()));
        },e->{}));
        assertEquals(2,count.get());assertArrayEquals(new MembershipBootstrapCommitData(f.plan()).journal(2),Files.readAllBytes(f.plan().operation().resolve(MembershipBootstrapCommitData.JOURNAL)));
        assertFalse(Files.exists(f.plan().operation().resolve(MembershipBootstrapCommitData.RECEIPT)));assertFalse(Files.exists(base.resolve("validation-2")));
        var before=authority(f.plan());assertThrows(RuntimeException.class,()->MembershipBootstrapTransaction.apply(f.plan().summary(),true,()->
                MembershipBootstrapSeed.revalidate(builder().configuration(),f.request(),f.plan(),base.resolve("validation-resume"),retained.get()),e->{}));
        assertEquals(before,authority(f.plan()));assertFalse(Files.exists(base.resolve("validation-resume")));
    }
}
