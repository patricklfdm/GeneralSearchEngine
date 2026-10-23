package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;
import static io.github.patricklfdm.generalsearch.replication.V53BootstrapStoreAdmissionTest.*;

class V53BootstrapProgressResumeTest {
    @TempDir Path temp;
    record Fixture(MembershipBootstrapRequest<Integer,Doc> request,MembershipBootstrapPlanData plan,List<String> events){}
    Fixture fixture(String name,int size,boolean backup)throws Exception {
        var h=new V53BootstrapCoordinatorTest();h.temp=temp;var request=h.request(name,size,backup);
        var reviewed=MembershipBootstrapCoordinator.plan(builder().configuration(),request,e->{});var events=new ArrayList<String>();
        assertThrows(IOException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),request,reviewed,false,e->{events.add(e);if(e.equals("BOOTSTRAP_SEAL_0_ACTIVE_PARENT_FORCED"))throw new IOException(e);}));
        var p=V53BootstrapCoordinatorTest.original(reviewed.operationDirectory(),false);
        Files.move(MembershipBootstrapCoordinator.projection(p.operation()),temp.resolve(name+"-saved-projection"));
        if(backup)Files.move(request.sourcePath().orElseThrow(),temp.resolve(name+"-saved-source"));
        return new Fixture(request,p,List.copyOf(events));
    }
    static MembershipBootstrapResult resume(Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipBootstrapCoordinator.apply(builder().configuration(),f.request(),f.plan().summary(),true,cut);
    }
    static Map<String,String> safeFiles(Path root)throws IOException {
        var out=new TreeMap<String,String>();try(var paths=Files.walk(root)) {for(Path file:paths.filter(Files::isRegularFile).toList()) {
            byte[] raw;if(file.getFileName().toString().endsWith(".lock")){assertEquals(0,Files.size(file));raw=new byte[0];}else raw=Files.readAllBytes(file);
            out.put(root.relativize(file).toString(),hash(raw));
        }}return out;
    }
    static void copy(MembershipBootstrapPlanData plan,Path dest)throws IOException {
        Files.createDirectories(dest);var roots=new LinkedHashMap<Path,String>();roots.put(plan.operation(),"operation");int n=0;for(Path path:plan.summary().absentTargets())roots.put(path,"target-"+n++);
        for(var entry:roots.entrySet())if(Files.exists(entry.getKey()))try(var stream=Files.walk(entry.getKey())) {for(Path path:stream.sorted().toList()) {
            Path to=dest.resolve(entry.getValue()).resolve(entry.getKey().relativize(path));
            if(Files.isDirectory(path))Files.createDirectories(to);
            else if(path.getFileName().toString().endsWith(".lock")){assertEquals(0,Files.size(path));Files.write(to,new byte[0]);}
            else Files.copy(path,to);
        }}
    }
    static void noCompletedWrites(List<String> events) {
        for(String event:events)assertFalse(event.startsWith("BOOTSTRAP_TARGET_0_") || event.equals("BOOTSTRAP_OWNED_0") || event.startsWith("BOOTSTRAP_DIRECTORY_0_")
                || event.startsWith("BOOTSTRAP_RESEAL_0_") || event.startsWith("BOOTSTRAP_PREPARATION_RESEAL_0") || event.startsWith("BOOTSTRAP_ADMISSION_0_")
                || event.startsWith("BOOTSTRAP_SEAL_0_"),event);
        assertFalse(events.contains("BOOTSTRAP_TYPED_RECHECKED"));
    }
    @Test void remainingSealsCompleteAroundARealLiveInitialVoterAfterRecoveryIsInterruptedAgain()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-progress-resume/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");var f=fixture(name,size,backup);var p=f.plan();Path member=Files.createDirectory(evidence.resolve(name));
            Files.write(member.resolve("original-plan.gsbp"),p.bytes());Files.write(member.resolve("original-application.image"),p.seed.application());copy(p,member.resolve("initial"));
            var r=resources();var storeEvents=new ArrayList<String>();var second=new ArrayList<String>();var last=new ArrayList<String>();var id=identity(p,0);
            try(var store=open(p,0,r,storeEvents::add)) {
                assertEquals(2,store.reserveCounter());store.prepareCurrent(Map.of("counter",2L,"proposer",id.nodeId().value(),"incarnation",id.storageId().toString()));
                Files.createDirectory(core(p,0));Files.writeString(core(p,0).resolve("derived-marker"),"retained");assertEquals(3,store.reserveCounter());
                var before=safeFiles(node(p,0));copy(p,member.resolve("before"));
                assertThrows(IOException.class,()->resume(f,e->{second.add(e);if(e.equals("BOOTSTRAP_SEAL_1_CANDIDATE_PREFIX_WRITTEN"))throw new IOException(e);}));
                noCompletedWrites(second);assertEquals(before,safeFiles(node(p,0)));copy(p,member.resolve("second-crash"));new V53MembershipOwnershipTest().probe(node(p,0).resolve("replica.lock"));
                var result=resume(f,last::add);noCompletedWrites(last);assertEquals(before,safeFiles(node(p,0)));assertEquals(result,MembershipBootstrapCoordinator.readResult(p.operation()));
                assertEquals(result,resume(f,e->{assertFalse(e.startsWith("BOOTSTRAP_OWNED_"));assertFalse(e.startsWith("BOOTSTRAP_RESEAL_"));}));
                new V53MembershipOwnershipTest().probe(node(p,0).resolve("replica.lock"));assertEquals(4,store.reserveCounter());
                Files.write(member.resolve("result.json"),canonical(V53BootstrapResultReaderTest.result(result),65536));
            }
            assertEquals(0,r.usage().leases());copy(p,member.resolve("final"));
            Files.write(member.resolve("events.json"),canonical(Map.of("first",f.events(),"second",second,"resumed",last,"store",storeEvents),1024*1024));rows.add(Map.of("case",name,"targets",size,"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-progress-resume-v1","status","PASS","cases",rows,"typedCoordinator",true,"freshProcesses",false,"publicRuntime",false),65536));
        System.out.println("v53BootstrapProgressResumeEvidence="+evidence.toAbsolutePath());
    }
    @Test void lostSealOrUnsealedMutationNeverResetsProgressToGenesis()throws Exception {
        for(boolean completed:List.of(false,true)) {
            var f=fixture("lost-"+completed,3,false);var p=f.plan();int at=completed?0:1;
            if(completed){var r=resources();try(var store=open(p,0,r,e->{})){assertEquals(2,store.reserveCounter());}Files.delete(node(p,0).resolve(SEAL));}
            else Files.write(node(p,1).resolve(MembershipBallotAllocator.CURRENT),counter(p,1,2));
            var before=V53BootstrapRevalidationTest.authority(p);var events=new ArrayList<String>();assertThrows(Exception.class,()->resume(f,events::add));assertTrue(events.isEmpty());assertEquals(before,V53BootstrapRevalidationTest.authority(p));
        }
    }
    @Test void noMissingOrAlteredAdmissionCanBeRecreatedOnEitherCompletedOrPendingTargets()throws Exception {
        var f=fixture("missing",3,false);var p=f.plan();var r=resources();
        try(var store=open(p,0,r,e->{})) {
            for(int at:List.of(0,2))for(String name:List.of(PREPARED,ADMISSION,"root.gsr")) {
                Path path=node(p,at).resolve(name);byte[] raw=Files.readAllBytes(path);Files.write(path,Arrays.copyOf(raw,raw.length/2));var before=V53BootstrapRevalidationTest.authority(p);
                assertThrows(Exception.class,()->resume(f,e->{}));assertEquals(before,V53BootstrapRevalidationTest.authority(p));Files.write(path,raw);
            }
            // Restoring the same inode after intentional test corruption leaves the owner usable.
            new V53MembershipOwnershipTest().probe(node(p,0).resolve("replica.lock"));assertEquals(2,store.reserveCounter());
        }
    }
    @Test void aPendingTargetStillRequiresExclusiveOwnership()throws Exception {
        var f=fixture("pending-owner",3,false);var p=f.plan();
        try(var owner=MembershipOwnership.own(node(p,1).resolve("replica.lock"),false)) {
            var before=V53BootstrapRevalidationTest.authority(p);assertThrows(ReplicationException.class,()->resume(f,e->{}));assertEquals(before,V53BootstrapRevalidationTest.authority(p));
            new V53MembershipOwnershipTest().probe(node(p,1).resolve("replica.lock"));
        }
        assertEquals(new MembershipBootstrapCommitData(p).result(),resume(f,e->{}));
    }
    @Test void completedMetadataReplacementDuringResumeRefusesWithoutChangingTheRunningCounter()throws Exception {
        var f=fixture("replacement",3,false);var p=f.plan();var r=resources();
        try(var store=open(p,0,r,e->{})) {
            assertEquals(2,store.reserveCounter());
            assertThrows(Exception.class,()->resume(f,e->{if(e.equals("BOOTSTRAP_OWNED_1")) {
                Path admission=node(p,0).resolve(ADMISSION),copy=admission.resolveSibling("replacement");Files.copy(admission,copy);Files.move(copy,admission,StandardCopyOption.REPLACE_EXISTING);
            }}));
            assertArrayEquals(counter(p,0,2),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.CURRENT)));new V53MembershipOwnershipTest().probe(node(p,0).resolve("replica.lock"));
            assertThrows(Exception.class,store::reserveCounter);
        }assertEquals(0,r.usage().leases());
    }
}
