package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import java.nio.file.*;
import java.util.*;

/** Internal boundary fixtures, explicitly separate from the public JVM matrix. */
public final class V51ResourceWorker {
    static Map<String,Object> inventory(Path path) throws Exception {
        var result=new TreeMap<String,Object>();
        try(var files=Files.walk(path)) {
            for(var file:files.filter(Files::isRegularFile).toList())result.put(path.relativize(file).toString(),Map.of("size",Files.size(file),"sha256",sha(Files.readAllBytes(file))));
        }
        return result;
    }
    static long size(Path path) throws Exception {return inventory(path).values().stream().mapToLong(v->number(object(v),"size")).sum();}
    static void save(Path path,Object value) throws Exception {Files.write(path,canonical(value));}
    static void saveInventory(Path path,Path directory) throws Exception {
        save(path,inventory(directory).entrySet().stream().map(e->Map.of("path",e.getKey(),"size",object(e.getValue()).get("size"),"sha256",object(e.getValue()).get("sha256"))).toList());
    }
    static Map<String,Object> reject(Runnable call) {
        try {call.run();throw new AssertionError("expected capacity rejection");}
        catch(AutomaticReplicationException e) {
            if(e.reason()!=AutomaticReplicationException.Reason.CAPACITY_EXCEEDED)throw e;
            return Map.of("reason",e.reason().name(),"message",e.getMessage());
        }
    }
    static ReplicationBounds bounds(long retained,long staging) {
        var b=ReplicationBounds.defaults();return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),retained,staging);
    }
    static AutomaticStore open(Path root,byte[] manifest,ReplicationBounds b,AutomaticStore.Faults faults) {
        return AutomaticStore.open(root.resolve("node-1"),manifest,"node-1",b,faults);
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String action=args[1];Path node=root.resolve("node-1");
        if(action.equals("reopen")) {
            var config=object(ReplicaJson.decode(Files.readAllBytes(root.resolve("limits.json")),65536));
            try(var store=open(root,Files.readAllBytes(node.resolve("manifest.gsr")),bounds(number(config,"retained"),number(config,"staging")),AutomaticStore.Faults.NONE)) {
                save(root.resolve("reopened.json"),store.status());
            }
            return;
        }
        Files.createDirectories(root);byte[] manifest=setup(root);long retained=8L<<30,staging=16L<<30;
        var result=new LinkedHashMap<String,Object>();result.put("case",action);result.put("execution","internal-resource-boundary");result.put("publicRuntime",false);result.put("pid",ProcessHandle.current().pid());
        byte[] request=null;var counts=new TreeMap<String,Long>();
        AutomaticStore.Faults faults=new AutomaticStore.Faults(){public void at(String event){counts.merge(event,1L,Long::sum);}};
        if(action.equals("retained-bytes"))retained=size(node)+promise(manifest,2).length;
        if(action.equals("transfer-staging"))staging=128L<<10;
        save(root.resolve("limits.json"),Map.of("retained",retained,"staging",staging));
        var b=bounds(retained,staging);
        try(var store=open(root,manifest,b,faults)) {
            if(action.equals("promise-count")) {
                for(int i=1;i<10_000;i++) {
                    var row=copy(decode(promise(manifest,3L*i-1),"PROMISE").value());row.put("incarnation",new UUID(0,i).toString());
                    store.promise(encode("PROMISE",row));
                }
                request=promise(manifest,29_999);result.put("limit",10_000L);
            } else if(action.equals("retained-bytes")) {store.promise(promise(manifest,2));request=promise(manifest,5);result.put("limit",retained);}
            else if(action.equals("entry-count")) {
                store.promise(promise(manifest,2));var entry=copy(decode(entry(manifest,1,null,9,new byte[0]),"ENTRY").value());
                entry.put("index",1_000_001L);entry.put("previousIndex",1_000_000L);entry.put("previousEpoch",2L);
                request=accept(manifest,encode("ENTRY",entry),2);result.put("limit",1_000_000L);
            } else if(action.equals("transfer-staging")) {
                store.promise(promise(manifest,2));
                var transfer=encode("TRANSFER",Map.of("manifestDigest",digest(manifest),"node","node-1","ballot",AutomaticRecovery.ballotOf(store.promised()),
                        "transferId","33333333-3333-3333-3333-333333333333","imageDigest","a".repeat(64),"imageBytes",staging,"receivedBytes",0L));
                store.beginTransfer(transfer);Files.write(root.resolve("request.gsr"),transfer);result.put("limit",staging);
            } else if(action.equals("epoch-overflow")) {store.promise(promise(manifest,Long.MAX_VALUE));result.put("limit",Long.MAX_VALUE);}
            else if(!action.equals("ancestry-count"))throw new IllegalArgumentException(action);
            if(request!=null)Files.write(root.resolve("request.gsr"),request);
            saveInventory(root.resolve("before.json"),node);save(root.resolve("before-status.json"),store.status());
            var beforeCounts=new TreeMap<>(counts);byte[] rejected=request;
            if(action.equals("promise-count")||action.equals("retained-bytes")) {
                result.put("rejection",reject(()->store.promise(rejected)));
                store.promise(store.promised().bytes()); // Exact retry must still fit; only re-force, no append.
                result.put("afterStatus",store.status());
            } else if(action.equals("entry-count"))result.put("rejection",reject(()->store.accept(rejected)));
            else if(action.equals("transfer-staging"))result.put("rejection",reject(()->store.transferChunk("33333333-3333-3333-3333-333333333333",0,new byte[]{1})));
            else if(action.equals("ancestry-count")) {
                var snapshot=copy(decode(unbase(samples().get("SNAPSHOT")),"SNAPSHOT").value());
                Object anchor=list(snapshot.get("anchors")).getFirst();snapshot.put("anchors",Collections.nCopies(1_000_001,anchor));
                save(root.resolve("ancestry-request.json"),Map.of("count",1_000_001L,"anchor",anchor));result.put("limit",1_000_000L);
                result.put("rejection",reject(()->encode("SNAPSHOT",snapshot)));
            } else {
                var probes=new ArrayList<Object>();
                for(long observed:new long[]{Long.MAX_VALUE-6,Long.MAX_VALUE-3,Long.MAX_VALUE})for(int rank=0;rank<3;rank++) {
                    var probe=new LinkedHashMap<String,Object>();probe.put("observed",observed);probe.put("rank",rank);
                    try {probe.put("next",AutomaticProtocol.nextEpoch(observed,rank));}
                    catch(AutomaticReplicationException e){if(e.reason()!=AutomaticReplicationException.Reason.CAPACITY_EXCEEDED)throw e;probe.put("reason",e.reason().name());}
                    probes.add(probe);
                }
                result.put("probes",probes);
            }
            result.put("eventsBefore",beforeCounts);result.put("eventsAfter",counts);
            saveInventory(root.resolve("after.json"),node);
        }
        result.put("status","PASS");save(root.resolve("result.json"),result);
    }
}
