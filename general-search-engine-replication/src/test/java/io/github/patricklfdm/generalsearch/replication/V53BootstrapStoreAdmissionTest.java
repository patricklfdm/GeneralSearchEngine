package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;

class V53BootstrapStoreAdmissionTest {
    @TempDir Path temp;
    static final String ADMISSION=MembershipBootstrapAdmissionData.FILE;
    static final List<String> IMMUTABLE=List.of(PREPARED,SEAL,ADMISSION);
    MembershipBootstrapPlanData fixture(String name,int size,boolean backup)throws Exception {
        var h=new V53BootstrapTransactionTest();h.temp=temp;var p=h.fixture(name,size,backup);
        V53BootstrapAdmissionFilesTest.run(p,false,e->{});return p;
    }
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static Path node(MembershipBootstrapPlanData p,int i){return p.summary().absentTargets().get(2*i);}
    static Path core(MembershipBootstrapPlanData p,int i){return p.summary().absentTargets().get(2*i+1);}
    static MembershipIdentity identity(MembershipBootstrapPlanData p,int i){return MembershipContext.identity(object(list(p.seed.rootRecord.value().get("initial")).get(i)));}
    static MembershipGrantJournal open(MembershipBootstrapPlanData p,int i,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openBootstrapped(node(p,i),core(p,i),p.seed.root,identity(p,i),r,
                (root,packet,images)->MembershipCapsule.verify(root,packet,images,Set.of()),MembershipGrantJournal.MAXIMUM,cut);
    }
    static byte[] counter(MembershipBootstrapPlanData p,int i,long value){return encode("records","ALLOCATOR",Map.of("root",p.seed.root.manifestDigest(),"node",identity(p,i).nodeId().value(),"counter",value));}
    static Map<String,String> originals(Path node)throws Exception {var out=new TreeMap<String,String>();for(String file:IMMUTABLE)out.put(file,hash(Files.readAllBytes(node.resolve(file))));return out;}
    static void rejected(MembershipBootstrapPlanData p,int i)throws Exception {
        var before=V53BootstrapTransactionTest.files(p);var r=resources();var trace=new ArrayList<String>();
        assertThrows(Exception.class,()->open(p,i,r,trace::add));assertTrue(trace.isEmpty(),trace.toString());
        assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapTransactionTest.files(p));
    }
    @Test void everyAdmittedInitialVoterPreservesItsOriginalReceiptAcrossActualGrantAndReopen()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-store-admission/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");var p=fixture(name,size,backup);Path member=Files.createDirectory(evidence.resolve(name));
            Files.write(member.resolve("original-plan.gsbp"),p.bytes());Files.write(member.resolve("original-application.image"),p.seed.application());
            V53BootstrapTransactionTest.copy(p,member.resolve("initial"));var calls=new ArrayList<Map<String,Object>>();
            for(int i=0;i<size;i++) {
                var r=resources();var immutable=originals(node(p,i));var events=new ArrayList<String>();String basis;
                var id=identity(p,i);var ballot=Map.<String,Object>of("counter",2L,"proposer",id.nodeId().value(),"incarnation",id.storageId().toString());
                try(var store=open(p,i,r,events::add)) {
                    assertTrue(store.originalBasis().isEmpty());assertEquals(1,r.usage().counts().get(MembershipResources.Unit.MISC));
                    assertEquals(2,store.reserveCounter());basis=store.prepareCurrent(ballot).digest();
                    assertEquals(basis,store.originalSource().basis.digest());
                }assertEquals(0,r.usage().leases());
                // A legitimate derived materialization may appear after offline bootstrap.
                Files.createDirectory(core(p,i));Files.writeString(core(p,i).resolve("derived-marker"),"retained");
                try(var store=open(p,i,r,events::add)) {
                    assertEquals(basis,store.originalBasis().orElseThrow().digest());assertEquals(basis,store.prepareCurrent(ballot).digest());
                    assertEquals(3,store.reserveCounter());assertEquals(1,r.usage().counts().get(MembershipResources.Unit.MISC));
                }
                assertEquals(0,r.usage().leases());assertEquals(immutable,originals(node(p,i)));
                assertEquals("retained",Files.readString(core(p,i).resolve("derived-marker")));
                calls.add(Map.of("node",id.nodeId().value(),"basis",basis,"events",events,"leasesAfterClose",0));
            }
            V53BootstrapTransactionTest.copy(p,member.resolve("final"));Files.write(member.resolve("calls.json"),canonical(calls,1024*1024));
            rows.add(Map.of("case",name,"targets",size,"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-store-admission-v1","status","PASS","cases",rows,"typedCoordinator",false,"publicRuntime",false),65536));
        System.out.println("v53BootstrapStoreAdmissionEvidence="+evidence.toAbsolutePath());
    }
    @Test void invalidAdmissionIsRefusedBeforeRecoveringAnUnreturnedCounter()throws Exception {
        var other=fixture("foreign",3,true);
        for(String file:IMMUTABLE)for(String change:List.of("missing","torn","corrupt","foreign","rehash")) {
            var p=fixture(file+"-"+change,3,false);Path target=node(p,0).resolve(file);
            Files.write(node(p,0).resolve(MembershipBallotAllocator.PENDING),counter(p,0,7));byte[] raw=Files.readAllBytes(target);
            switch(change) {
                case "missing"->Files.delete(target);
                case "torn"->Files.write(target,Arrays.copyOf(raw,raw.length/2));
                case "corrupt"->{raw[16]^=1;Files.write(target,raw);}
                case "foreign"->Files.copy(node(other,0).resolve(file),target,StandardCopyOption.REPLACE_EXISTING);
                case "rehash"->{
                    int kind=file.equals(PREPARED)?2:4;
                    if(file.equals(ADMISSION))Files.write(target,MembershipBootstrapAdmissionData.envelope(new MembershipBootstrapCommitData(other).receipt(),new MembershipBootstrapCommitData(p).row(3),new MembershipBootstrapCommitData(p).row(4)));
                    else {var value=new TreeMap<>(MembershipBootstrapAdmissionData.privateFrame(raw,kind));value.put("plan","a".repeat(64));Files.write(target,MembershipBootstrapCommitMetadata.container(kind,value));}
                }
            }
            rejected(p,0);assertArrayEquals(counter(p,0,1),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.CURRENT)));
            assertArrayEquals(counter(p,0,7),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.PENDING)));
        }
    }
    @Test void secondInterruptedCounterRecoveryKeepsAdmissionAndNeverReusesTheReservation()throws Exception {
        for(String point:List.of("RECOVERY_PENDING_FORCED","RECOVERY_RENAMED","RECOVERY_DIRECTORY_FORCED")) {
            var p=fixture("recovery-"+point,3,false);var original=originals(node(p,0));var r=resources();
            try(var store=open(p,0,r,e->{if(e.equals("ALLOCATOR_WRITTEN"))throw new IOException(e);})){assertThrows(IOException.class,store::reserveCounter);}
            assertEquals(0,r.usage().leases());assertThrows(IOException.class,()->open(p,0,r,e->{if(e.equals(point))throw new IOException(e);}));assertEquals(0,r.usage().leases());
            try(var store=open(p,0,r,e->{})){assertEquals(3,store.reserveCounter());}
            assertEquals(0,r.usage().leases());assertEquals(original,originals(node(p,0)));assertArrayEquals(counter(p,0,3),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.CURRENT)));
        }
    }
    @Test void activeOwnerRejectsImmutableBytesOrInodeReplacementBeforeAnotherWrite()throws Exception {
        for(String file:IMMUTABLE)for(boolean replace:List.of(false,true)) {
            var p=fixture("live-"+file+"-"+replace,3,false);var r=resources();Path path=node(p,0).resolve(file);
            try(var store=open(p,0,r,e->{})) {
                if(replace){Path next=path.resolveSibling("swap");Files.copy(path,next);Files.move(next,path,StandardCopyOption.REPLACE_EXISTING);}
                else {byte[] raw=Files.readAllBytes(path);raw[16]^=1;Files.write(path,raw);}
                assertThrows(Exception.class,store::reserveCounter);assertFalse(Files.exists(node(p,0).resolve(MembershipBallotAllocator.PENDING)));
                assertArrayEquals(counter(p,0,1),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.CURRENT)));
            }assertEquals(0,r.usage().leases());
        }
    }
    @Test void localPathsIdentityLinksAndUnsealedComponentStoresCannotBeAdmitted()throws Exception {
        var p=fixture("bindings",3,false);var r=resources();var before=V53BootstrapTransactionTest.files(p);
        assertThrows(Exception.class,()->MembershipGrantJournal.openBootstrapped(node(p,0),core(p,1),p.seed.root,identity(p,0),r,(a,b,c)->MembershipCapsule.verify(a,b,c,Set.of()),MembershipGrantJournal.MAXIMUM,e->{}));
        assertThrows(Exception.class,()->MembershipGrantJournal.openBootstrapped(node(p,0),core(p,0),p.seed.root,identity(p,1),r,(a,b,c)->MembershipCapsule.verify(a,b,c,Set.of()),MembershipGrantJournal.MAXIMUM,e->{}));
        assertEquals(before,V53BootstrapTransactionTest.files(p));assertEquals(0,r.usage().leases());
        for(String mode:List.of("symlink","hardlink","file","seal-candidate")) {
            var q=fixture(mode,3,false);Path path=node(q,0).resolve(ADMISSION);
            if(mode.equals("file"))Files.write(core(q,0),new byte[]{1});
            else if(mode.equals("seal-candidate"))Files.move(node(q,0).resolve(SEAL),node(q,0).resolve(SEAL_PENDING));
            else {Path saved=temp.resolve(mode+"-saved");Files.move(path,saved);if(mode.equals("symlink"))Files.createSymbolicLink(path,saved);else Files.createLink(path,saved);}
            // Linked authority is intentionally not read by the generic snapshot helper.
            assertThrows(Exception.class,()->open(q,0,r,e->{}));assertEquals(0,r.usage().leases());
            assertArrayEquals(counter(q,0,1),Files.readAllBytes(node(q,0).resolve(MembershipBallotAllocator.CURRENT)));
        }
        var helper=new V53BootstrapTransactionTest();helper.temp=temp;var old=helper.fixture("old",3,false);V53BootstrapTransactionTest.run(old,false,e->{});rejected(old,0);
    }
    @Test void exclusiveOwnershipAndFailedReservationReleaseEveryLease()throws Exception {
        var p=fixture("ownership",3,false);var r=resources();
        try(var store=open(p,0,r,e->{})) {
            assertThrows(ReplicationException.class,()->open(p,0,resources(),e->{}));assertEquals(2,store.reserveCounter());
            assertEquals(1,r.usage().counts().get(MembershipResources.Unit.MISC));
        }assertEquals(0,r.usage().leases());
        var small=new MembershipResources(1);assertThrows(Exception.class,()->open(p,0,small,e->{}));assertEquals(0,small.usage().leases());
        try(var store=open(p,0,r,e->{})){assertEquals(3,store.reserveCounter());}assertEquals(0,r.usage().leases());
    }
}
