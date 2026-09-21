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
        final Path path,arm;final int generation;final String node,group,manifestDigest;long order;boolean crashing;
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
            String mode;
            synchronized(this) {
                if(crashing)mode="kill";
                else {
                    write(name,values);
                    if(!Files.exists(arm))return;
                    var settings=Files.readAllLines(arm);
                    if(!settings.get(0).equals(name))return;
                    mode=settings.get(1);crashing=!mode.equals("pause");
                    Files.delete(arm);write("CUT_REACHED",Map.of("cut",name,"mode",mode));
                }
            }
            if(mode.equals("halt"))Runtime.getRuntime().halt(71);
            if(mode.equals("pause")) {
                Path release=path.resolveSibling(node+"-release");long until=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(60);
                try {
                    while(!Files.exists(release)&&System.nanoTime()<until)Thread.sleep(10);
                    if(!Files.exists(release))throw new IOException("controller did not release paused worker");
                    write("CUT_RELEASED",Map.of("cut",name));return;
                } catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
            }
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
                    if(event.startsWith("ACCEPT_")||event.startsWith("PROOF_"))trace.event(event,Map.of());
                }
            };
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(hooks,(barrier,request,response)->{
                Path partition=root.resolve("network-blocks.txt");
                if((barrier.equals("BEFORE_REQUEST_WRITE")||barrier.equals("AFTER_RESPONSE_READ"))&&Files.exists(partition)
                        &&Files.readAllLines(partition).contains(request.get("sender")+" "+request.get("recipient"))) {
                    trace.event("NETWORK_DROP",Map.of("barrier",barrier,"request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
                    throw new IOException("controller-owned network partition");
                }
                if(barrier.equals("BEFORE_RESPONSE_WRITE"))trace.event("REPLY",Map.of("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())),"frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
                if(barrier.equals("AFTER_RESPONSE_READ")) {
                    trace.event("RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())),"frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
                    if(response.get("type").equals("ACCEPT_ACK"))trace.event("ACCEPT_ACK_RECEIVED",Map.of());
                    if(response.get("type").equals("COMMIT_PROOF_ACK"))trace.event("PROOF_ACK_RECEIVED",Map.of());
                }
        },(name,values)->{
            if(name.equals("READ_CAPTURE_VALIDATED"))trace.write(name,values); // Observation only; never pause under the protocol monitor.
            else trace.event(name,values);
        }));
        io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.observer=(name,values)->{try{trace.event(name,values);}catch(IOException e){throw new UncheckedIOException(e);}};
        if(args.length>2&&(args[2].equals("qualification")||args[2].equals("lifecycle")))
            Class.forName("io.github.patricklfdm.generalsearch.admission."+(args[2].equals("lifecycle")?"PublicLifecycleConsumer":"PublicQualificationConsumer")).getMethod("main",String[].class).invoke(null,(Object)args);
        else io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.main(args);
    }
}
