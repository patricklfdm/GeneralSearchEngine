package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** The leader owns its listener, journal and automatic service in a fresh JVM.
 * Every observation is acknowledged by the parent before the boundary returns.
 * This pipe is instrumentation only; protocol traffic uses the real TCP link. */
public final class V53NodeProcessWorker {
    @FunctionalInterface interface Sink {void accept(String action,Object value)throws IOException;}
    static MembershipNodeOwner.Hooks hooks(String name,int life,Sink sink) {
        var installation=new AtomicLong(life-1);
        return new MembershipNodeOwner.Hooks(event->sink.accept("event",Map.of("node",name,"incarnation",life,"event",event)),
            (event,request,response)->{
                if(event.equals("BEFORE_REQUEST_WRITE"))sink.accept("event",Map.of("node",name,"incarnation",life,"event","NETWORK_SEND",
                        "request",request.digest(),"kind",request.kind(),"bytes",Base64.getEncoder().encodeToString(request.bytes())));
                if(event.equals("AFTER_REQUEST_READ"))sink.accept("event",Map.of("node",name,"incarnation",life,"event","NETWORK_REQUEST","request",request.digest(),"kind",request.kind()));
                if(event.equals("BEFORE_REQUEST_WRITE") && request.kind().equals("PUBLISH"))sink.accept("event",Map.of("node",name,"event","PUBLICATION_SEND_BOUNDARY","request",request.digest()));
                if(event.equals("AFTER_RESPONSE_READ"))sink.accept("event",Map.of("node",name,"incarnation",life,"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
                if(event.equals("BEFORE_RESPONSE_WRITE")) {
                    var wire=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));wire.put("withheld",false);
                    sink.accept("response",Map.of("wire",wire,"event",Map.of("node",name,"incarnation",life,"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest())));
                }
            },(event,record)->{
                sink.accept("event",Map.of("node",name,"incarnation",life,"event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                if(event.equals("INSTALLED"))sink.accept("installed",Map.of("number",installation.incrementAndGet(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
            },(event,record,voters)->{
                if(event.equals("FUTURE_QUORUM_COMPLETE"))sink.accept("event",Map.of("node",name,"event",event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                if(event.equals("APPLIED") || event.equals("PUBLISHED"))sink.accept("snapshot",event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));
            });
    }
    static final class Pipe implements Sink {
        final BufferedReader input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
        @Override public synchronized void accept(String action,Object value)throws IOException {
            System.out.println(new String(canonical(Map.of("action",action,"value",value),8*1024*1024),StandardCharsets.UTF_8));System.out.flush();
            if(!"ACK".equals(input.readLine()))throw new IOException("parent observation acknowledgement absent");
        }
    }
    static void crash(Pipe sink,String point,String mode)throws IOException {
        sink.accept("cut",Map.of("name",point,"mode",mode,"pid",ProcessHandle.current().pid()));
        if(mode.equals("halt"))Runtime.getRuntime().halt(73);
        if(!mode.equals("kill"))throw new AssertionError("unknown process fault");
        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
        throw new AssertionError("external SIGKILL absent");
    }
    public static void main(String[] args)throws Exception {
        Path spec=Path.of(args[0]);int life=Integer.parseInt(args[1]);String mode=args[2],point=args.length==4?args[3]:"AFTER_DATA_RETURN";
        if(!Set.of("AFTER_DATA_RETURN","ACCEPT_PARENT_FORCED","PROOF_PARENT_FORCED","ACCEPT_RENAMED","PROOF_RENAMED").contains(point))throw new AssertionError("unknown crash boundary");
        var values=object(parse(Files.readAllBytes(spec),65536));var paths=list(values.get("nodes")).stream().map(MembershipFormat::object).toList();
        var identities=new ArrayList<MembershipIdentity>();
        for(var path:paths)identities.add(MembershipContext.identity(object(decode(Files.readAllBytes(Path.of((String)path.get("replica")).resolve("node.gsr")),"records","NODE").value().get("identity"))));
        Path replica=Path.of((String)paths.getFirst().get("replica")),materialization=Path.of((String)paths.getFirst().get("application"));
        var root=decode(Files.readAllBytes(replica.resolve("root.gsr")),"records","ROOT");
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var bounds=ReplicationBounds.defaults();var config=new MembershipReplicaConfig<>(history,identities.getFirst(),identities.subList(1,3),replica,
                storage(materialization,2),bounds,AutomaticLeadershipPolicy.forBounds(bounds));
        Path scratch=Path.of((String)values.get("scratch"));var sink=new Pipe();
        sink.accept("started",Map.of("pid",ProcessHandle.current().pid(),"life",life,"mode",mode));
        var original=hooks("node-1",life,sink);var activeSlot=new AtomicLong();
        var instrumented=new MembershipNodeOwner.Hooks(event->{
            original.storage().at(event);
            if(life==1 && activeSlot.get()==2 && event.equals(point))crash(sink,point,mode);
        },original.network(),(event,record)->{
            if(event.equals("SLOT_BEGIN"))activeSlot.set(number(record.value().get("index")));
            original.round().at(event,record);
        },original.slot());
        var node=new MembershipNodeOwner<>(config,builder().configuration(),scratch.resolve("incoming"),scratch.resolve("outgoing"),System::nanoTime,V53NodeOwnerNetworkTest.BUDGET,instrumented);
        // A real halt/kill bypasses this finally and every owner close method.
        try {
            node.open();if(node.serviceState().orElseThrow()!=MembershipAutomaticOwner.State.NEW)throw new AssertionError("restored READY");
            try{node.readiness();throw new AssertionError("readiness without fresh barrier");}catch(IllegalArgumentException expected){}
            sink.accept("event",Map.of("node","node-1","incarnation",life,"event","NODE_OPEN"));
            sink.accept("opened",life); // Parent starts unchanged follower owners before acknowledging life 1.
            node.start().await(180,TimeUnit.SECONDS);sink.accept("snapshot",life==1?"first-ready":"second-ready");
            int id=99+life;byte[] payload;
            try(var encoder=new ReplicaApplication<>(builder().configuration(),config.materialization(),bounds)) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(id,"node-owner-"+id))));
            }
            if(!node.submit("DATA",payload).await(180,TimeUnit.SECONDS).kind().equals("PUBLISH_ACK"))throw new AssertionError("missing DATA publication");
            if(life==1) {
                if(!point.equals("AFTER_DATA_RETURN"))throw new AssertionError("declared write boundary not reached");
                crash(sink,point,mode);
            }
        }finally{node.close();}
        if(node.usage().leases()!=0)throw new AssertionError("node drain leak");
        sink.accept("event",Map.of("node","node-1","incarnation",life,"event","NODE_CLOSED"));sink.accept("closed",life);
    }
}
