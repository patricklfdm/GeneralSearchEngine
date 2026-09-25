package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.admission.*;
import io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.Doc;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Owned public rich voter. Hooks observe bytes or inject declared faults only. */
public final class V51FullSizeRuntime {
    final Path root, trace, signals;
    final String node;
    final int generation;
    final AutomaticRecords.Record manifest;
    final ThreadLocal<String> call=new ThreadLocal<>();
    long order;
    V51FullSizeRuntime(Path root,int ordinal,int generation) throws Exception {
        this.root=root;this.node="node-"+ordinal;this.generation=generation;
        trace=root.resolve(node+"-g"+generation+"-trace.jsonl");signals=root.resolve(node+"-g"+generation+"-signals.jsonl");
        manifest=decode(Files.readAllBytes(root.resolve(node+"/manifest.gsr")),"MANIFEST");
    }
    synchronized void record(String name,Map<String,Object> values) throws IOException {
        var row=new LinkedHashMap<>(values);row.put("event",name);row.put("order",++order);row.put("node",node);
        row.put("generation",generation);row.put("pid",ProcessHandle.current().pid());row.put("localNanos",System.nanoTime());
        row.put("manifestDigest",manifest.digest());row.put("groupId",manifest.value().get("groupId"));
        if(name.equals("PUBLIC_READ_INVOKE")){need(call.get()!=null,"unowned public read");row.put("opId",call.get());}
        V51CloudJournal.append(trace,row);
        if(Set.of("CUT_REACHED","CUT_RELEASED","REJOIN_INSTALLED","RECOVERY_FLOOR","STARTED","CLOSED","GENERATION_PAIR").contains(name)
                ||name.equals("FORCE")&&values.get("kind").equals("PROMISE")) {
            var signal=new LinkedHashMap<>(row);signal.remove("local");signal.remove("remote");signal.remove("snapshot");signal.remove("snapshots");
            Files.writeString(signals,new String(canonical(signal),StandardCharsets.US_ASCII)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
    }
    void event(String name,Map<String,Object> values) throws IOException {
        record(name,values);cut(name);
    }
    void cut(String name) throws IOException {
        Path arm=root.resolve(node+"-arm.txt");String mode;
        synchronized(this) {
            if(!Files.exists(arm))return;var lines=Files.readAllLines(arm);
            if(!lines.getFirst().equals(name))return;mode=lines.get(1);Files.delete(arm);
            record("CUT_REACHED",Map.of("cut",name,"mode",mode));
        }
        if(mode.equals("halt")){V51CloudJournal.closeAll();Runtime.getRuntime().halt(71);}
        need(mode.equals("pause"),"owned cut mode");Path release=root.resolve(node+"-release");long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(60);
        try {while(!Files.exists(release)&&System.nanoTime()<deadline)Thread.sleep(10);need(Files.deleteIfExists(release),"pin release deadline");}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
        record("CUT_RELEASED",Map.of("cut",name));
    }
    byte[] last(String kind) throws IOException {
        Path directory=root.resolve(node);
        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
        byte[] bytes=Files.readAllBytes(directory.resolve(kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr"));
        int offset=0,last=0;while(offset<bytes.length){last=offset;offset+=48+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
        return Arrays.copyOfRange(bytes,last,offset);
    }
    void install() {
        var faults=new AutomaticStore.Faults(){public void at(String name)throws IOException {
            for(String kind:List.of("PROMISE","ACCEPT","PROOF"))if(name.equals(kind+"_AFTER_FORCE"))record("FORCE",Map.of("kind",kind,"record",b64(last(kind))));
            if(name.equals("SELECTOR_BEFORE_ACK")) {
                Path a=root.resolve(node+"/generation-a/snapshot.gsr"),b=root.resolve(node+"/generation-b/snapshot.gsr");
                if(Files.isRegularFile(a)&&Files.isRegularFile(b))record("GENERATION_PAIR",Map.of("snapshots",List.of(b64(Files.readAllBytes(a)),b64(Files.readAllBytes(b)))));
            }
            if(name.equals("FLOOR_AFTER_FORCE")||name.startsWith("DELETE_AFTER"))record("STORAGE_CUT",Map.of("cut",name));
        }};
        var wire=new AutomaticTransport.Events(){public void at(String barrier,Map<String,Object> request,Map<String,Object> response)throws IOException {
            Path rules=root.resolve("network-rules.txt");
            if(Files.exists(rules))for(String rule:Files.readAllLines(rules)) {
                if(rule.isBlank())continue;String[] fields=rule.split(" ");need(fields.length==4,"network rule");
                if(fields[0].equals(request.get("sender"))&&fields[1].equals(request.get("recipient"))&&fields[2].equals(barrier)&&(fields[3].equals("*")||fields[3].equals(request.get("type")))) {
                    record("NETWORK_DROP",Map.of("rule",rule,"request",b64(AutomaticWire.encode(request,manifest,1<<20))));throw new IOException("owned partition");
                }
            }
            if(barrier.equals("BEFORE_REQUEST_WRITE"))record("REQUEST",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20))));
            if(!response.isEmpty())record(barrier.equals("BEFORE_RESPONSE_WRITE")?"REPLY":"RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20)),"frame",b64(AutomaticWire.encode(response,manifest,1<<20))));
            if(barrier.equals("AFTER_RESPONSE_READ")&&response.get("type").equals("ACCEPT_ACK"))cut("CHOSEN");
        }};
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(faults,wire,this::event));
    }
    static synchronized void print(Object value){System.out.println(new String(canonical(value),StandardCharsets.US_ASCII));System.out.flush();}
    void execute(AutomaticReplicatedSearchEngine<Integer,Doc> engine,Map<String,Object> request) {
        var result=new LinkedHashMap<>(request);String kind=text(request,"kind");call.set(text(request,"opId"));
        try {
            if(!kind.equals("status"))record("CLIENT_INVOKE",request);
            switch(kind) {
                case "status" -> {var s=engine.leadershipStatus();result.put("state",s.state().name());result.put("epoch",s.promisedEpoch());result.put("provenIndex",s.provenIndex());result.put("appliedIndex",s.appliedIndex());}
                case "update" -> engine.update(V51RichWorkload.document((int)number(request,"key"),(int)number(request,"revision"),17)).get(15,TimeUnit.SECONDS);
                case "read" -> result.put("documents",engine.search(d->true).stream().sorted(Comparator.comparingInt(Doc::id)).map(d->List.of(d.id(),d.title(),d.category(),d.price(),d.body())).toList());
                case "checkpoint" -> engine.checkpoint().get(15,TimeUnit.SECONDS);
                default -> throw new IllegalArgumentException(kind);
            }
            result.put("outcome","SUCCESS");
        }catch(Exception error) {
            Throwable cause=error;while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
            result.put("reason",cause.toString());result.put("outcome",cause instanceof AutomaticReplicationException a?a.outcome().name():"VALIDATION_FAILURE");
            if(cause instanceof AutomaticReplicationException a)result.put("reasonCode",a.reason().name());
        }finally {call.remove();}
        try {if(!kind.equals("status"))record("CLIENT_RESULT",result);}catch(IOException error){throw new UncheckedIOException(error);}print(result);
    }
    void run(int ordinal) throws Exception {
        install();var config=V51MeasuredAutomatic.configs(root).get(ordinal-1);
        try(var engine=AutomaticReplicatedSearchEngines.builder(V51RichWorkload.builder(),config).build()) {
            need(engine.start().get(15,TimeUnit.SECONDS).state()==AutomaticReplicationState.FOLLOWER,"public voter startup");
            event("STARTED",Map.of("node",node));print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            var callers=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(4));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;while((line=input.readLine())!=null) {
                    @SuppressWarnings("unchecked") var request=(Map<String,Object>)AdmissionJson.parse(line);
                    if(request.get("kind").equals("close"))break;callers.execute(()->execute(engine,request));
                }
            }finally {callers.shutdown();need(callers.awaitTermination(20,TimeUnit.SECONDS),"owned calls drained");}
            engine.close();event("CLOSED",Map.of());
        }finally {AutomaticRuntimeHooks.CURRENT.remove();V51CloudJournal.closeAll();}
    }
    public static void main(String[] args)throws Exception {new V51FullSizeRuntime(Path.of(args[0]),Integer.parseInt(args[1]),Integer.parseInt(args[2])).run(Integer.parseInt(args[1]));}
}
