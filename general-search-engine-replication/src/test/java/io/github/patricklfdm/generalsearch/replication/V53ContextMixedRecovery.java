package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Additional admission and interrupted cleanup checks on the actual mixed-owner chain. */
final class V53ContextMixedRecovery {
    static final List<String> ACCEPT_CUTS=List.of("CONTEXT_ACCEPT_SUCCESSOR_FORCED","CONTEXT_REDUNDANT_DELETED","CONTEXT_ACCEPT_CLEARED",
            "FLOOR_RELEASE_AUTHORITY_WRITTEN","FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_FILE_DELETED","FLOOR_RELEASE_AUTHORITY_CLEARED","CONTEXT_ACCEPT_BEFORE_RETURN");
    static final List<String> SOURCE_CUTS=List.of("SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_BEFORE_RETURN");
    static void run(V53ContextInstallationLifetimeTest driver,Path reference,Path temp)throws Exception {
        Path raw=Path.of("target/v53-context-mixed-recovery/run-"+UUID.randomUUID());Files.createDirectories(raw);driver.snapshot(reference,raw.resolve("reference"));
        System.out.println("v53ContextMixedRecoveryEvidence="+raw.toAbsolutePath());
        guards(driver,reference,temp);
        var rows=new ArrayList<Map<String,Object>>();var f=driver.reference.seed();
        for(boolean acceptance:List.of(true,false))for(String point:acceptance?ACCEPT_CUTS:SOURCE_CUTS) {
            int n=acceptance?1:2;Path group=Files.createDirectory(temp.resolve(point)),node=group.resolve("node-"+n),row=Files.createDirectory(raw.resolve(point));
            Path seed=reference.resolve((acceptance?"round-24/source-retired":"retired")+"/node-"+n);driver.snapshot(seed,node);
            var original=MembershipPendingAccept.decode(Files.readAllBytes(seed.resolve("pending.accept")));String sourceId=(String)original.promise().value().get("basisId");
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resumed=new ArrayList<String>();boolean[] armed={false};
            try(var owner=driver.open(group,n,e->{if(armed[0]){first.add(e);if(e.equals(point))throw new IOException("first cut");}})) {
                armed[0]=true;assertEquals("first cut",assertThrows(IOException.class,()->{if(acceptance)owner.acceptRetainedCurrent(f.entry(),f.payload());else owner.retireSource(sourceId);}).getMessage());
            }
            assertEquals(0,f.fixture().f.resources.usage().leases());driver.snapshot(node,row.resolve("first"));
            String recoveryPoint=acceptance?"ACCEPT_ACTIVE_FORCED":"CONTEXT_SOURCE_PARENT_FORCED";
            assertEquals("second cut",assertThrows(IOException.class,()->{
                try(var owner=driver.open(group,n,e->{second.add(e);if(e.equals(recoveryPoint))throw new IOException("second cut");})) {
                    if(acceptance)owner.acceptRetainedCurrent(f.entry(),f.payload());else if(Files.exists(node.resolve("sources/"+sourceId)))owner.retireSource(sourceId);
                }
            }).getMessage());
            assertEquals(0,f.fixture().f.resources.usage().leases());driver.snapshot(node,row.resolve("second"));
            try(var owner=driver.open(group,n,resumed::add)) {
                resumed.add("OPEN_RETURNED");
                if(acceptance){var ack=owner.acceptRetainedCurrent(f.entry(),f.payload());resumed.add("EXPLICIT_ACCEPT_RETURNED");assertEquals(ack,owner.acceptRetainedCurrent(f.entry(),f.payload()));resumed.add("EXPLICIT_ACCEPT_RETURNED");}
                else {if(Files.exists(node.resolve("sources/"+sourceId)))owner.retireSource(sourceId);owner.retainPendingContext();resumed.add("EXPLICIT_RETIRE_RETURNED");}
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,f.fixture().f.resources.usage().leases());driver.snapshot(node,row.resolve("final"));
            assertEquals(V53BootstrapProgressResumeTest.safeFiles(reference.resolve((acceptance?"accepted":"predecessors-retired")+"/node-"+n)),V53BootstrapProgressResumeTest.safeFiles(node));
            V53JournalContextTest.noAck(first);V53JournalContextTest.noAck(second);
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"second",second,"resumed",resumed),262144));
            rows.add(Map.of("cut",point,"node",n,"status","PASS","operation",acceptance?"accept":"source-retirement"));
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-mixed-recovery-v1","status","PASS","cases",rows,"guardVariants",14,"freshProcesses",false,"runtimeEnabled",false),16384));
    }
    static MembershipSourcePacket packet(MembershipSourcePacket base,Map<String,byte[]> objects) {
        var value=new TreeMap<>(base.capsule().value());value.put("inventory",hash(MembershipSourcePacket.index(objects,base.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),"records","CAPSULE"),objects,base.images()));
    }
    static void guards(V53ContextInstallationLifetimeTest driver,Path reference,Path temp)throws Exception {
        Path group=Files.createDirectory(temp.resolve("guards"));driver.snapshot(reference.resolve("retired/node-1"),group.resolve("node-1"));
        var before=V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-1"));MembershipPendingContext.Reconstructed original;
        try(var owner=driver.open(group,1,e->{})){original=owner.retainPendingContext();
            assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(original.vote().entry(),new byte[0]));
        }
        var f=driver.reference.seed().fixture().f;Path node=group.resolve("node-1");
        var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");Path gen=node.resolve("generations/"+selector.value().get("generation"));
        var promise=decode(Files.readAllBytes(gen.resolve("promise.gsr")),"records","PROMISE");var basis=decode(Files.readAllBytes(gen.resolve("basis.gsr")),"records","BASIS");var selected=decode(Files.readAllBytes(gen.resolve("selected.gsr")),"records","SELECTED");
        try(var current=new MembershipCurrentGeneration(node,f.initial.application.f.f.f.root(),V53DeclarationsTest.node(1),f.resources,List.of(promise),List.of(basis),List.of(selected),
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),e->{},true)) {
            var old=original.vote();assertEquals(current.accepted,MembershipContextTail.selected(original,current.capsule.packet,current.accepted).digest());
            assertFalse(MembershipContextTail.retained(current,old.accept(),null));assertTrue(MembershipContextTail.retained(current,old.accept(),original));
            var fields=new TreeMap<>(old.accept().value());fields.put("ballot",promise.value().get("ballot"));var accepted=decode(encode("records","ACCEPT",fields),"records","ACCEPT");
            var successor=new MembershipPendingAccept.Vote(selector,promise,selected,old.entry(),accepted,old.payload());
            assertTrue(MembershipContextTail.successor(current,old.accept(),successor));assertFalse(MembershipContextTail.successor(current,old.accept(),null));
            assertFalse(MembershipContextTail.successor(current,old.accept(),old));
            var badSelected=new TreeMap<>(selected.value());badSelected.put("nextEntry","0".repeat(64));
            var foreign=new MembershipPendingAccept.Vote(selector,promise,decode(encode("records","SELECTED",badSelected),"records","SELECTED"),old.entry(),accepted,old.payload());
            assertFalse(MembershipContextTail.successor(current,old.accept(),foreign));
            var foreignPromise=new TreeMap<>(promise.value());foreignPromise.put("basisId",UUID.randomUUID().toString());
            assertFalse(MembershipContextTail.successor(current,old.accept(),new MembershipPendingAccept.Vote(selector,
                    decode(encode("records","PROMISE",foreignPromise),"records","PROMISE"),selected,old.entry(),accepted,old.payload())));

            for(String field:List.of("root","authority","entry","index","ballot")) {
                var changed=new TreeMap<>(old.accept().value());changed.put(field,field.equals("index")?3L:field.equals("ballot")?driver.ballot(19):"0".repeat(64));
                var bad=decode(encode("records","ACCEPT",changed),"records","ACCEPT");var objects=new TreeMap<String,byte[]>();for(String h:current.capsule.packet.objectNames())objects.put(h,current.capsule.packet.objectBytes(h));objects.put(bad.digest(),bad.bytes());
                var badPacket=packet(current.capsule.packet,objects);assertThrows(IllegalArgumentException.class,()->MembershipContextTail.selected(original,badPacket,bad.digest()));
            }
            for(byte[] absent:List.of(old.accept().bytes(),old.entry().bytes(),old.payload())) {
                var objects=new TreeMap<String,byte[]>();for(String h:current.capsule.packet.objectNames())objects.put(h,current.capsule.packet.objectBytes(h));objects.remove(hash(absent));
                var missing=packet(current.capsule.packet,objects);assertThrows(IllegalArgumentException.class,()->MembershipContextTail.selected(original,missing,current.accepted));
            }
        }
        assertEquals(0,f.resources.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
    }
    private V53ContextMixedRecovery() {}
}
