package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53PendingProofTest {
    @TempDir Path temp;
    static final List<String> CUTS=V53PendingAcceptTest.CUTS.stream().map(s->s.replace("ACCEPT","PROOF")).toList();
    final V53PendingProofFixture f=new V53PendingProofFixture(3,0);
    Map<String,String> files(Path path)throws Exception{return new V53CaptureRecoveryTest().files(path);}
    Set<Owned> setup(Path path)throws Exception{f.provision(path);f.install(path);return f.accept(path);}
    @Test void actualThreeFourFiveVoterQuorumsForceReopenAndCaptureStableJointAndNewStableProof()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7)) {
            var fixture=new V53PendingProofFixture(size,through);Path root=temp.resolve(size+"-"+through);
            fixture.provision(root);fixture.install(root);var accepts=fixture.accept(root);var proof=fixture.proof(accepts);var r=fixture.resources();
            for(int node:fixture.nodes) {
                try(var store=fixture.open(root,node,r,e->{})) {
                    var actual=store.proveCurrent(proof,accepts);assertEquals(proof.digest(),actual.record());
                    var bytes=Files.readAllBytes(fixture.node(root,node).resolve(MembershipPendingAccept.FILE));
                    assertEquals(actual,store.proveCurrent(proof,Set.of()));store.acceptCurrent(fixture.entry(),fixture.payload());
                    assertArrayEquals(bytes,Files.readAllBytes(fixture.node(root,node).resolve(MembershipPendingAccept.FILE)));
                }
                assertEquals(0,r.usage().leases());
                try(var store=fixture.open(root,node,r,e->{})) {
                    assertEquals(proof.digest(),store.currentOwnedProof().orElseThrow().record());
                    store.prepareCurrent(fixture.f.fixture.source.ballot(21));
                    assertArrayEquals(proof.bytes(),store.originalSource().capsule.packet.objectBytes(proof.digest()));
                    assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,accepts));
                }
                assertEquals(0,r.usage().leases());
            }
        }
    }
    @Test void receiptsAloneWrongOwnersWrongParentAndNoActualLocalAcceptCannotForceProof()throws Exception {
        Path root=temp.resolve("quorum");var accepts=setup(root);var proof=f.proof(accepts);
        try(var store=f.open(root,1,f.resources(),e->{})) {
            var before=files(root);
            assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,Set.of()));
            for(String field:List.of("record","parent","storage")) {
                var wrong=new HashSet<Owned>();for(var a:accepts)wrong.add(new Owned(a.voter(),field.equals("storage")?new UUID(0,99):a.storage(),field.equals("record")?"00".repeat(32):a.record(),field.equals("parent")?"00".repeat(32):a.parent()));
                assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,wrong));
            }
            var onlyTwo=accepts.stream().filter(o->!o.voter().equals("node-3")).collect(java.util.stream.Collectors.toSet());
            assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,onlyTwo));
            assertEquals(before,files(root));assertTrue(store.currentOwnedProof().isEmpty());
            store.proveCurrent(f.proof(onlyTwo),onlyTwo);
        }
        Path empty=temp.resolve("empty");f.provision(empty);f.install(empty);
        try(var store=f.open(empty,1,f.resources(),e->{})){assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,accepts));}
    }
    @Test void malformedPhasesParentsBallotsAndAlternateSameBallotProofCannotReplaceOriginal()throws Exception {
        Path root=temp.resolve("invalid");var accepts=setup(root);var proof=f.proof(accepts);
        try(var store=f.open(root,1,f.resources(),e->{})) {
            for(String field:List.of("root","authority","ballot","entry","index","accepts")) {
                var wrong=new TreeMap<>(proof.value());wrong.put(field,switch(field){case "ballot"->f.f.fixture.source.ballot(21);case "index"->2L;case "accepts"->{var rows=new ArrayList<Object>(list(proof.value().get("accepts")));var row=new TreeMap<>(object(rows.getFirst()));row.put("receipt","00".repeat(32));rows.set(0,row);yield rows;}default->"00".repeat(32);});
                var altered=decode(encode("records","PROOF",wrong),"records","PROOF");var before=files(root);
                assertThrows(IllegalArgumentException.class,()->store.proveCurrent(altered,accepts));assertEquals(before,files(root));
            }
            store.proveCurrent(proof,accepts);var before=files(root);
            var two=accepts.stream().filter(o->!o.voter().equals("node-3")).collect(java.util.stream.Collectors.toSet());
            assertThrows(IllegalArgumentException.class,()->store.proveCurrent(f.proof(two),two));assertEquals(before,files(root));
        }
    }
    @Test void everyInterruptedProofResumesExactRequestAndPartialCannotBeOverwrittenByAccept()throws Exception {
        for(String point:CUTS) {
            Path root=temp.resolve(point);var accepts=setup(root);var proof=f.proof(accepts);var r=f.resources();
            try(var store=f.open(root,1,r,e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.proveCurrent(proof,accepts));}
            assertEquals(0,r.usage().leases());
            try(var store=f.open(root,1,r,e->{})) {
                if(Files.exists(f.node(root,1).resolve(MembershipPendingAccept.NEXT))) {
                    assertThrows(IllegalArgumentException.class,store::currentOwnedProof);
                    var before=files(root);assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(f.entry(),f.payload()));assertEquals(before,files(root));
                    assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,Set.of()));
                }
                assertEquals(proof.digest(),store.proveCurrent(proof,accepts).record());
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void repeatedRecoveryAndHigherObservationAtEveryForceBoundaryNeverReturnOldSuccess()throws Exception {
        for(String point:List.of("PROOF_RECOVERY_VALIDATED","PROOF_PREFIX_WRITTEN","PROOF_CANDIDATE_FORCED","PROOF_RENAMED","PROOF_PARENT_FORCED","PROOF_ACTIVE_FORCED","PROOF_ACTIVE_PARENT_FORCED")) {
            Path root=temp.resolve(point);var accepts=setup(root);var proof=f.proof(accepts);var r=f.resources();
            try(var store=f.open(root,1,r,e->{if(e.equals("PROOF_CANDIDATE_WRITTEN"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.proveCurrent(proof,accepts));}
            assertThrows(IOException.class,()->f.open(root,1,r,e->{if(e.equals(point))throw new IOException("again");}));assertEquals(0,r.usage().leases());
            try(var store=f.open(root,1,r,e->{})){assertEquals(proof.digest(),store.currentOwnedProof().orElseThrow().record());}
        }
        for(String point:CUTS) {
            Path root=temp.resolve("fence-"+point);var accepts=setup(root);var proof=f.proof(accepts);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(root,1,f.resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,accepts));
            }
        }
    }
    @Test void corruptProofAndSameByteInodeReplacementFailClosed()throws Exception {
        for(String point:List.of("PROOF_CANDIDATE_FORCED","PROOF_RENAMED","PROOF_BEFORE_RETURN")) {
            Path root=temp.resolve(point);var accepts=setup(root);var proof=f.proof(accepts);
            try(var store=f.open(root,1,f.resources(),e->{if(e.equals(point)) {
                Path path=f.node(root,1).resolve(point.equals("PROOF_CANDIDATE_FORCED")?MembershipPendingAccept.NEXT:MembershipPendingAccept.FILE);
                Path copy=path.resolveSibling("copy");Files.write(copy,Files.readAllBytes(path));Files.move(copy,path,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,()->store.proveCurrent(proof,accepts));}
        }
        Path root=temp.resolve("corrupt");var accepts=setup(root);var proof=f.proof(accepts);
        try(var store=f.open(root,1,f.resources(),e->{})){store.proveCurrent(proof,accepts);}
        Path path=f.node(root,1).resolve(MembershipPendingAccept.FILE);byte[] bytes=Files.readAllBytes(path);bytes[bytes.length-1]^=1;Files.write(path,bytes);
        var before=files(root);assertThrows(IllegalArgumentException.class,()->f.open(root,1,f.resources(),e->{}));assertEquals(before,files(root));
    }
    @Test void everyActualSubsetMustCoverBothOldAndNewMajorities()throws Exception {
        for(int size:List.of(3,4,5)) {
            var fixture=new V53PendingProofFixture(size,6);Path root=temp.resolve("subsets-"+size);
            fixture.provision(root);fixture.install(root);var actual=fixture.accept(root);var all=actual.stream().sorted(Comparator.comparing(Owned::voter)).toList();
            var context=fixture.f.admitted.context;var accepted=MembershipPendingAccept.decode(Files.readAllBytes(fixture.node(root,1).resolve(MembershipPendingAccept.FILE))).accept();
            for(int mask=0;mask<(1<<all.size());mask++) {
                var subset=new HashSet<Owned>();for(int i=0;i<all.size();i++)if((mask&(1<<i))!=0)subset.add(all.get(i));
                if(subset.size()<2)continue;
                var nodes=subset.stream().map(Owned::voter).collect(java.util.stream.Collectors.toSet());
                boolean quorum=true;for(String side:List.of("old","new")){var members=MembershipContext.nodes(context.view,side);quorum&=nodes.stream().filter(members::contains).count()>members.size()/2;}
                var proof=fixture.proof(subset);
                if(quorum)context.proof(proof,accepted,subset);
                else assertThrows(IllegalArgumentException.class,()->context.proof(proof,accepted,subset));
            }
        }
    }
    @Test void AcceptReservesProofReplacementBeforeAcknowledgingAndProofCandidateCannotInventLocalAccept()throws Exception {
        Path root=temp.resolve("headroom");f.provision(root);f.install(root);Path path=f.node(root,1);
        var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");Path generation=path.resolve("generations/b");
        var promise=decode(Files.readAllBytes(generation.resolve("promise.gsr")),"records","PROMISE");
        var selected=decode(Files.readAllBytes(generation.resolve("selected.gsr")),"records","SELECTED");
        var value=Map.<String,Object>of("root",f.f.root().manifestDigest(),"authority",f.f.admitted.context.authority(),
                "ballot",f.f.fixture.source.ballot(20),"entry",f.entry().digest(),"index",f.entry().value().get("index"));
        var accepted=decode(encode("records","ACCEPT",value),"records","ACCEPT");
        var vote=new MembershipPendingAccept.Vote(selector,promise,selected,f.entry(),accepted,f.payload());
        int maximum=Math.toIntExact(Files.size(path.resolve("grants.gsr")))+12+vote.bytes().length+8192+16384;
        var before=files(root);var r=f.resources();
        try(var store=MembershipGrantJournal.openVoting(path,f.f.root(),V53DeclarationsTest.node(1),r,f.f::verify,maximum,e->{})) {
            assertThrows(MembershipOperationException.class,()->store.acceptCurrent(f.entry(),f.payload()));assertEquals(before,files(root));
        }
        assertEquals(0,r.usage().leases());
        var actual=f.accept(root);var proof=f.proof(actual);
        // Deliberately corrupt a closed owner's fixture: a proof candidate cannot substitute
        // for the missing active ACCEPT even if its receipt structure is otherwise valid.
        Files.write(path.resolve(MembershipPendingAccept.NEXT),vote.withProof(proof).bytes());Files.write(path.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());
        before=files(root);assertThrows(IllegalArgumentException.class,()->f.open(root,1,r,e->{}));assertEquals(before,files(root));assertEquals(0,r.usage().leases());
    }

    @Test void higherBallotReacceptRetainsOldProofInOriginalFrozenSource()throws Exception {
        Path root=temp.resolve("reaccept-proof");var accepts=setup(root);var proof=f.proof(accepts);
        try(var store=f.open(root,2,f.resources(),e->{})){store.proveCurrent(proof,accepts);}
        var copies=new ArrayList<MembershipFloor.Copy>();
        for(int node:f.nodes)try(var store=f.open(root,node,f.resources(),e->{})){copies.add(store.floorCopyCurrent());}
        for(int node:f.nodes)try(var store=f.open(root,node,f.resources(),e->{})) {
            store.establishFloor(copies);store.retireInactive();store.releaseFloor();
        }
        var sources=new ArrayList<MembershipSelection.Source>();
        for(int node:f.nodes)try(var store=f.open(root,node,f.resources(),e->{})) {
            store.prepareCurrent(f.f.fixture.source.ballot(21));sources.add(store.originalSource());
        }
        var own=sources.stream().filter(v->v.owner.nodeId().value().equals("node-2")).findFirst().orElseThrow();
        assertArrayEquals(proof.bytes(),own.capsule.packet.objectBytes(proof.digest()));String basisId=(String)own.basis.value().get("basisId");
        Path original=f.node(root,2).resolve("sources").resolve(basisId).resolve("source.gscp");byte[] frozen=Files.readAllBytes(original);
        try(var store=f.open(root,2,f.resources(),e->{})) {
            store.selectCurrent(sources,List.of());store.installCurrent(sources,List.of(),f.f.fixture.source.images);
            var newAccept=store.acceptCurrent(f.entry(),f.payload());assertNotEquals(own.accepted.digest(),newAccept.record());
            assertTrue(store.currentOwnedProof().isEmpty());assertArrayEquals(frozen,Files.readAllBytes(original));
            var pending=MembershipPendingAccept.decode(Files.readAllBytes(f.node(root,2).resolve(MembershipPendingAccept.FILE)));
            assertArrayEquals(f.entry().bytes(),pending.entry().bytes());assertEquals(21L,object(pending.accept().value().get("ballot")).get("counter"));
        }
        try(var store=f.open(root,2,f.resources(),e->{})) {
            assertTrue(store.currentOwnedProof().isEmpty());assertArrayEquals(proof.bytes(),store.originalSource().capsule.packet.objectBytes(proof.digest()));
        }
    }

}
