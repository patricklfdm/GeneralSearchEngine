package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;

class V53BootstrapAdmissionFilesTest {
    @TempDir Path temp;
    static final String ADMISSION=MembershipBootstrapAdmissionData.FILE;
    MembershipBootstrapPlanData fixture(String name,int size,boolean backup)throws Exception {var h=new V53BootstrapTransactionTest();h.temp=temp;return h.fixture(name,size,backup);}
    static MembershipBootstrapResult run(MembershipBootstrapPlanData p,boolean resume,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipBootstrapTransaction.applyAdmitted(p.summary(),resume,x->{},x->{},cut);
    }
    static void verify(MembershipBootstrapPlanData p)throws Exception {
        var d=new MembershipBootstrapCommitData(p);byte[] raw=MembershipBootstrapAdmissionData.create(d.metadata);
        assertEquals(d.result(),MembershipBootstrapTransaction.readAdmitted(p.summary()));
        assertArrayEquals(d.journal(4),Files.readAllBytes(p.operation().resolve(JOURNAL)));assertArrayEquals(d.receipt(),Files.readAllBytes(p.operation().resolve(RECEIPT)));
        for(int i=0;i<d.targets.size();i++) {
            var expected=new TreeMap<>(d.payload(i));expected.put(PREPARED,d.preparation(i));expected.put(SEAL,d.seal(i));expected.put(ADMISSION,raw);
            assertEquals(V53BootstrapPlanTest.hashes(expected),V53ReplayFilesTest.files(d.targets.get(i)));
            assertEquals(d.result(),V53BootstrapAdmissionDataTest.inspect(Files.readAllBytes(d.targets.get(i).resolve(ADMISSION)),d.metadata,i,d.preparation(i),d.seal(i)).result());
        }
    }
    @Test void everyAdmissionIsDurableBeforeAnyLocalSealForEverySizeAndSource()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var p=fixture("all-"+size+"-"+backup,size,backup);var events=new ArrayList<String>();run(p,false,events::add);verify(p);
            for(int i=0;i<size;i++) {
                assertTrue(events.indexOf("BOOTSTRAP_COMMITTED_DURABLE")<events.indexOf("BOOTSTRAP_ADMISSION_"+i+"_CREATED"));
                assertTrue(events.indexOf("BOOTSTRAP_ADMISSION_"+i+"_FORCED")<events.indexOf("BOOTSTRAP_ADMISSION_"+i+"_PARENT_FORCED"));
                assertTrue(events.indexOf("BOOTSTRAP_ADMISSION_"+i+"_PARENT_FORCED")<events.indexOf("BOOTSTRAP_SEAL_0_CANDIDATE_CREATED"));
            }
            var before=V53BootstrapTransactionTest.files(p);run(p,true,e->{});assertEquals(before,V53BootstrapTransactionTest.files(p));
            assertThrows(RuntimeException.class,()->MembershipBootstrapTransaction.read(p.summary()));assertEquals(before,V53BootstrapTransactionTest.files(p));
        }
    }
    static boolean selected(String e){return e.startsWith("BOOTSTRAP_ADMISSION_0_") || e.startsWith("BOOTSTRAP_ADMISSION_2_") || e.startsWith("BOOTSTRAP_SEAL_0_") || Set.of("BOOTSTRAP_COMMITTED_PREFIX_WRITTEN","BOOTSTRAP_COMMITTED_DURABLE","BOOTSTRAP_COMMITTED_BEFORE_RETURN").contains(e);}
    @Test void admissionAndSealCutsResumeAfterAnotherInterruptedAdmissionForce()throws Exception {
        var base=fixture("cuts",3,false);var events=new ArrayList<String>();run(base,false,events::add);var points=events.stream().filter(V53BootstrapAdmissionFilesTest::selected).distinct().toList();
        Path evidence=Path.of("target/v53-bootstrap-admission-files/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int i=0;i<points.size();i++) {
            String stop=points.get(i);var p=fixture("cut-"+i,3,false);Path member=Files.createDirectory(evidence.resolve(String.format("case-%03d",i)));
            Files.write(member.resolve("original-plan.gsbp"),p.bytes());Files.write(member.resolve("original-application.image"),p.seed.application());
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resumed=new ArrayList<String>();
            assertThrows(IOException.class,()->run(p,false,e->{first.add(e);if(e.equals(stop))throw new IOException(e);}));V53BootstrapTransactionTest.copy(p,member.resolve("crash"));
            assertThrows(IOException.class,()->run(p,true,e->{second.add(e);if(e.equals("BOOTSTRAP_ADMISSION_0_FORCED"))throw new IOException(e);}));V53BootstrapTransactionTest.copy(p,member.resolve("second-crash"));
            run(p,true,resumed::add);verify(p);V53BootstrapTransactionTest.copy(p,member.resolve("final"));
            Files.write(member.resolve("events.json"),canonical(Map.of("first",first,"second",second,"resumed",resumed),1024*1024));rows.add(Map.of("case",member.getFileName().toString(),"cut",stop,"plan",p.digest(),"status","PASS"));
            if((i+1)%5==0)System.out.println("v53BootstrapAdmissionFilesProgress="+(i+1)+"/"+points.size());
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-admission-files-v1","status","PASS","cases",rows,"freshProcesses",false,"typedCoordinator",false,"publicBootstrap",false),65536));
        System.out.println("v53BootstrapAdmissionFilesEvidence="+evidence.toAbsolutePath());
    }
    @Test void missingOrPartialAdmissionAfterAnySealCannotBeRecreatedOnAnyTarget()throws Exception {
        for(String cut:List.of("BOOTSTRAP_SEAL_0_CANDIDATE_CREATED","BOOTSTRAP_SEAL_0_RENAMED","BOOTSTRAP_COMMITTED_BEFORE_RETURN"))for(int target:List.of(0,2))for(boolean missing:List.of(false,true)) {
            var p=fixture("lost-"+cut+"-"+target+"-"+missing,3,false);
            assertThrows(IOException.class,()->run(p,false,e->{if(e.equals(cut))throw new IOException(e);}));Path path=p.summary().absentTargets().get(2*target).resolve(ADMISSION);
            if(missing)Files.delete(path);else {byte[] raw=Files.readAllBytes(path);Files.write(path,Arrays.copyOf(raw,raw.length/2));}
            var before=V53BootstrapTransactionTest.files(p);assertThrows(Exception.class,()->run(p,true,e->{}));assertEquals(before,V53BootstrapTransactionTest.files(p));
            assertThrows(Exception.class,()->MembershipBootstrapTransaction.readAdmitted(p.summary()));assertEquals(before,V53BootstrapTransactionTest.files(p));
        }
    }
    @Test void earlyOrForeignAdmissionAndOldSealedStoresAreNeverUpgraded()throws Exception {
        var other=fixture("other-history",3,true);
        for(String kind:List.of("early","corrupt","foreign","legacy")) {
            var p=fixture(kind,3,false);var d=new MembershipBootstrapCommitData(p);Path path=d.targets.getFirst().resolve(ADMISSION);
            if(kind.equals("legacy"))V53BootstrapTransactionTest.run(p,false,e->{});
            else {
                String cut=kind.equals("early")?"BOOTSTRAP_PREPARED_DURABLE":"BOOTSTRAP_ADMISSION_0_PARENT_FORCED";
                assertThrows(IOException.class,()->run(p,false,e->{if(e.equals(cut))throw new IOException(e);}));
                Files.write(path,kind.equals("early")?MembershipBootstrapAdmissionData.create(d.metadata):kind.equals("corrupt")?new byte[]{1}:MembershipBootstrapAdmissionData.create(new MembershipBootstrapCommitData(other).metadata));
            }
            var before=V53BootstrapTransactionTest.files(p);assertThrows(Exception.class,()->run(p,true,e->{}));assertEquals(before,V53BootstrapTransactionTest.files(p));
        }
    }
    @Test void completionBudgetCountsEveryAdmissionBeforeStartingTheTransaction()throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;var original=helper.fixture("capacity",5,true).plan();var body=V53BootstrapPlanTest.body(original.bytes());var data=new MembershipBootstrapCommitData(original);
        long wanted=MembershipBootstrapAdmissionData.completionBytes(data.metadata);
        MembershipBootstrapPlanData p=original;
        for(int i=0;i<3;i++){body.put("maximumOperation",wanted);p=MembershipBootstrapPlanData.decode(MembershipBootstrapPlanData.encode(body),original.seed.application());wanted=MembershipBootstrapAdmissionData.completionBytes(new MembershipBootstrapCommitData(p).metadata);}
        body.put("maximumOperation",wanted-1);var small=MembershipBootstrapPlanData.decode(MembershipBootstrapPlanData.encode(body),original.seed.application());
        assertTrue(new MembershipBootstrapCommitData(small).completionBytes<small.maximumOperation);
        try(var owner=MembershipBootstrapPlanFiles.create(small,e->{})){assertEquals(small.summary(),owner.summary());}
        var before=V53BootstrapTransactionTest.files(small);assertThrows(RuntimeException.class,()->run(small,false,e->{}));assertEquals(before,V53BootstrapTransactionTest.files(small));
        assertFalse(Files.exists(small.operation().resolve(JOURNAL)));for(Path target:small.summary().absentTargets())assertFalse(Files.exists(target));
    }
    @Test void admissionInodeChangesInvalidateOwnershipInsteadOfBeingSilentlyResealed()throws Exception {
        for(String cut:List.of("BOOTSTRAP_ADMISSION_0_WRITTEN","BOOTSTRAP_ADMISSION_0_FORCED","BOOTSTRAP_SEAL_0_ACTIVE_FORCED")) {
            var p=fixture("identity-"+cut,3,false);Path target=p.summary().absentTargets().getFirst().resolve(ADMISSION);
            assertThrows(IllegalArgumentException.class,()->run(p,false,e->{if(e.equals(cut)) {
                Path replacement=target.resolveSibling("replacement");Files.copy(target,replacement);Files.move(replacement,target,StandardCopyOption.REPLACE_EXISTING);
            }}));
        }
    }
}
