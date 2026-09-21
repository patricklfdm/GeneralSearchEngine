package io.github.patricklfdm.generalsearch.replication;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Observes force and wire boundaries only; cannot bootstrap, submit or activate privately. */
public final class V51PublicWorker {
    private static final class Trace {
        final Path path;long order;
        Trace(Path path){this.path=path;}
        synchronized void event(String name,Map<String,Object> values) throws IOException {
            var row=new LinkedHashMap<>(values);row.put("event",name);row.put("order",++order);row.put("pid",ProcessHandle.current().pid());
            Files.writeString(path,new String(canonical(row),StandardCharsets.US_ASCII)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();String local="node-"+args[1];var trace=new Trace(root.resolve(local+"-trace.jsonl"));
        var manifest=decode(Files.readAllBytes(root.resolve(local+"/manifest.gsr")),"MANIFEST");
            var hooks=new AutomaticStore.Faults(){
                public void at(String event) throws IOException {
                    if(event.equals("FLOOR_BEFORE_ACK")||event.equals("SELECTOR_BEFORE_ACK")||event.equals("SOURCE_BEFORE_ACK")||event.equals("WITNESS_BEFORE_ACK")||event.equals("TRANSFER_PROGRESS_BEFORE_ACK")||event.startsWith("DELETE_AFTER_"))
                        trace.event("STORAGE_CUT",Map.of("cut",event));
                    for(String kind:List.of("PROMISE","ACCEPT","PROOF"))if(event.equals(kind+"_AFTER_FORCE")) {
                        Path directory=root.resolve(local);
                        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
                        byte[] bytes=Files.readAllBytes(directory.resolve(kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr"));
                        int offset=0,last=0;while(offset<bytes.length){last=offset;offset+=HEADER+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
                        trace.event("FORCE",Map.of("kind",kind,"record",b64(Arrays.copyOfRange(bytes,last,offset))));
                    }
                }
            };
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(hooks,(barrier,request,response)->{
                if(barrier.equals("BEFORE_RESPONSE_WRITE"))trace.event("REPLY",Map.of("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())),"frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
                if(barrier.equals("AFTER_RESPONSE_READ"))trace.event("RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())),"frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
        },trace::event));
        io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.observer=(name,values)->{try{trace.event(name,values);}catch(IOException e){throw new UncheckedIOException(e);}};
        io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.main(args);
    }
}
