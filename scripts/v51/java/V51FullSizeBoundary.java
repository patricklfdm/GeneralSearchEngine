package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import io.github.patricklfdm.generalsearch.admission.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.Doc;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Isolated component qualification, not a public leader election or throughput test.
 * Uses the shipped storage/application/TCP implementations and public V4.4 bootstrap.
 * The controller schedules ballots explicitly; it never manufactures voter receipts.
 */
public final class V51FullSizeBoundary implements AutoCloseable {
    final Path root, group;
    final List<AutomaticReplicationGroupConfig<Integer,Doc>> configs;
    final AutomaticStore[] stores = new AutomaticStore[3];
    final AutomaticApplication<Integer,Doc>[] apps;
    final AutomaticTransport[] transports = new AutomaticTransport[3];
    final Map<String,Long>[] forces;
    final Record manifest;
    final UUID trace = UUID.randomUUID();
    final BufferedWriter events;
    long serial, message;
    Record ballot;

    @SuppressWarnings("unchecked")
    V51FullSizeBoundary(Path root) throws Exception {
        this.root=root;group=root.resolve("group");configs=V51MeasuredAutomatic.configs(group);
        manifest=decode(Files.readAllBytes(group.resolve("node-1/manifest.gsr")),"MANIFEST");
        apps=(AutomaticApplication<Integer,Doc>[])new AutomaticApplication<?,?>[3];
        forces=(Map<String,Long>[])new Map<?,?>[3];
        events=Files.newBufferedWriter(root.resolve("events.jsonl"),StandardOpenOption.CREATE_NEW);
        try {for(int i=0;i<3;i++) {
            final int n=i;forces[i]=new HashMap<>();
            stores[i]=AutomaticStore.open(group.resolve(node(i)),manifest.bytes(),node(i),configs.get(i).bounds(),new AutomaticStore.Faults(){
                public void at(String cut) throws IOException {
                    if(cut.endsWith("AFTER_FORCE")||cut.endsWith("BEFORE_ACK")||cut.startsWith("DELETE_AFTER"))
                        forces[n].put(cut,event("force",Map.of("node",node(n),"cut",cut)));
                }
            });
            apps[i]=new AutomaticApplication<>(V51RichWorkload.builder().configuration(),configs.get(i).materialization(),configs.get(i).bounds());
            apps[i].validate(manifest,configs.get(i).materialization());publish(i);
            transports[i]=new AutomaticTransport(manifest,node(i),configs.get(i).bounds(),request->handle(n,request),(cut,request,response)->{if(!response.isEmpty())event("transport",Map.of("node",node(n),"cut",cut,"request",b64(AutomaticWire.encode(request,manifest,1<<20)),"response",b64(AutomaticWire.encode(response,manifest,1<<20))));});
        }} catch(Exception|Error error) {try{close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    static String node(int i){return "node-"+(i+1);}
    synchronized long event(String kind,Map<String,Object> details) throws IOException {
        var row=new LinkedHashMap<String,Object>(details);row.put("event",kind);row.put("serial",++serial);row.put("nanos",System.nanoTime());
        events.write(new String(canonical(row),java.nio.charset.StandardCharsets.US_ASCII));events.newLine();events.flush();return serial;
    }
    void save(String name,byte[] bytes) throws IOException {Path p=root.resolve(name);Files.createDirectories(p.getParent());Files.write(p,bytes,StandardOpenOption.CREATE_NEW);}
    void publish(int i) {apps[i].publish(stores[i].provenSnapshot(apps[i].reconstruct(stores[i].replay())));}
    Record ballot(long epoch) {return decode(encode("PROMISE",Map.of("manifestDigest",manifest.digest(),"epoch",epoch,"proposer","node-1","incarnation",UUID.randomUUID().toString())),"PROMISE");}
    byte[] image(int i) {return apps[i].index()==stores[i].replay().through()?apps[i].encoder().snapshot():apps[i].checkpointImage(stores[i].replay());}
    Map<String,Object> handle(int i,Map<String,Object> request) {
        try {
            String type=text(request,"type");var p=object(request.get("payload"));var answer=new LinkedHashMap<>(p);var store=stores[i];
            switch(type) {
                case "PREPARE" -> {
                    var basis=store.prepare(AutomaticWire.ballot(request,manifest).bytes(),"node-1",image(i));
                    return AutomaticWire.reply(request,"PROMISE",Map.of("nonce",p.get("nonce"),"basis",b64(basis.record().bytes())));
                }
                case "BASIS_CHUNK" -> {
                    var b=decode(Files.readAllBytes(group.resolve(node(i)+"/basis/node-1/basis.gsr")),"BASIS");
                    int count=(int)Math.min(4096,number(b.value(),"imageBytes")-number(p,"offset"));
                    byte[] chunk=store.basisChunk("node-1",text(p,"basisId"),number(p,"offset"),count);
                    answer.put("action","DATA");answer.put("chunkBytes",(long)chunk.length);answer.put("chunk",b64(chunk));answer.put("chunkDigest",sha(chunk));
                }
                case "SNAPSHOT_OFFER" -> {
                    var meta=new LinkedHashMap<String,Object>();meta.put("manifestDigest",manifest.digest());meta.put("node",node(i));
                    meta.put("ballot",AutomaticRecovery.ballotOf(AutomaticWire.ballot(request,manifest)));meta.put("transferId",p.get("transferId"));
                    meta.put("imageBytes",p.get("imageBytes"));meta.put("imageDigest",p.get("imageDigest"));meta.put("receivedBytes",0L);
                    store.beginTransfer(encode("TRANSFER",meta));answer.put("response",true);
                }
                case "SNAPSHOT_CHUNK" -> {
                    store.transferChunk(text(p,"transferId"),number(p,"offset"),unbase(p.get("chunk")));
                    answer.put("action","ACK");answer.put("chunk","");
                }
                case "REJOIN_INSTALL" -> {
                    var transferred=store.completeTransfer(text(p,"transferId"));need(transferred.accepted()==null,"proven-only transfer");
                    store.installProven(transferred.snapshot());answer.put("response",true);
                }
                default -> throw new IllegalArgumentException(type);
            }
            return AutomaticWire.reply(request,type,answer);
        } catch(Exception e) {throw new IllegalStateException(e);}
    }
    Map<String,Object> exchange(int i,String type,Map<String,Object> payload) throws Exception {
        var request=AutomaticWire.message(manifest,ballot,"node-1",node(i),type,trace,++message,payload);
        long start=System.nanoTime();var response=transports[0].exchange(node(i),request).get(2,TimeUnit.SECONDS);
        AutomaticWire.correlated(request,response);
        event("wire",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20)),"response",b64(AutomaticWire.encode(response,manifest,1<<20)),"startNanos",start));
        return object(response.get("payload"));
    }
    AutomaticRecovery.Basis basis(int i,String name) throws Exception {
        Record descriptor;
        if(i==0)descriptor=stores[0].prepare(ballot.bytes(),"node-1",image(0)).record();
        else descriptor=decode(unbase(exchange(i,"PREPARE",Map.of("nonce",UUID.randomUUID().toString())).get("basis")),"BASIS");
        var bytes=new ByteArrayOutputStream();int length=(int)number(descriptor.value(),"imageBytes");
        for(int offset=0;offset<length;) {
            int count=Math.min(4096,length-offset);byte[] chunk;
            if(i==0)chunk=stores[0].basisChunk("node-1",text(descriptor.value(),"basisId"),offset,count);
            else chunk=unbase(exchange(i,"BASIS_CHUNK",Map.of("basisId",descriptor.value().get("basisId"),"action","REQUEST","offset",(long)offset,
                    "maxChunkBytes",4096L,"chunkBytes",0L,"chunk","","chunkDigest",sha(new byte[0]))).get("chunk"));
            need(chunk.length==count,"basis chunk extent");bytes.write(chunk);offset+=count;
        }
        save(name+"/"+node(i)+"-basis.gsr",descriptor.bytes());save(name+"/"+node(i)+"-image.gsr",bytes.toByteArray());
        return AutomaticRecovery.Basis.read(descriptor.bytes(),bytes.toByteArray(),manifest);
    }
    Record entry(int index) {
        var head=stores[0].head();byte[] payload=index==1?new byte[0]:apps[0].encoder().documents("UPDATE",List.of(V51RichWorkload.document(1+(index-2)%64,1+(index-2)/64,17)));
        var v=new LinkedHashMap<String,Object>();v.put("manifestDigest",manifest.digest());v.put("originEpoch",ballot.value().get("epoch"));v.put("originIncarnation",ballot.value().get("incarnation"));
        v.put("index",(long)index);v.put("operation",index==1?9L:2L);v.put("previousEpoch",head.originEpoch());v.put("previousIndex",(long)index-1);
        v.put("previousDigest",head.digest());v.put("payload",b64(payload));v.put("payloadDigest",sha(payload));return decode(encode("ENTRY",v),"ENTRY");
    }
    Record accept(Record entry) throws Exception {
        var v=new LinkedHashMap<String,Object>(ballot.value());v.put("entry",b64(entry.bytes()));v.put("entryDigest",entry.digest());
        var acceptance=decode(encode("ACCEPT",v),"ACCEPT");var receipts=new ArrayList<Map<String,Object>>();
        for(int i=0;i<2;i++) {
            String receipt=stores[i].accept(acceptance.bytes());
            event("accept",Map.of("node",node(i),"record",b64(acceptance.bytes()),"receipt",receipt,"force",forces[i].get("ACCEPT_AFTER_FORCE")));
            receipts.add(Map.of("voter",node(i),"digest",receipt));
        }
        v=new LinkedHashMap<>(ballot.value());v.put("index",entry.value().get("index"));v.put("entryDigest",entry.digest());
        v.put("previousDigest",entry.value().get("previousDigest"));v.put("receipts",receipts);return decode(encode("PROOF",v),"PROOF");
    }
    void prove(Record proof) throws Exception {
        for(int i=0;i<2;i++) {
            String receipt=stores[i].prove(proof.bytes());
            event("proof",Map.of("node",node(i),"record",b64(proof.bytes()),"receipt",receipt,"force",forces[i].get("PROOF_AFTER_FORCE")));
        }
    }
    void archive(String name) throws Exception {
        for(int i=0;i<3;i++) {
            Path source=group.resolve(node(i)),destination=root.resolve(name).resolve(node(i));
            try(var paths=Files.walk(source)){for(Path p:paths.toList())if(Files.isRegularFile(p))save(root.relativize(destination.resolve(source.relativize(p))).toString(),Files.readAllBytes(p));}
        }
        event("archive",Map.of("name",name));
    }
    static List<Object> viewDocuments(SearchEngine<Integer,Doc> engine) {return engine.search(d->true).stream().sorted(Comparator.comparingInt(Doc::id)).map(d->(Object)List.of(d.id(),d.title(),d.category(),d.price(),d.body())).toList();}
    List<Object> documents(int i) {return apps[i].readLocal(V51FullSizeBoundary::viewDocuments);}
    void run() throws Exception {
        ballot=ballot(2);for(var s:stores)s.promise(ballot.bytes());
        for(int index=1;index<=511;index++)prove(accept(entry(index)));
        for(int i=0;i<2;i++)publish(i);
        Record tail=entry(512);accept(tail); // Real chosen acceptance, deliberately no commit proof yet.
        ballot=ballot(5);var pair=List.of(basis(0,"pending-basis"),basis(1,"pending-basis"));
        for(int i=0;i<2;i++) {
            var selected=stores[i].select(pair);need(Arrays.equals(unbase(selected.record().value().get("nextEntry")),tail.bytes()),"same-slot selection");
            save("selected/"+node(i)+".gsr",selected.record().bytes());stores[i].installSelected();
        }
        archive("before-reproposal");
        var captured=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var reader=Executors.newSingleThreadExecutor()) {
            var pinned=reader.submit(()->apps[1].readLocal(engine->{
                var before=viewDocuments(engine);
                try {event("pin-captured",Map.of("index",apps[1].index(),"documents",before));captured.countDown();
                    need(release.await(60,TimeUnit.SECONDS),"pin release deadline");
                    var after=viewDocuments(engine);need(before.equals(after),"pinned view changed");
                    event("pin-released",Map.of("index",apps[1].index(),"documents",after));return after;
                }catch(Exception e){throw new IllegalStateException(e);}
            }));
            try {
                need(captured.await(5,TimeUnit.SECONDS),"pin capture deadline");
                prove(accept(tail));publish(0);
                Record complete=stores[0].provenSnapshot(image(0));save("snapshot-512.gsr",complete.bytes());
                stores[0].checkpoint(unbase(complete.value().get("application")));stores[1].installProven(complete);
                archive("two-generations");
                ballot=ballot(8);basis(0,"full-basis");basis(1,"full-basis");stores[2].promise(ballot.bytes());
                byte[] transfer=AutomaticRecovery.image(manifest,complete,null);save("transfer-image.gsr",transfer);
                String id=UUID.randomUUID().toString();exchange(2,"SNAPSHOT_OFFER",Map.of("transferId",id,"imageBytes",(long)transfer.length,"imageDigest",digest(transfer),"response",false));
                for(int offset=0;offset<transfer.length;) {
                    int count=Math.min(4096,transfer.length-offset);byte[] chunk=Arrays.copyOfRange(transfer,offset,offset+count);
                    exchange(2,"SNAPSHOT_CHUNK",Map.of("transferId",id,"action","DATA","offset",(long)offset,"maxChunkBytes",4096L,"chunkBytes",(long)count,"chunk",b64(chunk),"chunkDigest",sha(chunk)));offset+=count;
                }
                exchange(2,"REJOIN_INSTALL",Map.of("transferId",id,"imageDigest",digest(transfer),"response",false));publish(2);
                var sources=List.of(stores[0].recoverySource(),stores[1].recoverySource());
                for(int i=0;i<3;i++){stores[i].establishRecoveryFloor(i==2?List.of(sources.getFirst(),stores[2].recoverySource()):sources);stores[i].cleanup();}
                archive("after-cleanup");
            } finally {release.countDown();}
            pinned.get(5,TimeUnit.SECONDS);
        }
        publish(1);
        for(int i=0;i<3;i++)event("final-read",Map.of("node",node(i),"index",apps[i].index(),"sequence",apps[i].sequence(),"documents",documents(i)));
        for(int i=0;i<3;i++){transports[i].close();transports[i]=null;apps[i].close();apps[i]=null;stores[i].close();stores[i]=null;}
        for(int i=0;i<3;i++) {
            stores[i]=AutomaticStore.open(group.resolve(node(i)),manifest.bytes(),node(i),configs.get(i).bounds(),AutomaticStore.Faults.NONE);
            apps[i]=new AutomaticApplication<>(V51RichWorkload.builder().configuration(),configs.get(i).materialization(),configs.get(i).bounds());publish(i);
            event("reopened",Map.of("node",node(i),"index",apps[i].index(),"sequence",apps[i].sequence(),"documents",documents(i)));
        }
    }
    public void close() throws Exception {
        try {for(var t:transports)if(t!=null)t.close();}
        finally {try{for(var a:apps)if(a!=null)a.close();}finally{try{for(var s:stores)if(s!=null)s.close();}finally{events.close();}}}
    }
    public static void main(String[] args) throws Exception {try(var run=new V51FullSizeBoundary(Path.of(args[0]))){run.run();}}
}
