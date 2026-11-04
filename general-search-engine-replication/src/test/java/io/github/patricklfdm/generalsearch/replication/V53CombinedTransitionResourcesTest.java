package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceReceiveTest.*;

/** Opt-in diagnostic: one admitted REMOVE lifetime keeps two real receiving copies on a required
 * voter. Receiving copies exert storage pressure; they are not additional votes
 * or an admitted learner. Their deliberately extended lifetime is not yet shown
 * reachable through the automatic runtime. This is not a qualification gate.
 * No alternate quorum, timeout or retry is introduced. */
@EnabledIfSystemProperty(named="v53.combined.transition.probe",matches="true")
class V53CombinedTransitionResourcesTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture retained;
    ReplicationBounds retainedBounds;
    static final Set<String> POINTS=Set.of("INSTALL_BEFORE_RETURN","ACCEPT_PARENT_FORCED","PROOF_PARENT_FORCED",
            "PUBLICATION_ACK_BEFORE_RETURN","JOURNAL_ROTATION_PARENT_FORCED","SOURCE_RETIREMENT_BEFORE_RETURN","FLOOR_COPY_HANDED_OFF");

    static final class Capture {
        final Path root,scratch,authority;
        final V53NativeDispatchTest.Network network;
        final MembershipResources budget;
        final List<Map<String,Object>> rows=new ArrayList<>();
        Capture(Path root,Path scratch,V53NativeDispatchTest.Network network)throws Exception {
            this.root=Files.createDirectory(root);this.scratch=scratch;this.network=network;
            authority=network.f.request.targets().get(1).replicaDirectory();budget=network.resources.get(1);
        }
        synchronized void at(String point,int eventIndex)throws IOException {
            assertTrue(rows.size()<256,"bounded resource observations");String id=String.format(Locale.ROOT,"%03d",rows.size());
            Path dir=Files.createDirectory(root.resolve(id));
            try {
                V53CombinedReceiveResourcesTest.snapshot(authority,dir.resolve("authority"));
                V53CombinedReceiveResourcesTest.snapshot(scratch,dir.resolve("scratch"));
            }catch(IOException e){throw e;}catch(Exception e){throw new IOException(e);}
            rows.add(Map.of("id",id,"point",point,"eventIndex",eventIndex,"usage",V53CombinedReceiveResourcesTest.usage(budget)));
        }
        void event(String point)throws IOException {
            if(!POINTS.contains(point))return;
            int found=-1;synchronized(network.events){for(int i=network.events.size()-1;i>=0;i--) {
                var row=network.events.get(i);if(row.get("node").equals("node-2") && row.get("event").equals(point)){found=i;break;}
            }}
            assertTrue(found>=0,"original writer event");at(point,found);
        }
        void save()throws IOException {Files.write(root.resolveSibling("resources.json"),canonical(rows,1024*1024));}
    }

    @Test void admittedFinalCompletesWhileRequiredVoterRetainsRealReceivingCopies()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-combined-transition/run-"+UUID.randomUUID()));
        System.out.println("v53CombinedTransitionEvidence="+root.toAbsolutePath());var cases=new ArrayList<String>();
        try {
            for(int size:List.of(4,5)) {
                String profile=size+"-REMOVE";scenario(Files.createDirectory(root.resolve(profile)),size);
                cases.add(profile);System.out.println("v53CombinedTransitionCase="+profile+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-combined-transition-v1",
                "status",cases.size()==2?"PASS":"INCOMPLETE","cases",cases,"network",true,
                "simultaneousMaximumQualified",false,"publicRuntime",false,"phase3Complete",false),65536));
        }
    }
    void scenario(Path raw,int size)throws Exception {
        var helper=new V53TransitionRoundDriverTest();helper.temp=temp;var ordinal=new AtomicInteger();
        Path scratch=Files.createDirectory(temp.resolve("pressure-"+size));Path history=null;Capture capture=null;
        var held=new ArrayList<MembershipSourceReceive>();boolean success=false;
        try {
            try(var n=helper.network("SEALED",size)) {
                retained=n.f;retainedBounds=n.bounds;
                history=n.f.raw;capture=new Capture(raw.resolve("states"),scratch,n);var observed=capture;
                var owner=n.owners.get(1);var budget=n.resources.get(1);capture.at("before-hold",-1);
                try {
                    var source=owner.originalSource();
                    try(var export=owner.exportSource(source.basis,V53SourceExchangeTest.BUDGET)) {
                        Files.write(raw.resolve("source-promise.gsr"),export.promise().bytes());Files.write(raw.resolve("source-basis.gsr"),source.basis.bytes());
                        for(int i=0;i<2;i++) {
                            long started=System.nanoTime();Path path=scratch.resolve(i==0?"source":"learner");
                            var received=i==0?new MembershipSourceReceive(path,source.capsule.context.root,source.owner,export.promise(),source.basis,
                                    UUID.randomUUID(),packetOffer(export),budget,1024,System::nanoTime,started,V53SourceExchangeTest.BUDGET):
                                MembershipSourceReceive.learner(path,source.capsule.context.root,source.owner,source.capsule.context.cut,
                                    UUID.randomUUID(),UUID.randomUUID(),packetOffer(export),budget,1024,System::nanoTime,started,V53SourceExchangeTest.BUDGET);
                            held.add(received);send(received,export,received.packetBinding());
                            for(var binding:received.imageBindings())send(received,export,binding);
                            received.packet().verifyImages(received.images());
                        }
                    }
                    capture.at("held",-1);n.hook.set(observed::event);n.observeRequests=true;
                    try(var round=helper.driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
                        var completed=round.start();assertEquals("PUBLISH_ACK",completed.kind());assertEquals(3,ordinal.get());
                        assertEquals(MembershipRoundDriver.State.READY,round.state());assertArrayEquals(completed.bytes(),round.readiness().bytes());
                        var context=owner.activationContext();assertEquals(7L,context.cut.get("index"));assertNull(context.catalog.get("active"));
                        assertEquals("COMPLETED",object(list(context.catalog.get("results")).getLast()).get("phase"));
                        Files.write(history.resolve("transition-round-result.json"),canonical(Map.of("status","PASS","kind","REMOVE","profile",size+"-REMOVE",
                            "activations",3,"internalReady",true,"publicReady",false,"originalBudgetSeconds",600),4096));
                    }
                    n.hook.set(point->{});capture.at("before-release",-1);
                    for(var received:held)received.close();held.clear();capture.at("released",-1);
                }catch(Exception | AssertionError failure) {
                    n.hook.set(point->{});capture.at("failed",-1);throw failure;
                }finally {
                    n.hook.set(point->{});for(var received:held)received.close();held.clear();
                }
            }
            capture.at("closed",-1);assertEquals(0,capture.budget.usage().leases());success=true;
        }finally {
            if(capture!=null)capture.save();
            if(history!=null && Files.exists(history))Files.move(history,raw.resolve("history"));
            Files.write(raw.resolve("result.json"),canonical(Map.of("profile",size+"-REMOVE","status",success?"PASS":"FAIL",
                "pressureVoter","node-2","sourceCopies",1,"learnerCopies",1,"admittedLearner",false),4096));
        }
    }
}
