package io.github.patricklfdm.generalsearch.replication;
import io.github.patricklfdm.generalsearch.admission.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Observer compiled against the checksum-pinned published V5.0 replication JAR. */
public final class V51ConfiguredObserver {
    private static Path root;private static String node;private static long order;
    private static synchronized void trace(String event,Map<String,Object> values) {
        try {
            var row=new LinkedHashMap<>(values);row.put("event",event);row.put("node",node);row.put("pid",ProcessHandle.current().pid());
            row.put("localNanos",System.nanoTime());row.put("order",++order);row.put("window",V51Measurement.window);
            V51Measurement.append(root.resolve(node+"-trace.jsonl"),row);
        }catch(IOException error){throw new UncheckedIOException(error);}
    }
    private static byte[] last(String kind) throws IOException {
        Path directory=root.resolve(node);
        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr"))) {
            var input=new DataInputStream(new ByteArrayInputStream(Files.readAllBytes(directory.resolve("current.gsr"))));
            input.skipNBytes(80);input.skipNBytes(input.readInt());String slot=new String(input.readNBytes(input.readInt()),java.nio.charset.StandardCharsets.UTF_8);
            if(!Set.of("generation-a","generation-b").contains(slot))throw new IOException("configured selector slot");
            directory=directory.resolve(slot);
        }
        byte[] data=Files.readAllBytes(directory.resolve(kind.equals("ENTRY")?"entries.gsr":kind.equals("PROOF")?"proofs.gsr":"promises.gsr"));
        int at=0,last=0;while(at<data.length){last=at;at+=48+ByteBuffer.wrap(data,at+12,4).getInt();}return Arrays.copyOfRange(data,last,at);
    }
    public static void main(String[] args) throws Exception {
        root=Path.of(args[0]);node="node-"+args[1];var starts=ThreadLocal.withInitial(HashMap<String,Long>::new);
        var faults=new ReplicaStore.Faults(){public void at(String barrier) throws IOException {
            for(String kind:List.of("PROMISE","ENTRY","PROOF")) {
                if(barrier.equals("BEFORE_"+kind+"_FORCE"))starts.get().put(kind,System.nanoTime());
                if(barrier.equals("AFTER_"+kind+"_FORCE")) {
                    long end=System.nanoTime();Long start=starts.get().remove(kind);var row=new LinkedHashMap<String,Object>();
                    row.put("kind",kind);row.put("record",Base64.getEncoder().encodeToString(last(kind)));
                    if(V51Measurement.detailed&&start!=null){row.put("forceStartNanos",start);row.put("forceEndNanos",end);}
                    trace("FORCE",row);
                }
            }
        }};
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(faults,(name,index)->trace(name,Map.of("index",index)),
                (name,request,response)->{
                    if(name.equals("BEFORE_RESPONSE_WRITE")||name.equals("AFTER_RESPONSE_READ"))
                        trace(name.equals("BEFORE_RESPONSE_WRITE")?"REPLY":"RECEIVED",Map.of(
                                "request",Base64.getEncoder().encodeToString(ReplicaWire.encode(request,1<<20)),
                                "frame",Base64.getEncoder().encodeToString(ReplicaWire.encode(response,1<<20))));
                }));
        V51Measurement.observer=V51ConfiguredObserver::trace;
        V51Measurement.diagnostics=engine->Map.of("queueDetail","unsupported: published V5.0 exposes pending clients via status; no private queue traversal");
        try {V51MeasuredConfigured.main(args);}finally{ReplicaRuntimeHooks.CURRENT.remove();}
    }
}
