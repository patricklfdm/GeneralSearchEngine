package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Real TCP, typed owner and scratch lifetime. Voter histories are conditional
 * fixtures, not native autonomous cancellation/INTENT qualification. */
class V53LearnerProgressNetworkTest {
    @TempDir Path temp;
    final class Peer implements AutoCloseable {
        final MembershipResources server=V53SourceExchangeTest.resources();
        final Path path;
        final MembershipGrantJournal owner;
        final MembershipTransferService service;
        Peer(V53CapsuleFixture history,boolean retainParent)throws Exception {
            var f=new V53CurrentGenerationFixture(3,history);path=temp.resolve("peer-"+UUID.randomUUID());f.provision(path);
            var bridges=retainParent?List.of(bridge(history,3,history.through<6?history.through:5)):List.<MembershipSelection.Bridge>of();
            var opened=MembershipGrantJournal.openGenerations(path,f.root(),V53DeclarationsTest.node(1),server,f::verify,e->{});
            try {
                if(retainParent) {
                    // First create an actual selected generation. Conditional
                    // historical ancestry is then provisioned just as in the
                    // existing publication-admission fixtures; no new remote
                    // CHECKPOINT_ACK observation is claimed by this TCP test.
                    opened.prepareCurrent(history.source.ballot(20));var offers=new ArrayList<MembershipSelection.Source>();offers.add(opened.originalSource());
                    var selection=new V53SelectionFixture(history);
                    for(String voter:List.of("node-2","node-3"))offers.add(selection.source(voter,20,null,0));
                    opened.selectCurrent(offers,List.of());var manifest=opened.installCurrent(offers,List.of(),history.source.images);opened.close();
                    Path generation=path.resolve("generations").resolve((String)manifest.value().get("generation"));
                    byte[] bytes=MembershipGenerationPlan.ancestry(bridges);AdmissionPaths.write(generation.resolve("ancestry.gsr"),bytes);
                    var fields=new TreeMap<>(manifest.value());var rows=new TreeMap<String,Object>();
                    for(Object row:list(fields.get("files")))rows.put((String)object(row).get("path"),row);
                    rows.put("ancestry.gsr",Map.of("path","ancestry.gsr","sha256",hash(bytes),"size",(long)bytes.length));fields.put("files",new ArrayList<>(rows.values()));
                    var changed=decode(encode("records","GENERATION",fields),"records","GENERATION");Files.write(generation.resolve("generation.gsr"),changed.bytes());
                    var selector=new TreeMap<>(decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR").value());selector.put("digest",changed.digest());
                    Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",selector));
                    opened=MembershipGrantJournal.openGenerations(path,f.root(),V53DeclarationsTest.node(1),server,
                            (r,p,m)->f.verify(r,p,m).retainingVerifiedAncestry(bridges),e->{});
                }
                service=MembershipTransferService.prefix(opened,server,ReplicationBounds.defaults(),()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60));
                owner=opened;
            }catch(Exception|Error error){try{opened.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
        }
        @Override public void close()throws Exception {service.close();owner.close();assertEquals(0,server.usage().leases());}
    }
    static MembershipSelection.Bridge bridge(V53CapsuleFixture capsule,int from,int to) {
        var f=capsule.source;var before=capsule.state(from);var after=capsule.state(to);
        var statement=f.record("CHECKPOINT",map("root",f.rootHash,"scope","RANGE","start",before.get("cut"),"end",after.get("cut"),
                "catalogBefore",capsule.catalog(from),"catalogAfter",capsule.catalog(to),
                "applicationBefore",before.get("application"),"applicationAfter",after.get("application")));
        var cut=object(after.get("cut"));var acknowledgements=new ArrayList<Decoded>();var owned=new HashSet<MembershipContext.Owned>();
        for(String voter:nodes(object(cut.get("view")),"old")) {
            var identity=f.context().identities.get(voter);var ack=f.record("CHECKPOINT_ACK",map("root",f.rootHash,"voter",voter,
                    "incarnation",identity.storageId().toString(),"cut",cut,"statement",statement.digest()));acknowledgements.add(ack);
            owned.add(new MembershipContext.Owned(voter,identity.storageId(),ack.digest(),cutDigest(cut)));
        }
        return new MembershipSelection.Bridge(statement,acknowledgements,owned);
    }
    @Test void preparedOwnerReadsCancellationAndJointProgressWithoutChangingItsReceiptOrGrantingAVote()throws Exception {
        for(String phase:List.of("CANCELLED","JOINT","COMPLETED")) {
            var h=new V53LearnerMaterializationTest();h.temp=temp;
            try(var f=h.new Fixture(3,"ADD");var typed=f.prepare(e->{})) {
                var head=typed.retainGeneration();var original=f.source.fixture.fixture;
                var next=phase.equals("CANCELLED")?V53LearnerProgressTest.cancelled(original,3):
                        V53CapsuleFixture.fromHistory(original.source,phase.equals("JOINT")?6:7);
                try(var source=new Peer(next,true);
                        var transport=new MembershipTransport(source.owner,f.config.bounds(),source.server,(sender,request)->
                            request.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(source.owner.activationContext(),source.owner.activationIdentity(),sender,request):
                            source.service.handle(sender,request),MembershipTransport.Events.NONE)) {
                    byte[] receipt=typed.receipt().bytes();var before=V53ReplayFilesTest.files(f.source.request.replicaDirectory());
                    var beforeTyped=V53ReplayFilesTest.files(f.typed());var server=V53ReplayFilesTest.files(source.path);var usage=f.source.client.usage();
                    var exchanges=new ArrayList<String>();MembershipFloor.Copy copy;
                    try(var progress=new MembershipLearnerProgress(head,source.owner.activationIdentity(),f.config.bounds(),(event,request,response)->{
                        if(event.equals("AFTER_RESPONSE_READ"))exchanges.add(request.kind());
                    },System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                        copy=progress.fetch(f.base.resolve("progress"));assertSame(copy,progress.source());
                        assertEquals(phase,MembershipLearnerProgressAccess.operation(copy.capsule.context,f.source.request.identity()).get("phase"));
                        assertFalse(copy.capsule.containsCut(head.source().context.cut));
                        copy.capsule.verifyAncestry(copy.fileBytes("ancestry.gsr"),List.of(head.source().terminal()));assertArrayEquals(receipt,typed.receipt().bytes());
                        assertEquals(1,f.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                        assertEquals(1,f.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                        assertThrows(IllegalArgumentException.class,()->progress.fetch(f.base.resolve("second")));
                        progress.close();assertThrows(IllegalArgumentException.class,progress::source);
                    }
                    // Copy.check is pure byte validation, not a live ownership capability.
                    copy.check();assertEquals(usage,f.source.client.usage());
                    assertEquals(before,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));assertEquals(beforeTyped,V53ReplayFilesTest.files(f.typed()));
                    assertEquals(server,V53ReplayFilesTest.files(source.path));assertFalse(Files.exists(f.base.resolve("progress")));
                    assertEquals("STATUS_PROBE",exchanges.getFirst());assertTrue(exchanges.contains("TRANSFER_COMMIT"));
                    assertTrue(exchanges.stream().allMatch(k->Set.of("STATUS_PROBE","CHUNK","TRANSFER_COMMIT").contains(k)));
                    head.check();assertFalse(Files.exists(f.config.materialization().directory()));
                }
            }
        }
    }
    @Test void missingParentAncestryAndClosedTypedOwnersRefuseWithoutChangingLocalAuthority()throws Exception {
        var h=new V53LearnerMaterializationTest();h.temp=temp;
        try(var f=h.new Fixture(3,"ADD")) {
            MembershipLearnerHead closed;
            try(var typed=f.prepare(e->{})) {
                var head=typed.retainGeneration();closed=head;
                // This independently valid compacted source omits the prepared
                // owner's exact cut. A higher index is not sufficient ancestry.
                var next=V53CapsuleFixture.fromHistory(f.source.fixture.fixture.source,6);
                try(var source=new Peer(next,false);
                        var transport=new MembershipTransport(source.owner,f.config.bounds(),source.server,(sender,request)->
                            request.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(source.owner.activationContext(),source.owner.activationIdentity(),sender,request):
                            source.service.handle(sender,request),MembershipTransport.Events.NONE);
                        var progress=new MembershipLearnerProgress(head,source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                                System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                    var before=V53ReplayFilesTest.files(f.source.request.replicaDirectory());var usage=f.source.client.usage();
                    var error=assertThrows(IllegalArgumentException.class,()->progress.fetch(f.base.resolve("unrelated")));
                    assertEquals("generation did not preserve original proven parent",error.getMessage());
                    assertEquals(usage,f.source.client.usage());assertEquals(before,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));
                    assertThrows(IllegalArgumentException.class,progress::source);
                }
            }
            assertThrows(IllegalArgumentException.class,()->new MembershipLearnerProgress(closed,f.source.owner.activationIdentity(),f.config.bounds(),
                    MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60)));
        }
    }
    @Test void progressTransportStillRejectsVotingAndEnrollmentReferencesInTheJointView()throws Exception {
        var helper=new V53LearnerSourceTest();helper.temp=temp;
        try(var f=helper.new Fixture(3,"ADD",6);
                var contact=MembershipTransport.learnerProgress(f.request,f.hint,ReplicationBounds.defaults(),f.client,MembershipTransport.Events.NONE)) {
            assertTrue(f.owner.activationContext().voters().contains(f.request.identity().nodeId().value()));
            var frame=new TreeMap<String,Object>(Map.of("root",f.request.root().manifestDigest(),"view",f.request.change().expectedConfigurationDigest(),
                    "ballot",MembershipLearnerDiscovery.correlation(f.request.identity()),"sender",MembershipBootstrapSeed.identity(f.request.identity()),
                    "recipient",MembershipBootstrapSeed.identity(f.hint.peer()),"trace",UUID.randomUUID().toString(),"sequence",1L,
                    "payload",Map.of("promise","ab".repeat(32))));
            var vote=decode(encode("wire","PREPARE",frame),"wire","PREPARE");
            assertEquals(MembershipTransport.Reason.PROTOCOL,V53MembershipTransportTest.failure(contact.exchange(f.hint.peer(),vote,"PROMISE",
                    System.nanoTime()+TimeUnit.SECONDS.toNanos(10))).reason);
            for(String reference:List.of(MembershipLearnerPrefixExport.reference(f.request,f.hint.cut(),"prefix"),MembershipLearnerDiscovery.reference(f.request))) {
                frame.put("payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",reference,"bytes",""));
                var request=decode(encode("wire","CHUNK",frame),"wire","CHUNK");
                assertEquals(MembershipTransport.Reason.PROTOCOL,V53MembershipTransportTest.failure(contact.exchange(f.hint.peer(),request,"SOURCE_OFFER",
                        System.nanoTime()+TimeUnit.SECONDS.toNanos(10))).reason);
            }
            assertThrows(IllegalArgumentException.class,()->contact.learn(f.owner.activationCapsule()));
            assertEquals(0,contact.usage().sockets());assertEquals(0,f.client.usage().leases());
        }
    }
}
