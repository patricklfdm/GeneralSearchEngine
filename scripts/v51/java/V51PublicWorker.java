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
        final Path path,arm;final int generation;final String node,group,manifestDigest;long order;
        Trace(Path path,Path arm,int generation,String node,AutomaticRecords.Record manifest){
            this.path=path;this.arm=arm;this.generation=generation;this.node=node;
            group=text(manifest.value(),"groupId");manifestDigest=manifest.digest();
        }
        synchronized void write(String name,Map<String,Object> values) throws IOException {
            var row=new LinkedHashMap<>(values);row.put("event",name);row.put("order",++order);row.put("pid",ProcessHandle.current().pid());
            row.put("generation",generation);row.put("localNanos",System.nanoTime());
            row.put("node",node);row.put("groupId",group);row.put("manifestDigest",manifestDigest);
            Files.writeString(path,new String(canonical(row),StandardCharsets.US_ASCII)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
        void event(String name,Map<String,Object> values) throws IOException {
            write(name,values);
            String mode;
            synchronized(this) {
                if(!Files.exists(arm))return;
                var settings=Files.readAllLines(arm);
                if(!settings.get(0).equals(name))return;
                mode=settings.get(1);Files.delete(arm);write("CUT_REACHED",Map.of("cut",name,"mode",mode));
            }
            if(mode.equals("halt"))Runtime.getRuntime().halt(71);
            try {Thread.sleep(60000);}catch(InterruptedException e){Thread.currentThread().interrupt();}
            throw new IOException("controller did not SIGKILL armed worker");
        }
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();String local="node-"+args[1];
        var manifest=decode(Files.readAllBytes(root.resolve(local+"/manifest.gsr")),"MANIFEST");
        var trace=new Trace(root.resolve(local+"-trace.jsonl"),root.resolve(local+"-arm.txt"),args.length>3?Integer.parseInt(args[3]):1,local,manifest);
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
        if(args.length>2&&args[2].equals("qualification"))
            Class.forName("io.github.patricklfdm.generalsearch.admission.PublicQualificationConsumer").getMethod("main",String[].class).invoke(null,(Object)args);
        else io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.main(args);
    }
}
