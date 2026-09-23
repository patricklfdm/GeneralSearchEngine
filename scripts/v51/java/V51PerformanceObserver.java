package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.admission.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Candidate-only read-only probe. Bootstrap, calls and routing stay in the public consumer. */
public final class V51PerformanceObserver {
    private static Object field(Object owner,String name) throws ReflectiveOperationException {
        var f=owner.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(owner);
    }
    private static byte[] last(Path directory,String kind) throws IOException {
        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))
            directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
        byte[] bytes=Files.readAllBytes(directory.resolve(kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr"));
        int offset=0,last=0;while(offset<bytes.length){last=offset;offset+=HEADER+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
        return Arrays.copyOfRange(bytes,last,offset);
    }
    public static Map<String,Object> diagnostics(Object engine) {
        try {
            var result=new LinkedHashMap<String,Object>();
            Object runtime=field(engine,"node");Object transport=field(runtime,"transport");
            result.put("admissionAvailable",((Semaphore)field(engine,"admission")).availablePermits());
            for(String name:List.of("ordered","deadlines"))result.put(name+"Queue",((ThreadPoolExecutor)field(engine,name)).getQueue().size());
            for(String name:List.of("inputs","completions"))result.put(name+"Queue",((BlockingQueue<?>)field(runtime,name)).size());
            for(String name:List.of("network","app","clients"))result.put(name+"Queue",((ThreadPoolExecutor)field(runtime,name)).getQueue().size());
            result.put("queuedBytes",((AtomicLong)field(transport,"queuedBytes")).get());
            result.put("inboundAvailable",((Semaphore)field(transport,"inbound")).availablePermits());
            var outbound=new TreeMap<String,Object>();
            for(var entry:((Map<?,?>)field(transport,"outbound")).entrySet())outbound.put(entry.getKey().toString(),((Semaphore)entry.getValue()).availablePermits());
            result.put("outboundAvailable",outbound);
            boolean terminated=(boolean)field(runtime,"terminated");result.put("closed",terminated);
            // Only read control-owned containers on their owning thread. The query adds no
            // protocol message, authority write, application call or strong-read barrier.
            var method=runtime.getClass().getDeclaredMethod("controlled",Callable.class);method.setAccessible(true);
            Callable<Map<String,Object>> inspect=()->{
                Object rejoin=field(runtime,"rejoin");long pinned=0,staging=0;
                for(Object lease:((Map<?,?>)field(rejoin,"sources")).values())pinned+=((byte[])field(lease,"bytes")).length;
                Object seed=field(rejoin,"seed");if(seed!=null)staging+=((byte[])field(seed,"bytes")).length;
                Object protocol=field(runtime,"protocol");
                synchronized(protocol) {
                    var basis=(AutomaticRecovery.Basis)field(protocol,"ownBasis");
                    if(basis!=null)pinned+=basis.image().encoded().bytes().length;
                }
                var store=(AutomaticStore)field(runtime,"store");long disk=0,transfer=0;
                synchronized(store) {
                    Path directory=(Path)field(store,"directory");
                    try(var paths=Files.walk(directory)) {
                        for(Path path:paths.filter(Files::isRegularFile).toList()) {
                            long size=Files.size(path);disk+=size;
                            if(directory.relativize(path).startsWith("transfer"))transfer+=size;
                        }
                    }
                }
                return Map.of("pinsBytes",pinned,"stagingBytes",staging,"authorityDiskBytes",disk,"transferDiskBytes",transfer);
            };
            @SuppressWarnings("unchecked") var counts=terminated?inspect.call():(Map<String,Object>)method.invoke(runtime,inspect);
            result.putAll(counts);return result;
        }catch(Exception error){throw new IllegalStateException("read-only diagnostic failed",error);}
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String node="node-"+args[1];
        var manifest=decode(Files.readAllBytes(root.resolve(node+"/manifest.gsr")),"MANIFEST");
        var trace=new V51PublicWorker.Trace(root.resolve(node+"-trace.jsonl"),root.resolve(node+"-arm.txt"),1,node,manifest) {
            @Override void append(byte[] line) throws IOException {
                if(line.length>4<<20||Files.exists(path)&&Files.size(path)+line.length>64L<<20)throw new IOException("performance trace bound");
                super.append(line);
            }
        };
        var starts=ThreadLocal.withInitial(HashMap<String,Long>::new);
        var faults=new AutomaticStore.Faults() {
            public void at(String event) throws IOException {
                for(String kind:List.of("PROMISE","ACCEPT","PROOF")) {
                    if(event.equals(kind+"_BEFORE_FORCE"))starts.get().put(kind,System.nanoTime());
                    if(event.equals(kind+"_AFTER_FORCE")) {
                        long end=System.nanoTime();Long start=starts.get().remove(kind);
                        var value=new LinkedHashMap<String,Object>();value.put("kind",kind);value.put("record",b64(last(root.resolve(node),kind)));
                        value.put("window",V51Measurement.window);
                        if(V51Measurement.detailed&&start!=null){value.put("forceStartNanos",start);value.put("forceEndNanos",end);}
                        trace.write("FORCE",value);
                    }
                }
            }
        };
        var reservations=Collections.synchronizedMap(new IdentityHashMap<Object,Long>());var serial=new AtomicLong();
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(faults,new AutomaticTransport.Events() {
            public void accounting(String event,Map<String,Object> request,Object token,int bytes) {
                try {
                    long id=0;if(event.endsWith("_ADMITTED")){id=serial.incrementAndGet();reservations.put(token,id);}
                    if(event.endsWith("_RELEASED")){Long old=reservations.remove(token);if(old==null)throw new IOException("reservation release without admit");id=old;}
                    trace.write("TRANSPORT",Map.of("transition",event,"reservation",id,"bytes",bytes,"window",V51Measurement.window));
                }catch(IOException e){throw new UncheckedIOException(e);}
            }
            public void at(String event,Map<String,Object> request,Map<String,Object> response) throws IOException {
                if(event.equals("BEFORE_REQUEST_WRITE"))trace.write("REQUEST",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20)),"window",V51Measurement.window));
                if(event.equals("BEFORE_RESPONSE_WRITE")||event.equals("AFTER_RESPONSE_READ"))
                    trace.write(event.equals("BEFORE_RESPONSE_WRITE")?"REPLY":"RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20)),"frame",b64(AutomaticWire.encode(response,manifest,1<<20))));
            }
        },trace::write));
        V51Measurement.observer=(name,row)->{try{trace.write(name,row);}catch(IOException e){throw new UncheckedIOException(e);}};
        V51Measurement.diagnostics=V51PerformanceObserver::diagnostics;
        try { V51MeasuredAutomatic.main(args); }
        finally {AutomaticRuntimeHooks.CURRENT.remove();}
    }
}
