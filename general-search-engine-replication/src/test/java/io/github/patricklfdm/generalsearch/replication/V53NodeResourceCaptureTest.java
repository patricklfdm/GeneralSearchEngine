package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NodeResourceCaptureTest {
    @TempDir Path temp;
    @Test void optionalFileObserverSharesExactEventBytesAndOriginalOwnerRegistration()throws Exception {
        var helper=new V53NodeOwnerTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            Path output=temp.resolve("observed-prefix"),prefix=temp.resolve("file-prefix"),floor=temp.resolve("floor-prefix");
            Path campaign=temp.resolve("campaign-prefix"),vote=temp.resolve("vote-prefix"),completion=temp.resolve("completion-prefix"),ledger=temp.resolve("ledger-prefix");
            var capture=new V53NodeResourceCapture(output,f.group.fixture.result.root().manifestDigest(),2,(a,v)->{},prefix,floor,campaign,vote,completion,ledger);
            var node=observed(f,V53NodeOwnerTest.hooks(event->capture.accept("event",Map.of("node","node-1","event",event)),MembershipTransport.Events.NONE));
            var config=f.config(ReplicationBounds.defaults());
            assertThrows(IllegalArgumentException.class,()->capture.register(config.localIdentity(),node));
            capture.register(config.localIdentity(),node,config.replicaDirectory());node.open();capture.closeOwner(node);capture.save("CLOSED");
            var resources=object(parse(Files.readAllBytes(output.resolve("index.json")),16384));
            var files=object(parse(Files.readAllBytes(prefix.resolve("collection.json")),4096));
            for(String key:List.of("root","life","pid","terminal","eventsSha256"))assertEquals(resources.get(key),files.get(key));
            assertEquals(V53RemoveRetirementCapture.PROCESS_SCHEMA,files.get("schema"));
            var floors=object(parse(Files.readAllBytes(floor.resolve("collection.json")),4096));
            for(String key:List.of("root","life","pid","terminal","eventsSha256"))assertEquals(resources.get(key),floors.get(key));
            assertEquals(V53RemoveRetirementCapture.PROCESS_FLOOR_SCHEMA,floors.get("schema"));
            for(var extra:Map.of(campaign,V53RemoveRetirementCapture.PROCESS_CAMPAIGN_SCHEMA,vote,V53RemoveRetirementCapture.PROCESS_VOTE_SCHEMA,completion,V53RemoveRetirementCapture.PROCESS_COMPLETION_SCHEMA,ledger,V53RemoveRetirementCapture.PROCESS_LEDGER_SCHEMA).entrySet()) {
                var collection=object(parse(Files.readAllBytes(extra.getKey().resolve("collection.json")),4096));
                for(String key:List.of("root","life","pid","terminal","eventsSha256"))assertEquals(resources.get(key),collection.get(key));
                assertEquals(extra.getValue(),collection.get("schema"));
            }
        }
    }
    static MembershipNodeOwner<Integer,Doc> observed(V53NodeOwnerTest.Fixture f,MembershipNodeOwner.Hooks hooks) {
        var node=new MembershipNodeOwner<>(f.config(ReplicationBounds.defaults()),builder().configuration(),
                f.scratch.resolve("observed-in"),f.scratch.resolve("observed-out"),System::nanoTime,TimeUnit.SECONDS.toNanos(180),hooks,true);
        f.nodes.add(node);return node;
    }
    @Test void realNodeUsesSameLimitsAndOnlyObservedBudgetsExposeTraces()throws Exception {
        var helper=new V53NodeOwnerTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var normal=f.node();assertThrows(IllegalArgumentException.class,normal::resourceCheckpoint);normal.close();
            var node=observed(f,MembershipNodeOwner.Hooks.NONE);assertEquals(0,node.resourceCheckpoint().sequence());
            var initial=node.resourceObservations();assertEquals(MembershipResources.METADATA_LIMIT,initial.metadataLimit());
            assertEquals(ReplicationBounds.defaults().maxSnapshotStagingBytes(),initial.stagingLimit());
            assertEquals(MembershipResources.QUEUE_LIMIT,initial.queueLimit());node.open();
            assertEquals(node.usage(),node.resourceCheckpoint().usage());assertTrue(node.usage().leases()>0);
            node.close();assertEquals(0,node.resourceObservations().current().leases());assertFalse(node.resourceObservations().truncated());
            assertFalse(node.resourceObservations().failed());
        }
    }
    @Test void captureBindsOriginalCallbacksAndRealSuccessfulClose()throws Exception {
        var helper=new V53NodeOwnerTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            Path output=temp.resolve("observed");var sent=new ArrayList<String>();
            var capture=new V53NodeResourceCapture(output,f.group.fixture.result.root().manifestDigest(),2,(action,value)->sent.add(action));
            var node=observed(f,V53NodeOwnerTest.hooks(event->capture.accept("event",Map.of("node","node-1","event",event)),MembershipTransport.Events.NONE));
            capture.register(f.config(ReplicationBounds.defaults()).localIdentity(),node);node.open();
            assertThrows(IllegalArgumentException.class,()->capture.save("CLOSED"));
            capture.closeOwner(node);assertThrows(IllegalArgumentException.class,()->capture.closeOwner(node));capture.save("CLOSED");
            var index=object(parse(Files.readAllBytes(output.resolve("index.json")),16384));assertEquals("CLOSED",index.get("terminal"));
            byte[] events=Files.readAllBytes(output.resolve("events.json"));assertEquals(hash(events),index.get("eventsSha256"));
            assertEquals(sent.size(),list(parse(events,1024*1024)).size());
            var closes=list(parse(Files.readAllBytes(output.resolve("closes.json")),65536));assertEquals(2,closes.size());
            assertEquals("BEGIN",object(closes.getFirst()).get("event"));assertEquals("RETURNED",object(closes.getLast()).get("event"));
            assertThrows(IllegalArgumentException.class,()->capture.save("CLOSED"));
        }
    }
    @Test void crashCaptureIsWrittenBeforeCutAndNeverClaimsDrain()throws Exception {
        var helper=new V53NodeOwnerTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            Path output=temp.resolve("crashed");
            var capture=new V53NodeResourceCapture(output,f.group.fixture.result.root().manifestDigest(),1,(action,value)->{
                if(action.equals("cut"))assertTrue(Files.exists(output.resolve("index.json")));
            });
            var node=observed(f,MembershipNodeOwner.Hooks.NONE);capture.register(f.config(ReplicationBounds.defaults()).localIdentity(),node);node.open();
            capture.accept("event",Map.of("node","node-1","event","NODE_OPEN"));capture.accept("cut",Map.of("name","unit-boundary"));
            var index=object(parse(Files.readAllBytes(output.resolve("index.json")),16384));assertEquals("CUT_PREFIX",index.get("terminal"));
            assertTrue(node.usage().leases()>0);assertEquals(List.of(),parse(Files.readAllBytes(output.resolve("closes.json")),65536));
            // Later observations remain protocol observations, but cannot be
            // silently appended to the already retained resource prefix.
            byte[] before=Files.readAllBytes(output.resolve("events.json"));capture.accept("event",Map.of("node","node-1","event","LATER"));
            assertArrayEquals(before,Files.readAllBytes(output.resolve("events.json")));node.close();
        }
    }
    @Test void registrationRejectsReusedOpenedOrUnobservedOwners()throws Exception {
        var helper=new V53NodeOwnerTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var capture=new V53NodeResourceCapture(temp.resolve("capture"),f.group.fixture.result.root().manifestDigest(),1,(a,v)->{});
            var identity=f.config(ReplicationBounds.defaults()).localIdentity();var normal=f.node();
            assertThrows(IllegalArgumentException.class,()->capture.register(identity,normal));normal.close();
            var node=observed(f,MembershipNodeOwner.Hooks.NONE);capture.register(identity,node);
            assertThrows(IllegalArgumentException.class,()->capture.register(identity,node));node.open();
            var other=new V53NodeResourceCapture(temp.resolve("other"),f.group.fixture.result.root().manifestDigest(),1,(a,v)->{});
            assertThrows(IllegalArgumentException.class,()->other.register(identity,node));
            assertThrows(IllegalArgumentException.class,()->capture.accept("event",Map.of("node","node-9","event","OPEN")));
        }
    }
}
