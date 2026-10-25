package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ActivationTest {
    @TempDir Path temp;
    static Decoded response(Decoded request,String kind,Map<String,Object> payload) {
        var value=new TreeMap<>(request.value());value.put("sender",request.value().get("recipient"));value.put("recipient",request.value().get("sender"));
        value.put("payload",payload);return decode(encode("wire",kind,value),"wire",kind);
    }
    static Decoded changed(Decoded original,String key,Object value) {
        var fields=new TreeMap<>(original.value());fields.put(key,value);return decode(encode(original.family(),original.kind(),fields),original.family(),original.kind());
    }
    final class Local implements AutoCloseable {
        final V53CurrentGenerationFixture fixture;
        final String change;
        final Path path;
        final MembershipResources storage=new MembershipResources(512*MembershipResources.MIB);
        final MembershipResources control=new MembershipResources(512*MembershipResources.MIB);
        final AtomicLong time=new AtomicLong(100);
        final MembershipGrantJournal journal;
        final MembershipActivation campaign;
        Local(int size,String change,int through) throws Exception {this(size,change,through,e->{});}
        Local(int size,String change,int through,MembershipBallotAllocator.Cut cut) throws Exception {
            this.change=change;
            fixture=new V53CurrentGenerationFixture(size,new V53CapsuleFixture(size,change,through));
            path=temp.resolve(UUID.randomUUID().toString());fixture.provision(path);
            journal=MembershipGrantJournal.openGenerations(path,fixture.root(),V53DeclarationsTest.node(1),storage,fixture::verify,cut);
            campaign=new MembershipActivation(journal,control,time::get,1000);
        }
        MembershipIdentity peer(int node){return fixture.admitted.context.identities.get("node-"+node);}
        MembershipSelection.Source source(int node) {
            return new V53SelectionFixture(fixture.size,change,fixture.fixture.through)
                    .source("node-"+node,number(campaign.ballot().get("counter")),null,0);
        }
        MembershipActivation.Prepared prepare(int node) throws Exception {
            var request=campaign.prepare(peer(node));var source=source(node);
            return new MembershipActivation.Prepared(response(request,"PROMISE",Map.of("basis",source.basis.digest())),source);
        }
        void offer(int node) throws Exception {campaign.promised(peer(node),prepare(node),List.of());}
        Decoded ack(int node) throws Exception {
            var selected=journal.originalSelection().orElseThrow();
            return response(campaign.installation(peer(node)),"INSTALL_ACK",Map.of("selection",selected.digest(),"cut",selected.value().get("cut")));
        }
        void local() throws Exception {campaign.installLocal(List.of(),fixture.fixture.source.images);}
        @Override public void close() throws Exception {campaign.close();journal.close();assertEquals(0,control.usage().leases());assertEquals(0,storage.usage().leases());}
    }
    @Test void realAdmittedOwnersForceGrantSelectionAndAllInstallationsAtEveryStableSize() throws Exception {
        Path evidence=Path.of("target/v53-activation/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        System.out.println("v53ActivationEvidence="+evidence.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("admitted-"+size)),raw,size,false);
            var owners=new ArrayList<MembershipGrantJournal>();var resources=new ArrayList<MembershipResources>();var events=new TreeMap<String,List<String>>();
            var queue=new MembershipResources(512*MembershipResources.MIB);var time=new AtomicLong();
            try {
                for(var target:f.request.targets()) {
                    var r=new MembershipResources(512*MembershipResources.MIB);resources.add(r);var cuts=new ArrayList<String>();events.put(target.identity().nodeId().value(),cuts);
                    owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),r,
                            (root,packet,images)->MembershipCapsule.verify(root,packet,images,Set.of()),MembershipGrantJournal.MAXIMUM,cuts::add));
                }
                var proposer=f.request.targets().getFirst().identity();
                try(var campaign=new MembershipActivation(owners.getFirst(),queue,time::get,1000)) {
                    assertTrue(events.get(proposer.nodeId().value()).contains("GRANT_BEFORE_RETURN"));
                    assertEquals(owners.getFirst().originalBasis().orElseThrow().digest(),campaign.ownSource().basis.digest());
                    var images=new TreeMap<String,byte[]>();var wire=new ArrayList<Map<String,Object>>();
                    for(int n=1;n<=size/2;n++) {
                        var peer=f.request.targets().get(n).identity();var request=campaign.prepare(peer);
                        assertArrayEquals(request.bytes(),campaign.prepare(peer).bytes()); // one identical lost-request retry
                        var before=V53ReplayFilesTest.files(f.request.targets().get(n).replicaDirectory());
                        var bad=changed(request,"payload",Map.of("promise","0".repeat(64)));int member=n;
                        assertThrows(IllegalArgumentException.class,()->MembershipActivation.prepare(owners.get(member),proposer,bad,owners.getFirst().promised().orElseThrow()));
                        assertEquals(before,V53ReplayFilesTest.files(f.request.targets().get(n).replicaDirectory()));
                        var reply=MembershipActivation.prepare(owners.get(n),proposer,request,owners.getFirst().promised().orElseThrow());
                        var duplicate=MembershipActivation.prepare(owners.get(n),proposer,request,owners.getFirst().promised().orElseThrow());
                        assertArrayEquals(reply.response().bytes(),duplicate.response().bytes());assertArrayEquals(reply.source().basis.bytes(),duplicate.source().basis.bytes());
                        wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.response().bytes())));
                        campaign.promised(peer,reply,List.of());
                    }
                    assertEquals(MembershipActivation.State.INSTALLING,campaign.state());assertEquals(size/2+1,campaign.sources().size());
                    var source=campaign.ownSource();var target=f.request.targets().getFirst();
                    for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(target.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
                    assertThrows(IllegalArgumentException.class,campaign::votingSelection);
                    campaign.installLocal(List.of(),images);
                    for(int n=1;n<=size/2;n++) {
                        var peer=f.request.targets().get(n).identity();var request=campaign.installation(peer);
                        var before=V53ReplayFilesTest.files(f.request.targets().get(n).replicaDirectory());
                        var bad=changed(request,"payload",Map.of("selection","0".repeat(64)));int member=n;
                        assertThrows(IllegalArgumentException.class,()->MembershipActivation.install(owners.get(member),proposer,bad,campaign.sources(),campaign.ancestry(),List.of(),images));
                        assertEquals(before,V53ReplayFilesTest.files(f.request.targets().get(n).replicaDirectory()));
                        var reply=MembershipActivation.install(owners.get(n),proposer,request,campaign.sources(),campaign.ancestry(),List.of(),images);
                        var duplicate=MembershipActivation.install(owners.get(n),proposer,request,campaign.sources(),campaign.ancestry(),List.of(),images);
                        assertArrayEquals(reply.bytes(),duplicate.bytes());
                        assertThrows(IllegalArgumentException.class,campaign::votingSelection);
                        wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));
                        campaign.installed(peer,reply);
                    }
                    assertEquals(MembershipActivation.State.INSTALLED,campaign.state());var selected=campaign.votingSelection();
                    assertEquals(0,queue.usage().leases());Files.write(raw.resolve("selected.gsr"),selected.bytes());
                    Files.write(raw.resolve("wire.json"),canonical(wire,1024*1024));
                    for(int n=0;n<=size/2;n++)owners.get(n).checkActivation(owners.get(n).originalBasis().orElseThrow(),selected,true);
                    rows.add(Map.of("case","stable-"+size,"status","PASS","selected",size/2+1,"installed",size/2+1));
                }
            }finally {
                for(var owner:owners)owner.close();for(var r:resources)assertEquals(0,r.usage().leases());assertEquals(0,queue.usage().leases());
                f.snapshot("installed");Files.write(raw.resolve("events.json"),canonical(events.entrySet().stream().map(e->Map.of("node",e.getKey(),"events",e.getValue())).toList(),1024*1024));
                Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-activation-component-v1","cases",rows,
                        "status",rows.size()==3?"PASS":"INCOMPLETE","publicRuntime",false,"network",false,"syntheticOwners",false),65536));
            }
        }
    }
    @Test void allSevenProfilesSelectInOldJointAndNewViewsWithBothMajorities() throws Exception {
        for(var profile:V53SelectionTest.PROFILES)for(int through:List.of(5,6,7))try(var local=new Local(profile.getKey(),profile.getValue(),through)) {
            for(String node:new TreeSet<>(local.fixture.admitted.context.voters())) {
                if(node.equals("node-1"))continue;local.offer(Integer.parseInt(node.substring(5)));
                if(local.campaign.state()==MembershipActivation.State.INSTALLING)break;
            }
            assertEquals(MembershipActivation.State.INSTALLING,local.campaign.state());
            local.fixture.admitted.context.quorum(local.campaign.sources().stream().map(s->s.owner.nodeId().value()).toList());
        }
    }
    @Test void jointSelectionIsFixedAndEverySelectedInstallationIsRequired() throws Exception {
        try(var local=new Local(5,"REPLACE",6)) {
            var late=local.prepare(3);local.offer(2);local.offer(5); // old majority only
            assertEquals(MembershipActivation.State.PREPARING,local.campaign.state());assertTrue(local.journal.originalSelection().isEmpty());
            local.offer(6);var selected=local.journal.originalSelection().orElseThrow();
            assertEquals(List.of("node-1","node-2","node-5","node-6"),local.campaign.sources().stream().map(s->s.owner.nodeId().value()).toList());
            assertThrows(IllegalArgumentException.class,()->local.campaign.promised(local.peer(3),late,List.of()));
            assertArrayEquals(selected.bytes(),local.journal.originalSelection().orElseThrow().bytes());
            local.local();local.campaign.installed(local.peer(2),local.ack(2));local.campaign.installed(local.peer(5),local.ack(5));
            assertThrows(IllegalArgumentException.class,local.campaign::votingSelection);
            local.campaign.installed(local.peer(6),local.ack(6));assertEquals(selected.digest(),local.campaign.votingSelection().digest());
        }
    }
    @Test void repliesBindCorrelationPermanentIdentityOriginalSourceAndExactCut() throws Exception {
        try(var local=new Local(5,"REPLACE",0)) {
            var reply=local.prepare(2);var r=reply.response();
            for(var altered:List.of(changed(r,"trace",UUID.randomUUID().toString()),changed(r,"sequence",999L),
                    changed(r,"recipient",MembershipBootstrapSeed.identity(local.peer(3))),changed(r,"payload",Map.of("basis","a".repeat(64)))))
                assertThrows(IllegalArgumentException.class,()->local.campaign.promised(local.peer(2),new MembershipActivation.Prepared(altered,reply.source()),List.of()));
            var wrongDisk=new MembershipIdentity(local.peer(2).nodeId(),UUID.randomUUID(),local.peer(2).endpoint());
            assertThrows(IllegalArgumentException.class,()->local.campaign.promised(wrongDisk,reply,List.of()));
            local.campaign.promised(local.peer(2),reply,List.of());local.campaign.promised(local.peer(2),reply,List.of());
            assertEquals(MembershipActivation.State.PREPARING,local.campaign.state());local.offer(3);local.local();
            var ack=local.ack(2);var bad=changed(ack,"payload",Map.of("selection","b".repeat(64),"cut",object(ack.value().get("payload")).get("cut")));
            assertThrows(IllegalArgumentException.class,()->local.campaign.installed(local.peer(2),bad));
            local.campaign.installed(local.peer(2),ack);local.campaign.installed(local.peer(2),ack);
            assertThrows(IllegalArgumentException.class,local.campaign::votingSelection);
            local.campaign.installed(local.peer(3),local.ack(3));assertNotNull(local.campaign.votingSelection());
        }
    }
    @Test void threeIdenticalAttemptsShareOneDeadlineAndExhaustionEndsTheCampaign() throws Exception {
        try(var local=new Local(3,"REPLACE",0)) {
            var first=local.campaign.prepare(local.peer(2));local.time.set(500);
            assertArrayEquals(first.bytes(),local.campaign.prepare(local.peer(2)).bytes());local.time.set(1000);
            assertArrayEquals(first.bytes(),local.campaign.prepare(local.peer(2)).bytes());
            assertThrows(IllegalArgumentException.class,()->local.campaign.prepare(local.peer(2)));
            assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());assertEquals(0,local.control.usage().leases());
        }
        try(var local=new Local(3,"REPLACE",0)) {
            var reply=local.prepare(2);local.time.set(1100);
            assertThrows(IllegalArgumentException.class,()->local.campaign.promised(local.peer(2),reply,List.of()));
            assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());assertTrue(local.journal.originalSelection().isEmpty());
        }
    }
    @Test void higherRejectAndExternalObservationFenceLateRepliesAndNextBallotAdvances() throws Exception {
        try(var local=new Local(3,"REPLACE",0)) {
            var request=local.campaign.prepare(local.peer(2));var higher=new TreeMap<>(local.campaign.ballot());higher.put("counter",50L);
            var rejected=response(request,"REJECT",Map.of("promised",higher,"reason","STALE_EPOCH"));
            local.campaign.rejected(local.peer(2),rejected);assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());
            try(var fresh=new MembershipActivation(local.journal,local.control,local.time::get,1000)) {
                assertEquals(51L,number(fresh.ballot().get("counter")));
            }
        }
        try(var local=new Local(3,"REPLACE",0)) {
            local.offer(2);local.local();var ack=local.ack(2);var higher=new TreeMap<>(local.campaign.ballot());higher.put("counter",60L);
            local.journal.observeCurrent(higher);
            assertThrows(IllegalArgumentException.class,()->local.campaign.installed(local.peer(2),ack));
            assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());
        }
    }
    @Test void higherRejectionFromAnEarlierPrepareStillFencesAfterSelection() throws Exception {
        try(var local=new Local(3,"REPLACE",0)) {
            var original=local.campaign.prepare(local.peer(2));local.offer(2);local.local();
            var ack=local.ack(2);var higher=new TreeMap<>(local.campaign.ballot());higher.put("counter",70L);
            // A delayed old rejection after its successful response cannot undo that success.
            local.campaign.rejected(local.peer(2),response(original,"REJECT",Map.of("promised",local.campaign.ballot(),"reason","NOT_READY")));
            assertEquals(MembershipActivation.State.INSTALLING,local.campaign.state());
            local.campaign.rejected(local.peer(2),response(original,"REJECT",Map.of("promised",higher,"reason","STALE_EPOCH")));
            assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());
            assertThrows(IllegalArgumentException.class,()->local.campaign.installed(local.peer(2),ack));
        }
    }
    @Test void deadlineDuringSelectionCannotPublishInstallationOrChooseAnotherSet() throws Exception {
        var time=new AtomicLong(100);
        try(var local=new Local(3,"REPLACE",0,event->{if(event.equals("SELECTED_BEFORE_RETURN"))time.set(1100);})) {
            // The controller's monotonic clock is independent of wall time and can expire at a force boundary.
            // Use the fixture's owner with a fresh campaign and this clock.
            local.campaign.close();
            try(var campaign=new MembershipActivation(local.journal,local.control,time::get,1000)) {
                var peer=local.peer(2);var req=campaign.prepare(peer);
                var source=new V53SelectionFixture(3,"REPLACE",0).source("node-2",number(campaign.ballot().get("counter")),null,0);
                assertThrows(IllegalArgumentException.class,()->campaign.promised(peer,new MembershipActivation.Prepared(response(req,"PROMISE",Map.of("basis",source.basis.digest())),source),List.of()));
                assertEquals(MembershipActivation.State.ABANDONED,campaign.state());assertTrue(local.journal.originalSelection().isPresent());
                assertThrows(IllegalArgumentException.class,()->campaign.prepare(local.peer(3)));
            }
        }
    }
    @Test void installationFailureAndCloseReleaseControlAndDoNotInventAnAck() throws Exception {
        try(var local=new Local(3,"REPLACE",0,event->{if(event.equals("INSTALL_BEFORE_RETURN"))throw new IOException("injected after durable install");})) {
            local.offer(2);local.campaign.installation(local.peer(2));
            assertThrows(IOException.class,local::local);assertEquals(MembershipActivation.State.ABANDONED,local.campaign.state());
            assertThrows(IllegalArgumentException.class,local.campaign::votingSelection);assertEquals(0,local.control.usage().leases());
        }
        try(var local=new Local(3,"REPLACE",0)) {
            var reply=local.prepare(2);local.campaign.close();
            assertThrows(IllegalArgumentException.class,()->local.campaign.promised(local.peer(2),reply,List.of()));
            assertTrue(local.journal.originalSelection().isEmpty());assertEquals(0,local.control.usage().leases());
        }
    }
    @Test void queueExhaustionEndsCampaignAndKeepsDurableGrantForRecovery() throws Exception {
        try(var local=new Local(3,"REPLACE",0)) {
            local.campaign.close();var bounded=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,128);
            try(var campaign=new MembershipActivation(local.journal,bounded,local.time::get,1000)) {
                var original=local.journal.originalBasis().orElseThrow();
                assertThrows(IllegalArgumentException.class,()->campaign.prepare(local.peer(2)));
                assertEquals(MembershipActivation.State.ABANDONED,campaign.state());assertEquals(0,bounded.usage().leases());
                assertArrayEquals(original.bytes(),local.journal.originalBasis().orElseThrow().bytes());assertTrue(local.journal.originalSelection().isEmpty());
            }
        }
    }
    @Test void acceptedTailRemainsOriginalAndDoesNotBecomeAServiceReadySignal() throws Exception {
        try(var local=new Local(3,"REPLACE",9)) {
            var peer=local.peer(2);var request=local.campaign.prepare(peer);
            var source=new V53SelectionFixture(3,"REPLACE",9).source("node-2",number(local.campaign.ballot().get("counter")),"carried",3);
            local.campaign.promised(peer,new MembershipActivation.Prepared(response(request,"PROMISE",Map.of("basis",source.basis.digest())),source),List.of());
            assertEquals(source.entry.digest(),local.journal.originalSelection().orElseThrow().value().get("nextEntry"));
            assertArrayEquals(source.entry.bytes(),local.campaign.sources().get(1).entry.bytes());
            assertThrows(IllegalArgumentException.class,local.campaign::votingSelection);
        }
    }
}
