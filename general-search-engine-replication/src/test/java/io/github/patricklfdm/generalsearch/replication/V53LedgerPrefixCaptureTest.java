package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53LedgerPrefixCaptureTest {
    @TempDir Path temp;
    @Test void actualFutureRecordingPromotionClearingAndReopenRetainEveryLedgerPrefix()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-ledger-prefix-component/run-"+UUID.randomUUID()));
        System.out.println("v53LedgerPrefixComponentEvidence="+raw.toAbsolutePath());
        var f=V53FutureRetentionTest.ready(Files.createDirectory(temp.resolve("group")),Files.createDirectory(raw.resolve("prerequisite")));
        var local=f.request.targets().getFirst();Path replica=local.replicaDirectory();
        var acks=new ArrayList<Decoded>();var owned=new HashSet<MembershipContext.Owned>();
        for(var target:f.request.targets())try(var owner=f.open(target,"original-checkpoints")) {
            var end=owner.applyCurrent(builder().configuration(),target.materialization());acks.add(end.endorsement().acknowledgement());owned.add(end.endorsement().owned());
        }
        var capture=new V53RemoveRetirementCapture(raw,raw.resolve("captures"),V53RemoveRetirementCapture.Mode.LEDGER);
        var events=new ArrayList<Map<String,Object>>();var cases=new ArrayList<Map<String,Object>>();
        var active=new ArrayList<Map<String,Object>>();
        f.observer=(target,operation,point)->{
            if(!target.identity().equals(local.identity()))return;
            int index=events.size();events.add(Map.of("node","node-1","event",point));
            String kind=V53RemoveRetirementCapture.ledgerKind(point);
            if(kind==null)return;
            boolean begin=point.endsWith("_BEFORE_WRITE") || Set.of("RETENTION_RECOVERY_ACTIVE_FORCED","FUTURE_RETENTION_RECOVERY_FORCED").contains(point);
            if(begin) {
                assertTrue(active.isEmpty());String name=String.format(Locale.ROOT,"case-%02d",cases.size());
                Path directory=Files.createDirectory(raw.resolve(name));V53JournalApplicationTest.copy(replica,directory.resolve("before"));
                var row=new TreeMap<String,Object>();row.put("name",name);row.put("kind",kind);row.put("start",index);
                row.put("mode",point.endsWith("_BEFORE_WRITE")?"write":"reseal");active.add(row);
            }
            capture.at("node-1",replica,point,index);
            if(Set.of("RETENTION_PARENT_FORCED","RETENTION_RECOVERY_PARENT_FORCED","FUTURE_RETENTION_PARENT_FORCED","FUTURE_RETENTION_RECOVERY_PARENT_FORCED").contains(point)) {
                assertEquals(1,active.size());var row=active.removeFirst();row.put("end",index);
                V53JournalApplicationTest.copy(replica,raw.resolve((String)row.get("name")).resolve("after"));cases.add(row);
            }
        };
        try {
            try(var owner=f.open(local,"record-two-future-peers")) {
                var target=owner.pendingPublication(owner.applyCurrent(builder().configuration(),local.materialization()));
                for(var peer:f.request.targets().subList(1,3))assertTrue(owner.retainFutureDispatch(peer.identity(),target).pending());
                new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
            }
            try(var owner=f.open(local,"promote-and-clear")) {
                owner.publishCurrent(owner.applyCurrent(builder().configuration(),local.materialization()),acks,owned,List.of());
                assertFalse(owner.futureRetentionState().pending());
            }
            try(var owner=f.open(local,"reopen-complete")){assertFalse(owner.futureRetentionState().pending());}
            assertTrue(active.isEmpty());assertEquals(0,f.resources.usage().leases());assertEquals(10,cases.size());
            byte[] encoded=canonical(events,1024*1024);Files.write(raw.resolve("events.json"),encoded);
            capture.finishProcess(f.result.root().manifestDigest(),2,"CLOSED",encoded);
            Files.write(raw.resolve("result.json"),canonical(Map.of("schema","gse-v53-ledger-prefix-component-v1","cases",cases,
                    "pid",ProcessHandle.current().pid(),"root",f.result.root().manifestDigest(),
                    "expectedBytes","conditional-transaction-snapshots","nativeCarriedProcess",false),16384));
            assertEquals(40L,object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096)).get("captures"));
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void incompleteLedgerWritesCannotBorrowVoteRenameCrashException()throws Exception {
        for(String phase:List.of("RETENTION","FUTURE_RETENTION")) {
            Path replica=Files.createDirectory(temp.resolve(phase));Files.write(replica.resolve("empty"),new byte[0]);
            var capture=new V53RemoveRetirementCapture(replica,temp.resolve("capture-"+phase),V53RemoveRetirementCapture.Mode.LEDGER);
            capture.at("node-1",replica,phase+"_BEFORE_WRITE",0);capture.at("node-1",replica,phase+"_RENAMED",1);
            assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
            assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
        }
    }
    @Test void completionAcksAndOtherLedgersCannotMasqueradeAsPeerOrFutureWrites()throws Exception {
        for(String point:List.of("FUTURE_RETENTION_ACK_BEFORE_RETURN","FUTURE_RETENTION_BEFORE_RETURN","FUTURE_RETENTION_PROMOTED",
                "FUTURE_RETENTION_CLEARED","LEARNER_RETENTION_FORCED","SELECTED_RETENTION_COMPLETED","RETENTION_FORGED"))
            assertNull(V53RemoveRetirementCapture.ledgerKind(point));
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(replica,temp.resolve("capture"),V53RemoveRetirementCapture.Mode.LEDGER);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"RETENTION_PREFIX_WRITTEN",0));
        capture.at("node-1",replica,"RETENTION_RECOVERY_ACTIVE_FORCED",1);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"FUTURE_RETENTION_BEFORE_WRITE",2));
        capture.at("node-1",replica,"RETENTION_RECOVERY_PARENT_FORCED",3);
        capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
    }
}
