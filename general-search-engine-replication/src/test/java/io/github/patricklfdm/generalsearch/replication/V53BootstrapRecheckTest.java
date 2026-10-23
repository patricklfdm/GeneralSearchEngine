package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapRecheckTest {
    @TempDir Path temp;
    V53BootstrapPlanTest.Fixture fixture(String name,int size,boolean backup)throws Exception {
        var helper=new V53BootstrapRevalidationTest();helper.temp=temp;return helper.fixture(name,size,backup);
    }
    static Map<String,Object> projection(Path path)throws IOException {
        var result=new TreeMap<String,Object>();result.put("",MembershipBasisSources.key(path));
        for(var member:AdmissionPaths.inventory(path,1L<<30))result.put(member.name(),List.of(member,MembershipBasisSources.key(path.resolve(member.name()))));
        return result;
    }
    @Test void repeatedRecoveryUsesOnlyOriginalProjectionAcrossEverySizeAndSource()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-recheck/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var f=fixture("cohort-"+size+"-"+backup,size,backup);var plan=f.plan();Path scratch=plan.operation().getParent().resolve("scratch");var before=projection(scratch);var count=new AtomicInteger();
            MembershipBootstrapTransaction.Recheck check=()-> {
                var authority=V53BootstrapRevalidationTest.authority(plan);
                assertEquals(V53BootstrapRevalidationTest.bytes(scratch),MembershipBootstrapRecheck.verify(builder().configuration(),f.request(),plan,scratch));
                assertEquals(before,projection(scratch));assertEquals(authority,V53BootstrapRevalidationTest.authority(plan));count.incrementAndGet();
            };
            assertThrows(IOException.class,()->MembershipBootstrapTransaction.apply(plan.summary(),false,check,e->{if(e.equals("BOOTSTRAP_PREPARED_DURABLE"))throw new IOException("cut");}));
            assertEquals(1,count.get());assertArrayEquals(new MembershipBootstrapCommitData(plan).journal(2),Files.readAllBytes(plan.operation().resolve(MembershipBootstrapCommitData.JOURNAL)));
            MembershipBootstrapTransaction.apply(plan.summary(),true,check,e->{});assertEquals(2,count.get());
            check.run();check.run();assertEquals(4,count.get());V53BootstrapTransactionTest.verify(plan);
            Path member=Files.createDirectory(evidence.resolve("size-"+size+"-"+(backup?"backup":"empty")));
            Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());
            V53JournalApplicationTest.copy(scratch,member.resolve("planning-scratch"));
            if(backup)V53JournalApplicationTest.copy(f.request().sourcePath().orElseThrow(),member.resolve("original-source"));
            Files.write(member.resolve("receipt.gsbp"),Files.readAllBytes(plan.operation().resolve(MembershipBootstrapCommitData.RECEIPT)));
            V53BootstrapTransactionTest.copy(plan,member.resolve("final"));
            rows.add(Map.of("case",member.getFileName().toString(),"size",size,"source",f.request().source().name(),"checks",count.get(),"plan",plan.digest(),"projectionBytes",V53BootstrapRevalidationTest.bytes(scratch),"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-recheck-v1","status","PASS","cases",rows,"publicBootstrap",false,"freshProcesses",false),65536));
        System.out.println("v53BootstrapRecheckEvidence="+evidence.toAbsolutePath());
    }
    @Test void missingChangedExtraAndLinkedProjectionNeverTriggerRepair()throws Exception {
        for(String kind:List.of("missing","changed","extra","directory","linked")) {
            var f=fixture(kind,3,true);Path scratch=f.plan().operation().getParent().resolve("scratch"),member=scratch.resolve("application-0/gse-backup-checkpoint");
            if(kind.equals("missing"))Files.delete(member);
            else if(kind.equals("changed"))Files.writeString(member,"changed");
            else if(kind.equals("extra"))Files.writeString(scratch.resolve("extra"),"extra");
            else if(kind.equals("directory"))Files.createDirectory(scratch.resolve("extra"));
            else {Path saved=temp.resolve("saved");Files.copy(member,saved);Files.delete(member);Files.createSymbolicLink(member,saved);}
            var authority=V53BootstrapRevalidationTest.authority(f.plan());
            assertThrows(RuntimeException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),f.request(),f.plan(),scratch));
            assertEquals(authority,V53BootstrapRevalidationTest.authority(f.plan()));
            if(kind.equals("missing"))assertFalse(Files.exists(member));
            if(kind.equals("linked"))assertTrue(Files.isSymbolicLink(member));
            if(kind.equals("changed"))assertEquals("changed",Files.readString(member));
        }
    }
    @Test void sameNamedCodecAndConfigurationOrSourceDriftAreRefused()throws Exception {
        var f=fixture("drift",3,true);Path scratch=f.plan().operation().getParent().resolve("scratch");var before=projection(scratch);var authority=V53BootstrapRevalidationTest.authority(f.plan());
        var helper=new V53BootstrapSeedTest();var r=helper.replace(f.request(),1,V53BootstrapSeedTest.codec(()->{},true));
        assertThrows(RuntimeException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),r,f.plan(),scratch));
        var wrong=io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class,ID).index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE)).configuration();
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapRecheck.verify(wrong,f.request(),f.plan(),scratch));
        Files.writeString(f.request().sourcePath().orElseThrow().resolve("gse-backup-checkpoint"),"changed");
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),f.request(),f.plan(),scratch));
        assertEquals(before,projection(scratch));assertEquals(authority,V53BootstrapRevalidationTest.authority(f.plan()));
    }
    @Test void byteIdenticalSourceOrProjectionReplacementDuringCodecIsRejected()throws Exception {
        for(boolean source:List.of(false,true)) {
            var f=fixture("replace-"+source,3,true);Path scratch=f.plan().operation().getParent().resolve("scratch");
            Path member=(source?f.request().sourcePath().orElseThrow():scratch.resolve("application-0")).resolve("gse-backup-checkpoint");
            var once=new AtomicBoolean();var codec=V53BootstrapSeedTest.codec(()->{if(once.compareAndSet(false,true))try{Path other=member.resolveSibling("replacement");Files.copy(member,other);Files.move(other,member,StandardCopyOption.REPLACE_EXISTING);}catch(IOException e){throw new java.io.UncheckedIOException(e);}},false);
            var helper=new V53BootstrapSeedTest();var r=helper.replace(f.request(),0,codec);var before=V53BootstrapRevalidationTest.authority(f.plan());
            var error=assertThrows(IllegalArgumentException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),r,f.plan(),scratch));
            assertTrue(error.getMessage().contains(source?"source changed":"projection changed"));assertTrue(once.get());assertEquals(before,V53BootstrapRevalidationTest.authority(f.plan()));
        }
    }
    @Test void exactRetainedProjectionBytesAreCountedWithFullCompletion()throws Exception {
        var f=fixture("capacity",5,true);Path scratch=f.plan().operation().getParent().resolve("scratch");var r=f.request();long bytes=V53BootstrapRevalidationTest.bytes(scratch);
        long maximum=new MembershipBootstrapCommitData(f.plan()).completionBytes+bytes;
        MembershipBootstrapRequest<Integer,Doc> limited=null;MembershipBootstrapPlanData plan=null;
        for(int n=0;n<4;n++) {
            limited=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),maximum);
            plan=MembershipBootstrapPlanData.create(f.plan().seed,limited);maximum=new MembershipBootstrapCommitData(plan).completionBytes+bytes;
        }
        assertEquals(bytes,MembershipBootstrapRecheck.verify(builder().configuration(),limited,plan,scratch));
        var tooSmall=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),maximum-1);
        var tooSmallPlan=MembershipBootstrapPlanData.create(f.plan().seed,tooSmall);var before=projection(scratch);
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),tooSmall,tooSmallPlan,scratch));assertEquals(before,projection(scratch));
    }
    @Test void aliasesAndOccupiedCorePathsRemainUntouched()throws Exception {
        var f=fixture("aliases",3,true);Path scratch=f.plan().operation().getParent().resolve("scratch");var before=projection(scratch);
        for(Path p:List.of(f.plan().operation(),f.request().sourcePath().orElseThrow(),f.request().targets().getFirst().replicaDirectory()))
            assertThrows(RuntimeException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),f.request(),f.plan(),p));
        Path core=f.request().targets().getFirst().materialization().directory();Files.createDirectory(core);Files.writeString(core.resolve("keep"),"keep");
        assertThrows(RuntimeException.class,()->MembershipBootstrapRecheck.verify(builder().configuration(),f.request(),f.plan(),scratch));
        assertEquals("keep",Files.readString(core.resolve("keep")));assertEquals(before,projection(scratch));
    }
}
