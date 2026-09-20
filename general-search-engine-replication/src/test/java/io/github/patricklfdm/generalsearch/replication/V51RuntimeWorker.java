package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** One real runtime per JVM. The setup command is a test fixture, never a public bootstrap. */
public final class V51RuntimeWorker {
    private static final class Trace {
        final Path path;long order;
        Trace(Path path){this.path=path;}
        synchronized void event(String name,Map<String,Object> values) throws IOException {
            var row=new LinkedHashMap<>(values);row.put("event",name);row.put("order",++order);row.put("pid",ProcessHandle.current().pid());
            Files.writeString(path,new String(canonical(row),StandardCharsets.US_ASCII)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
    }
    private static void print(Object value) {System.out.println(new String(canonical(value),StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();
        if(args[1].equals("setup")) {try(var group=new V51RuntimeFixture(root,true,false)){print(Map.of("status","SETUP","manifestDigest",digest(group.manifest)));}return;}
        int ordinal=Integer.parseInt(args[1]);String local="node-"+ordinal;var trace=new Trace(root.resolve(local+"-trace.jsonl"));
        try(var group=new V51RuntimeFixture(root,false,false)) {
            var manifest=decode(group.manifest,"MANIFEST");
            var hooks=new AutomaticStore.Faults(){
                public void at(String event) throws IOException {
                    for(String kind:List.of("PROMISE","ACCEPT","PROOF"))if(event.equals(kind+"_AFTER_FORCE")) {
                        Path directory=root.resolve(local);
                        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
                        byte[] bytes=Files.readAllBytes(directory.resolve(kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr"));
                        int offset=0,last=0;while(offset<bytes.length){last=offset;offset+=HEADER+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
                        trace.event("FORCE",Map.of("kind",kind,"record",b64(Arrays.copyOfRange(bytes,last,offset))));
                    }
                }
            };
            group.open(ordinal,hooks,trace::event,(barrier,request,response)->{
                if(barrier.equals("BEFORE_RESPONSE_WRITE"))trace.event("REPLY",Map.of("frame",b64(AutomaticWire.encode(response,manifest,V51RuntimeFixture.BOUNDS.maxFrameBytes()))));
                if(barrier.equals("AFTER_RESPONSE_READ"))trace.event("RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,V51RuntimeFixture.BOUNDS.maxFrameBytes())),"frame",b64(AutomaticWire.encode(response,manifest,V51RuntimeFixture.BOUNDS.maxFrameBytes()))));
            });
            var runtime=group.nodes.get(local);trace.event("STARTED",Map.of("node",local));print(Map.of("status","STARTED","node",local,"pid",ProcessHandle.current().pid()));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;
                while((line=input.readLine())!=null) {
                    var command=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(line));String name=text(command,"command");
                    var result=new LinkedHashMap<String,Object>();result.put("command",name);result.put("accepted",true);
                    try {
                        if(name.equals("status")) {
                            var view=runtime.view();result.put("state",view.state().name());result.put("epoch",view.promisedEpoch());result.put("provenIndex",view.provenIndex());result.put("publishedIndex",view.publishedIndex());
                            result.put("failure",runtime.failure()==null?null:runtime.failure().toString());
                        } else if(name.equals("add")||name.equals("update")) {
                            var document=new Document((int)number(command,"id"),text(command,"value"));trace.event("CALL",command);
                            long index=runtime.submit(name.equals("add")?1:2,app->app.documents(name.toUpperCase(Locale.ROOT),List.of(document))).get(20,TimeUnit.SECONDS);
                            result.put("index",index);trace.event("SUCCESS",Map.of("index",index,"id",document.id(),"value",document.value()));
                        } else if(name.equals("query")) {
                            var documents=runtime.inspectLocal(engine->engine.search(d->true).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList()).get(5,TimeUnit.SECONDS);
                            result.put("documents",documents);
                        } else if(name.equals("close")) {runtime.close();trace.event("CLOSED",Map.of());print(result);break;}
                        else throw new IllegalArgumentException(name);
                    }catch(Exception error) {result.put("accepted",false);result.put("reason",error.toString());}
                    print(result);
                }
            }
        }
    }
}
