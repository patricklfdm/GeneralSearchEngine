package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53NativeRetirementTest {
    @TempDir Path temp;
    static long publishedIndex(Path directory)throws Exception {
        var selector=decode(Files.readAllBytes(directory.resolve("selector.gsr")),"records","SELECTOR");
        var generation=decode(Files.readAllBytes(directory.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
        assertEquals(selector.value().get("digest"),generation.digest());return number(object(generation.value().get("cut")).get("index"));
    }
    static V53BootstrapPublicationTest.Fixture prepared(Path home,Path raw)throws Exception {
        var f=V53NativeApplicationTest.certified(home,raw);f.snapshot("certified");
        for(var t:f.request.targets())try(var owner=f.open(t,"old-apply")){owner.applyCurrent(builder().configuration(),t.materialization());}
        f.snapshot("old-applied");V53DistinctMinorityTest.campaign(f,3,f.request.targets());return f;
    }
    static void onlyDerivedRemoved(Map<String,String> before,Path directory)throws Exception {
        var expected=new TreeMap<>(before);expected.keySet().removeIf(n->n.equals("applied-end") || n.startsWith("applied-end/") || n.equals("application-replay") || n.startsWith("application-replay/"));
        assertEquals(expected,V53ReplayFilesTest.files(directory));V53StagedApplicationTest.noStaging(directory);
    }
    static void finish(V53BootstrapPublicationTest.Fixture f)throws Exception {
        var t=f.request.targets().getFirst();var old=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept")));
        var accepts=new HashSet<MembershipContext.Owned>();
        for(var node:f.request.targets())try(var owner=f.open(node,"reaccept")){accepts.add(owner.acceptCurrent(old.entry(),old.payload()));}
        // The new vote now owns the carried entry. Establish a real governing
        // floor before reusing the old generation's publication slot.
        V53DistinctMinorityTest.maintain(f,"new-reclaimed",f.request.targets(),Map.of());
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept")));var fields=new TreeMap<>(vote.accept().value());
        fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",vote.accept(),accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<MembershipContext.Owned>();
        for(var node:f.request.targets())try(var owner=f.open(node,"reprove")){proofs.add(owner.proveCurrent(proof,accepts));}
        fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
        var cert=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var owned=new HashSet<>(accepts);owned.addAll(proofs);
        for(var node:f.request.targets())try(var owner=f.open(node,"recertify")){owner.certifyCurrent(cert,owned);}
        var acks=new ArrayList<Decoded>();var ends=new HashSet<MembershipContext.Owned>();
        for(var node:f.request.targets())try(var owner=f.open(node,"new-apply")){var applied=owner.applyCurrent(builder().configuration(),node.materialization());acks.add(applied.endorsement().acknowledgement());ends.add(applied.endorsement().owned());}
        for(var node:f.request.targets())try(var owner=f.open(node,"new-publish")) {
            owner.publishCurrent(owner.applyCurrent(builder().configuration(),node.materialization()),acks,ends,List.of());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
        }
        f.snapshot("new-published");
    }
    @Test void actualNativeCarriedCleanupPreservesAuthorityAndAllowsNewBallotPublication()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-native-retirement/carried-"+UUID.randomUUID()));
        var f=prepared(Files.createDirectory(temp.resolve("carried")),raw);
        try {
            assertTrue(f.observations.isEmpty());
            for(var t:f.request.targets()) {
                var before=V53ReplayFilesTest.files(t.replicaDirectory());
                try(var owner=f.open(t,"native-retire")) {
                    assertThrows(IllegalArgumentException.class,()->owner.retireSupersededApplication(builder().configuration(),t.materialization(),Set.of()));
                    assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
                    owner.retireSupersededApplication(builder().configuration(),t.materialization());owner.retireSupersededApplication(builder().configuration(),t.materialization());
                    assertTrue(owner.currentCertificate().isPresent());assertEquals(0L,publishedIndex(t.replicaDirectory()));
                }
                onlyDerivedRemoved(before,t.replicaDirectory());
            }
            f.snapshot("native-retired");finish(f);
            for(var row:f.calls)if(row.get("operation").equals("native-retire")) {
                var events=list(row.get("events"));assertTrue(events.indexOf("CERTIFICATE_ACTIVE_PARENT_FORCED")<events.indexOf("NATIVE_RETIREMENT_CERTIFICATE_RETAINED"));
                assertTrue(events.indexOf("NATIVE_RETIREMENT_CERTIFICATE_RETAINED")<events.indexOf("SUPERSEDED_END_AUTHORITY_FORCED"));
                assertFalse(events.stream().map(String::valueOf).anyMatch(e->e.startsWith("APPLY_ACK_") || e.equals("APPLY_BEFORE_RETURN")));
            }
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void coveredNativeCleanupUsesRealSelectedPrefixWithoutOldVotingObservations()throws Exception {
        var helper=new V53CoveredPhasedVoteTest();helper.temp=Files.createDirectory(temp.resolve("covered"));
        var p=helper.prepared(3,false,"CERTIFICATE",f->{
            f.ownedHistory=true;var target=f.request.targets().getFirst();
            try(var owner=f.open(target,"lagging-apply")){owner.applyCurrent(builder().configuration(),target.materialization());}
            f.snapshot("lagging-applied");
        });var f=p.f();f.observations.clear();var t=f.request.targets().getFirst();
        try {
            var before=V53ReplayFilesTest.files(t.replicaDirectory());
            try(var owner=f.open(t,"native-covered-retire")) {
                owner.retireCoveredApplication(builder().configuration(),t.materialization(),p.installation().sources(),List.of(),List.of(),p.installation().images(),List.of());
                assertTrue(owner.currentCertificate().isPresent());assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            onlyDerivedRemoved(before,t.replicaDirectory());
            try(var owner=f.open(t,"native-covered-install")){owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());assertTrue(owner.currentCertificate().isEmpty());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));}
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void higherObservedBallotAllowsCleanupButNeverOldApplicationAuthority()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-native-retirement/fence-"+UUID.randomUUID()));
        var f=prepared(Files.createDirectory(temp.resolve("fence")),raw);var t=f.request.targets().getFirst();var before=V53ReplayFilesTest.files(t.replicaDirectory());
        try {
            MembershipGrantJournal[] active={null};boolean[] seen={false};
            f.observer=(node,op,event)->{if(op.equals("fenced-cleanup") && event.equals("NATIVE_RETIREMENT_CERTIFICATE_RETAINED")) {
                active[0].observeCurrent(Map.of("counter",9L,"proposer",t.identity().nodeId().value(),"incarnation",t.identity().storageId().toString()));seen[0]=true;
            }};
            try(var owner=f.open(t,"fenced-cleanup")) {
                active[0]=owner;owner.retireSupersededApplication(builder().configuration(),t.materialization());assertTrue(seen[0]);
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept")));
                assertThrows(IllegalArgumentException.class,()->owner.applyCurrent(builder().configuration(),t.materialization()));
                assertThrows(IllegalArgumentException.class,()->owner.acceptCurrent(vote.entry(),vote.payload()));
            }
            onlyDerivedRemoved(before,t.replicaDirectory());
        }finally{V53NativeApplicationTest.save(f);}
    }
}
