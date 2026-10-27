package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Original four-voter history; a non-accepting owner inherits the carried result
 * and subsequently adopts its certified removal from the surviving majority. */
class V53InheritedFutureAdoptionTest {
    @TempDir Path temp;
    @FunctionalInterface interface Configure {
        void configure(V53BootstrapPublicationTest.Fixture fixture,V53AdmittedCrossViewTest.Walk walk)throws Exception;
    }

    static void finishCarried(V53BootstrapPublicationTest.Fixture f,
            List<MembershipBootstrapTarget<Integer,Doc>> targets)throws Exception {
        var first=targets.getFirst();
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(first.replicaDirectory().resolve(MembershipPendingAccept.FILE)));
        var accepts=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"carried-accept")){accepts.add(owner.acceptCurrent(vote.entry(),vote.payload()));}
        var fields=new TreeMap<>(vote.accept().value());
        fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",vote.accept(),accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"carried-proof")){proofs.add(owner.proveCurrent(proof,accepts));}
        fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
        var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
        var phases=new HashSet<>(accepts);phases.addAll(proofs);
        for(var t:targets)try(var owner=f.open(t,"carried-certificate")){owner.certifyCurrent(certificate,phases);}
        f.snapshot("carried-certified");
        var acks=new ArrayList<Decoded>();var ends=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"carried-apply")) {
            var applied=owner.applyCurrent(builder().configuration(),t.materialization());
            acks.add(applied.endorsement().acknowledgement());ends.add(applied.endorsement().owned());
        }
        f.snapshot("carried-applied");
        for(var t:targets)try(var owner=f.open(t,"carried-publish")) {
            owner.publishCurrent(owner.applyCurrent(builder().configuration(),t.materialization()),acks,ends,List.of());
            assertFalse(owner.futureRetentionState().pending());
        }
        f.snapshot("carried-published");
    }

    @Test void nonAcceptingOwnerKeepsInheritedEndpointsThroughCertifiedRemovalAndReopen()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-inherited-adoption/run-"+UUID.randomUUID()));
        System.out.println("v53InheritedAdoptionEvidence="+raw.toAbsolutePath());
        history(temp,raw,(fixture,walk)->{});
    }
    static void history(Path temp,Path raw,Configure configure)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("group")),raw,4,false);
        f.ownedHistory=true;f.nativeApplication=true;var all=f.request.targets();var survivors=all.subList(0,3);var lagging=all.getLast();
        boolean success=false;
        try {
            for(var t:all)try(var owner=f.open(t,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
            f.snapshot("retaining-genesis");var walk=new V53AdmittedCrossViewTest.Walk(f);
            walk.publicationParticipants=targets->targets.stream().filter(t->!t.identity().equals(lagging.identity())).toList();
            f.observer=(target,operation,event)->{if(operation.equals("publish-1"))throw new V53NativeApplicationTest.Stop();};
            try{assertThrows(V53NativeApplicationTest.Stop.class,()->walk.publish("BARRIER",null));}
            finally{f.observer=(target,operation,event)->{};}
            f.snapshot("original-certified");
            for(int i=0;i<2;i++) {
                var t=all.get(i);var peer=all.get(i+1);
                try(var owner=f.open(t,"original-future")) {
                    owner.retainFutureDispatch(peer.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization())));
                }
            }
            f.snapshot("two-futures");
            var install=V53DistinctMinorityTest.campaign(f,3,all,false);
            for(var t:all)try(var owner=f.open(t,"inherited-install")){owner.installCurrent(install.sources(),List.of(),install.images());}
            f.snapshot("inherited-installed");
            for(var t:survivors)try(var owner=f.open(t,"carried-retire")) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve(MembershipPendingAccept.FILE)));
                owner.retireSupersededApplication(builder().configuration(),t.materialization());
                owner.acceptCurrent(vote.entry(),vote.payload());
            }
            walk.maintain("inherited-maintained",all,install.obsolete());
            try(var owner=f.open(lagging,"non-accepting-original")) {
                assertTrue(owner.currentCertificate().isEmpty());assertFalse(owner.futureRetentionState().pending());
                assertArrayEquals(MembershipPendingAccept.empty(),Files.readAllBytes(lagging.replicaDirectory().resolve(MembershipPendingAccept.FILE)));
                var copy=owner.floorCopyCurrent();
                var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
                var original=MembershipSelectedRetention.find(copy.capsule,selected,lagging.identity()).orElseThrow();
                assertEquals(2,original.futures().size());assertTrue(original.hasPendingFutures());
                assertEquals(0L,copy.capsule.context.cut.get("index"));
            }
            finishCarried(f,survivors);walk.maintain("survivors-published",survivors,Map.of());
            walk.counter=3;walk.campaign(survivors);
            // Explicit native reconciliation at the actual publication boundary;
            // this fixture does not claim an autonomous runtime scheduler.
            walk.afterPublication=(kind,targets)->{
                if(kind.equals("INTENT") || kind.equals("FINAL"))
                    for(var t:targets)try(var owner=f.open(t,"configuration-retention")){owner.reconcilePeerRetention(List.of());}
            };
            configure.configure(f,walk);
            walk.adoption=(target,remote,images,number)->{
                byte[] ancestry=list(remote.generation.value().get("files")).stream().map(MembershipFormat::object)
                        .anyMatch(row->row.get("path").equals("ancestry.gsr"))?remote.fileBytes("ancestry.gsr"):new byte[0];
                var bridges=remote.capsule.verifiedAncestry(ancestry);
                f.snapshot("before-inherited-adoption");
                var rejectedBefore=V53ReplayFilesTest.files(target.replicaDirectory());
                try(var owner=f.open(target,"inherited-adopt-missing-ancestry")) {
                    var failure=assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(remote.capsule,images,List.of()));
                    assertEquals("generation did not preserve original proven parent",failure.getMessage());
                }
                assertEquals(rejectedBefore,V53ReplayFilesTest.files(target.replicaDirectory()));
                f.snapshot("rejected-inherited-adoption");
                try(var owner=f.open(target,"inherited-adopt")) {
                    var manifest=owner.adoptCurrent(remote.capsule,images,bridges);
                    assertArrayEquals(manifest.bytes(),owner.adoptCurrent(remote.capsule,images,bridges).bytes());
                    assertEquals(1L,owner.activationContext().view.get("generation"));
                    assertFalse(owner.activationContext().voters().contains(target.identity().nodeId().value()));
                    for(var peer:all.subList(1,3))assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                    assertFalse(owner.futureRetentionState().pending());
                }
                var before=V53ReplayFilesTest.files(target.replicaDirectory());
                try(var owner=f.open(target,"inherited-adopt-reopen")) {
                    assertEquals(remote.capsule.context.cut,owner.activationContext().cut);
                    for(var peer:all.subList(1,3))assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                }
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            };
            walk.removeLast(1);assertEquals(0,f.resources.usage().leases());success=true;
        }finally {
            V53NativeApplicationTest.save(f);
            Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
            Files.write(raw.resolve("result.json"),canonical(Map.of("status",success?"PASS":"FAIL","originalVoters",4,
                    "survivingVoters",3,"publicRuntime",false,"independentReplay",false),16384));
        }
    }
}
