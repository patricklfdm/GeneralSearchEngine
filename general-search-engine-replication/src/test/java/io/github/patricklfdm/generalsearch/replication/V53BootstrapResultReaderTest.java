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

class V53BootstrapResultReaderTest {
    @TempDir Path temp;
    MembershipBootstrapPlanData fixture(String name,int size,boolean backup)throws Exception {
        var h=new V53BootstrapCoordinatorTest();h.temp=temp;var request=h.request(name,size,backup);
        var plan=MembershipBootstrapCoordinator.plan(builder().configuration(),request,e->{});
        MembershipBootstrapCoordinator.apply(builder().configuration(),request,plan,false,e->{});
        var original=V53BootstrapCoordinatorTest.original(plan.operationDirectory(),false);
        Files.move(MembershipBootstrapCoordinator.projection(plan.operationDirectory()),temp.resolve(name+"-saved-projection"));
        if(backup)Files.move(request.sourcePath().orElseThrow(),temp.resolve(name+"-saved-source"));
        return original;
    }
    static Map<String,Object> result(MembershipBootstrapResult r) {
        return Map.of("root",r.root().manifestDigest(),"history",r.root().historyId().toString(),"plan",r.planDigest(),"receipt",r.receiptDigest(),"sequence",r.applicationSequence(),"operation",r.operationDirectory().toString());
    }
    MembershipBootstrapResult read(MembershipBootstrapPlanData p)throws Exception {return MembershipBootstrapCoordinator.readResult(p.operation());}
    boolean publicBootstrap(){return false;}
    String evidenceName(){return publicBootstrap()?"public":"result-reader";}
    @Test void everySizeAndSourceRetainsTheOriginalResultAfterGrantsAndWhileReplicaLocksAreLive()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-"+evidenceName()+"/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");var p=fixture(name,size,backup);Path member=Files.createDirectory(evidence.resolve(name));
            var original=new MembershipBootstrapCommitData(p).result();assertEquals(original,read(p));
            Files.write(member.resolve("original-plan.gsbp"),p.bytes());Files.write(member.resolve("original-application.image"),p.seed.application());
            V53BootstrapTransactionTest.copy(p,member.resolve("initial"));var calls=new ArrayList<Map<String,Object>>();
            for(int i=0;i<size;i++) {
                var r=resources();var immutable=originals(node(p,i));var events=new ArrayList<String>();String basis;var id=identity(p,i);
                var ballot=Map.<String,Object>of("counter",2L,"proposer",id.nodeId().value(),"incarnation",id.storageId().toString());
                try(var store=open(p,i,r,events::add)) {
                    assertEquals(2,store.reserveCounter());basis=store.prepareCurrent(ballot).digest();assertEquals(original,read(p));
                    new V53MembershipOwnershipTest().probe(node(p,i).resolve("replica.lock"));
                }assertEquals(0,r.usage().leases());
                Files.createDirectory(core(p,i));Files.writeString(core(p,i).resolve("derived-marker"),"retained");
                try(var store=open(p,i,r,events::add)) {
                    assertEquals(basis,store.prepareCurrent(ballot).digest());assertEquals(3,store.reserveCounter());assertEquals(original,read(p));
                    new V53MembershipOwnershipTest().probe(node(p,i).resolve("replica.lock"));
                }
                assertEquals(0,r.usage().leases());assertEquals(immutable,originals(node(p,i)));
                calls.add(Map.of("node",id.nodeId().value(),"basis",basis,"events",events,"leasesAfterClose",0));
            }
            var before=V53BootstrapTransactionTest.files(p);assertEquals(original,read(p));assertEquals(before,V53BootstrapTransactionTest.files(p));
            assertThrows(Exception.class,()->MembershipBootstrapCoordinator.readInitialResult(p.operation()));assertEquals(before,V53BootstrapTransactionTest.files(p));
            V53BootstrapTransactionTest.copy(p,member.resolve("final"));Files.write(member.resolve("calls.json"),canonical(calls,1024*1024));Files.write(member.resolve("result.json"),canonical(result(read(p)),65536));
            rows.add(Map.of("case",name,"targets",size,"status","PASS"));
        }
        var receipt=new TreeMap<String,Object>(Map.of("schema",publicBootstrap()?"gse-v53-bootstrap-public-v1":"gse-v53-bootstrap-result-reader-v1","status","PASS","cases",rows,"typedCoordinator",true,"publicRuntime",false));
        if(publicBootstrap())receipt.put("publicBootstrap",true);
        Files.write(evidence.resolve("receipt.json"),canonical(receipt,65536));
        System.out.println((publicBootstrap()?"v53BootstrapPublicEvidence=":"v53BootstrapResultReaderEvidence=")+evidence.toAbsolutePath());
    }
    @Test void missingTornForeignOrPendingOriginalAuthorityCannotBeReconstructed()throws Exception {
        var p=fixture("refusal",3,true);var other=fixture("foreign",3,false);
        var paths=new ArrayList<Path>();for(String name:List.of(MembershipBootstrapPlanFiles.FILE,MembershipBootstrapPlanFiles.IMAGE,JOURNAL,RECEIPT))paths.add(p.operation().resolve(name));
        for(String name:List.of("root.gsr","genesis.gsr","node.gsr",PREPARED,SEAL,ADMISSION))paths.add(node(p,0).resolve(name));
        for(Path path:paths) {
            byte[] raw=Files.readAllBytes(path);Files.delete(path);var absent=V53BootstrapTransactionTest.files(p);assertThrows(Exception.class,()->read(p));assertEquals(absent,V53BootstrapTransactionTest.files(p));
            Files.write(path,Arrays.copyOf(raw,raw.length/2));var torn=V53BootstrapTransactionTest.files(p);assertThrows(Exception.class,()->read(p));assertEquals(torn,V53BootstrapTransactionTest.files(p));Files.write(path,raw);
        }
        Path receipt=p.operation().resolve(RECEIPT);byte[] original=Files.readAllBytes(receipt);Files.write(receipt,new MembershipBootstrapCommitData(other).receipt());var foreign=V53BootstrapTransactionTest.files(p);
        assertThrows(Exception.class,()->read(p));assertEquals(foreign,V53BootstrapTransactionTest.files(p));Files.write(receipt,original);
        for(Path pending:List.of(p.operation().resolve(PENDING),node(p,0).resolve(SEAL_PENDING))) {
            Files.write(pending,new byte[0]);var before=V53BootstrapTransactionTest.files(p);assertThrows(Exception.class,()->read(p));assertEquals(before,V53BootstrapTransactionTest.files(p));Files.delete(pending);
        }
        assertEquals(new MembershipBootstrapCommitData(p).result(),read(p));
    }
    @Test void readResultDoesNotClaimCurrentRuntimeIntegrityOrRepairLostMutableAuthority()throws Exception {
        var p=fixture("mutable",3,false);Files.delete(node(p,0).resolve(MembershipBallotAllocator.CURRENT));var before=V53BootstrapTransactionTest.files(p);
        assertEquals(new MembershipBootstrapCommitData(p).result(),read(p));assertEquals(before,V53BootstrapTransactionTest.files(p));
        var r=resources();assertThrows(Exception.class,()->open(p,0,r,e->{}));assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapTransactionTest.files(p));
    }
    @Test void postValidationReplacementAndNewPendingAuthorityAreRefusedWithoutRepair()throws Exception {
        for(String kind:List.of("receipt","admission","extra","pending-seal","core-file")) {
            var p=fixture("race-"+kind,3,false);
            assertThrows(Exception.class,()->MembershipBootstrapResultReader.read(p.operation(),e->{
                if(kind.equals("receipt") || kind.equals("admission")) {
                    Path file=kind.equals("receipt")?p.operation().resolve(RECEIPT):node(p,0).resolve(ADMISSION),next=file.resolveSibling("replacement");
                    Files.copy(file,next);Files.move(next,file,StandardCopyOption.REPLACE_EXISTING);
                }else Files.write(kind.equals("extra")?p.operation().resolve("extra"):kind.equals("pending-seal")?node(p,0).resolve(SEAL_PENDING):core(p,0),new byte[0]);
            }));
            assertArrayEquals(counter(p,0,1),Files.readAllBytes(node(p,0).resolve(MembershipBallotAllocator.CURRENT)));
        }
    }
    @Test void ownedOperationAndLinkedOriginalsAreRefusedWithoutReleasingAnotherOwner()throws Exception {
        var p=fixture("owner",3,false);Path lock=p.operation().resolve(MembershipBootstrapPlanFiles.LOCK);
        try(var owner=MembershipOwnership.own(lock,false)) {assertThrows(ReplicationException.class,()->read(p));new V53MembershipOwnershipTest().probe(lock);}
        Path seal=node(p,0).resolve(SEAL),saved=temp.resolve("saved-seal");Files.move(seal,saved);Files.createSymbolicLink(seal,saved);assertThrows(Exception.class,()->read(p));Files.delete(seal);Files.createLink(seal,saved);assertThrows(Exception.class,()->read(p));
    }
}
