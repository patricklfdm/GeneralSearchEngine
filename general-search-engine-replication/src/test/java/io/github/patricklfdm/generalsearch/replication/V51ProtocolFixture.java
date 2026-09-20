package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.nio.file.Files;
import java.nio.ByteBuffer;
import java.util.*;
import java.util.function.Predicate;

/** Deterministic action driver over three real, separately locked automatic stores. */
final class V51ProtocolFixture implements AutoCloseable {
    final Path root;
    final byte[] manifest;
    final Map<String,AutomaticProtocol> nodes=new LinkedHashMap<>();
    final List<AutomaticProtocol.Message> messages=new ArrayList<>(),dropped=new ArrayList<>();
    final List<AutomaticProtocol.Completed> outcomes=new ArrayList<>();
    final List<Map<String,Object>> publications=new ArrayList<>();
    final List<Map<String,Object>> trace=new ArrayList<>();
    final List<Map.Entry<String,AutomaticProtocol.Action>> held=new ArrayList<>();
    final ArrayDeque<AutomaticProtocol.Message> network=new ArrayDeque<>();
    Predicate<AutomaticProtocol.Message> loss=m->false;
    boolean holdReconstruction,holdPublication;
    long now,incarnation;

    V51ProtocolFixture(Path root) throws Exception {
        this.root=root;manifest=V51StorageFixture.setup(root);
        for(int i=1;i<=3;i++)open(i,AutomaticStore.Faults.NONE);
        pump();
    }
    void open(int i,AutomaticStore.Faults faults) {
        String node="node-"+i;
        var store=AutomaticStore.open(root.resolve(node),manifest,node,ReplicationBounds.defaults(),new AutomaticStore.Faults() {
            public void at(String event) throws java.io.IOException {
                faults.at(event);
                for(String kind:List.of("PROMISE","ACCEPT","PROOF"))if(event.equals(kind+"_AFTER_FORCE")) {
                    Path directory=root.resolve(node);
                    if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))
                        directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
                    String filename=kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr";
                    byte[] bytes=Files.readAllBytes(directory.resolve(filename));int offset=0,last=0;
                    while(offset<bytes.length) {last=offset;offset+=HEADER+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
                    trace.add(Map.of("event","FORCE","node",node,"kind",kind,"record",b64(Arrays.copyOfRange(bytes,last,offset))));
                }
            }
        });
        var protocol=new AutomaticProtocol(store,()->(i-1)*1000L,()->new UUID(5,++incarnation));
        nodes.put(node,protocol);protocol.start(now);
    }
    AutomaticProtocol node(int i) {return nodes.get("node-"+i);}
    void elect(int i) {now+=15_000+(i-1)*1000;node(i).tick(now);pump();}
    void stop(int i) {nodes.remove("node-"+i).close();}
    void advance(long target) {
        while(now<target) {
            now=Math.min(target,now+1000);
            for(var node:List.copyOf(nodes.values()))node.tick(now);
            pump();
        }
    }
    static byte[] project(AutomaticStore.Replay replay) {
        // Synthetic, deterministic opaque application port. No V4/query acceptance claim.
        var out=new ByteArrayOutputStream();out.writeBytes(unbase(replay.snapshot().value().get("application")));
        for(var entry:replay.entries())if(number(entry.value(),"operation")<=8)out.writeBytes(unbase(entry.value().get("payload")));
        return out.toByteArray();
    }
    void application(String owner,AutomaticProtocol.Action action) {
        var node=nodes.get(owner);
        if(action instanceof AutomaticProtocol.Reconstruct r)node.reconstructed(r.id(),project(r.replay()),null,now);
        else if(action instanceof AutomaticProtocol.Publish p) {
            publications.add(Map.of("node",owner,"ballot",b64(p.ballot().bytes()),"snapshot",b64(p.snapshot().bytes())));
            trace.add(Map.of("event","PUBLISH","node",owner,"ballot",b64(p.ballot().bytes()),"snapshot",b64(p.snapshot().bytes())));
            node.published(p.id(),null,now);
        }
    }
    void releaseApplications() {
        var pending=List.copyOf(held);held.clear();
        for(var task:pending)application(task.getKey(),task.getValue());
        pump();
    }
    void deliver(AutomaticProtocol.Message message) {
        var receiver=nodes.get(message.recipient());
        if(receiver!=null) {trace.add(Map.of("event","DELIVER","message",describe(message)));receiver.receive(message,now);}
        else if(!message.response()&&nodes.containsKey(message.sender()))nodes.get(message.sender()).transportFailed(message.id(),now);
    }
    void pump() {
        for(int step=0;step<10_000;step++) {
            boolean work=false;
            for(var item:List.copyOf(nodes.entrySet()))for(var action:item.getValue().drain()) {
                work=true;
                if(action instanceof AutomaticProtocol.Send send) {messages.add(send.message());network.add(send.message());trace.add(Map.of("event","SEND","message",describe(send.message())));}
                else if(action instanceof AutomaticProtocol.Completed completed) {
                    outcomes.add(completed);trace.add(Map.of("event","COMPLETE","node",item.getKey(),"request",completed.request(),"index",completed.index(),
                            "reason",completed.reason()==null?"SUCCESS":completed.reason().name(),"outcome",completed.outcome().name()));
                }
                else if(action instanceof AutomaticProtocol.Reconstruct&&holdReconstruction||action instanceof AutomaticProtocol.Publish&&holdPublication)
                    held.add(Map.entry(item.getKey(),action));
                else application(item.getKey(),action);
            }
            while(!network.isEmpty()) {
                work=true;var message=network.remove();
                if(loss.test(message))dropped.add(message);else deliver(message);
            }
            if(!work)return;
        }
        throw new AssertionError("protocol action driver did not settle");
    }
    List<AutomaticProtocol.Message> requests(AutomaticProtocol.Kind kind) {
        return messages.stream().filter(m->!m.response()&&m.kind()==kind).toList();
    }
    void submit(int node,long request,byte[] payload) {
        trace.add(Map.of("event","CALL","node","node-"+node,"request",request,"payload",b64(payload)));
        node(node).submit(request,1,payload,now);pump();
    }
    static Map<String,Object> describe(AutomaticProtocol.Message message) {
        var value=new LinkedHashMap<String,Object>();value.put("id",message.id());value.put("kind",message.kind().name());
        value.put("sender",message.sender());value.put("recipient",message.recipient());value.put("ballot",b64(message.ballot().bytes()));
        value.put("response",message.response());value.put("accepted",message.accepted());value.put("promised",message.promised()==null?null:b64(message.promised().bytes()));
        Object payload=message.payload();
        if(payload instanceof AutomaticRecords.Record record)payload=b64(record.bytes());
        else if(payload instanceof AutomaticRecovery.Basis basis)payload=describeBasis(basis);
        else if(payload instanceof List<?> bases)payload=bases.stream().map(b->describeBasis((AutomaticRecovery.Basis)b)).toList();
        else if(payload instanceof AutomaticProtocol.Pulse p)payload=Map.of("sequence",p.sequence(),"activated",p.activated(),"stage",p.stage(),"bytes",p.bytes());
        else if(payload instanceof Enum<?> reason)payload=reason.name();
        value.put("payload",payload);return value;
    }
    private static Map<String,Object> describeBasis(AutomaticRecovery.Basis basis) {
        return Map.of("basis",b64(basis.record().bytes()),"image",b64(basis.image().encoded().bytes()));
    }
    @Override public void close() {
        holdPublication=holdReconstruction=false;releaseApplications();
        for(var node:nodes.values())node.close();nodes.clear();
    }
}
