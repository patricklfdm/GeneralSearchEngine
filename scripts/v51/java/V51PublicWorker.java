package io.github.patricklfdm.generalsearch.replication;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Observes force and wire boundaries only; cannot bootstrap, submit or activate privately. */
public final class V51PublicWorker {
    /** Read thread-safe queue/semaphore counters only; never enqueue or change authority. */
    private static Object field(Object owner,String name) throws ReflectiveOperationException {
        var value=owner.getClass().getDeclaredField(name);value.setAccessible(true);return value.get(owner);
    }
    private static Map<String,Object> queues(Object engine) {
        try {
            var result=new LinkedHashMap<String,Object>();Object runtime=field(engine,"node");
            result.put("admissionAvailable",((java.util.concurrent.Semaphore)field(engine,"admission")).availablePermits());
            for(String name:List.of("ordered","deadlines")) {
                var pool=(java.util.concurrent.ThreadPoolExecutor)field(engine,name);result.put(name+"Queue",pool.getQueue().size());
            }
            for(String name:List.of("inputs","completions")) {
                var queue=(java.util.concurrent.BlockingQueue<?>)field(runtime,name);result.put(name+"Queue",queue.size());result.put(name+"Remaining",queue.remainingCapacity());
            }
            for(String name:List.of("network","app","clients")) {
                var pool=(java.util.concurrent.ThreadPoolExecutor)field(runtime,name);result.put(name+"Queue",pool.getQueue().size());result.put(name+"Active",pool.getActiveCount());
            }
            return result;
        }catch(ReflectiveOperationException error){throw new IllegalStateException(error);}
    }
    private static byte[] lastJournal(Path directory,String kind) throws IOException {
        if(!kind.equals("PROMISE")&&Files.exists(directory.resolve("current.gsr")))
            directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
        byte[] bytes=Files.readAllBytes(directory.resolve(kind.equals("PROMISE")?"promises.gsr":kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr"));
        int offset=0,last=0;while(offset<bytes.length){last=offset;offset+=HEADER+ByteBuffer.wrap(bytes,offset+12,4).getInt();}
        return Arrays.copyOfRange(bytes,last,offset);
    }
    private static final class Pressure {
        final Path root;final Trace trace;final AutomaticRecords.Record manifest;
        final Map<Object,Long> reservations=new IdentityHashMap<>();long serial,holds;
        Pressure(Path root,Trace trace,AutomaticRecords.Record manifest){this.root=root;this.trace=trace;this.manifest=manifest;}
        synchronized void accounting(String event,Map<String,Object> request,Object token,int bytes) {
            try {
                long id=0;
                if(event.endsWith("_ADMITTED")){id=++serial;if(reservations.put(token,id)!=null)throw new IOException("duplicate reservation");}
                if(event.endsWith("_RELEASED")){Long found=reservations.remove(token);if(found==null)throw new IOException("unmatched reservation release");id=found;}
                var row=new LinkedHashMap<String,Object>();row.put("transition",event);row.put("reservation",id);row.put("bytes",bytes);
                if(!request.isEmpty())row.put("request",b64(AutomaticWire.encode(request,manifest,1<<20)));
                trace.write("TRANSPORT",row);
            }catch(IOException e){throw new UncheckedIOException(e);}
        }
        void hold(String barrier,Map<String,Object> request) throws IOException {
            Path rules=root.resolve("pressure-rules.txt");if(!Files.exists(rules))return;
            String match=request.get("sender")+" "+request.get("recipient")+" "+barrier+" "+request.get("type");
            String wildcard=request.get("sender")+" "+request.get("recipient")+" "+barrier+" *";
            var settings=Files.readAllLines(rules);if(!settings.contains(match)&&!settings.contains(wildcard))return;
            long id; synchronized(this){id=++holds;}
            trace.write("PRESSURE_HELD",Map.of("hold",id,"barrier",barrier,"request",b64(AutomaticWire.encode(request,manifest,1<<20))));
            long until=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(60);
            try {
                while(!Files.exists(root.resolve("pressure-release"))&&System.nanoTime()<until)Thread.sleep(10);
                if(!Files.exists(root.resolve("pressure-release")))throw new IOException("pressure controller did not release");
                trace.write("PRESSURE_RELEASED",Map.of("hold",id));
            }catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
        }
    }
    /** Read bytes only, at an existing serialized storage hook. Never repairs authority. */
    private static List<Map<String,Object>> reclamationFiles(Path directory) throws IOException {
        var files=new TreeMap<String,Object>();
        try(var paths=Files.walk(directory)) {
            for(Path path:paths.filter(Files::isRegularFile).toList()) {
                String name=directory.relativize(path).toString().replace(File.separatorChar,'/');
                if(Set.of("promises.gsr","accepted.gsr","proofs.gsr","current.gsr","recovery-floor.gsr","recovery-floor.pending.gsr").contains(name)
                        ||name.startsWith("generation-a/")||name.startsWith("generation-b/")
                        ||name.startsWith("transfer/floor-")||name.startsWith("transfer/retiring/"))
                    files.put(name,b64(Files.readAllBytes(path)));
            }
        }
        return files.entrySet().stream().map(e->Map.<String,Object>of("name",e.getKey(),"bytes",e.getValue())).toList();
    }
    static class Trace {
        final Path path,arm;final int generation;final String node,group,manifestDigest;long order;boolean crashing;
        Trace(Path path,Path arm,int generation,String node,AutomaticRecords.Record manifest) throws IOException {
            this.path=path;this.arm=arm;this.generation=generation;this.node=node;
            group=text(manifest.value(),"groupId");manifestDigest=manifest.digest();
            if(Files.exists(path.resolveSibling(path.getFileName()+".pending")))
                throw new IOException("stopped observer trace must be completed before restart");
        }
        synchronized void write(String name,Map<String,Object> values) throws IOException {
            var row=new LinkedHashMap<>(values);row.put("event",name);row.put("order",++order);row.put("pid",ProcessHandle.current().pid());
            row.put("generation",generation);row.put("localNanos",System.nanoTime());
            row.put("node",node);row.put("groupId",group);row.put("manifestDigest",manifestDigest);
            byte[] json=canonical(row),line=Arrays.copyOf(json,json.length+1);line[json.length]='\n';
            // Test telemetry only, outside replica authority. Publish the complete
            // observation before SIGKILL can interrupt its JSONL append.
            Path pending=path.resolveSibling(path.getFileName()+".pending"), staging=path.resolveSibling(path.getFileName()+".staging");
            if(Files.exists(pending))throw new IOException("unfinished observer append");
            byte[] record=ByteBuffer.allocate(48+line.length).put("GSETRC1\n".getBytes(StandardCharsets.US_ASCII))
                    .putLong(Files.exists(path)?Files.size(path):0).put(hash(line)).put(line).array();
            Files.write(staging,record);
            Files.move(staging,pending,StandardCopyOption.ATOMIC_MOVE);
            append(line);
            Files.delete(pending);
        }
        void append(byte[] line) throws IOException {
            Files.write(path,line,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
        void event(String name,Map<String,Object> values) throws IOException {
            String mode;
            synchronized(this) {
                if(crashing)mode="kill";
                else {
                    write(name,values);
                    if(!Files.exists(arm))return;
                    var settings=Files.readAllLines(arm);
                    if(!settings.get(0).equals(name)&&!settings.get(0).equals(name+":"+values.get("cut")))return;
                    mode=settings.get(1);crashing=!mode.equals("pause");
                    Files.delete(arm);write("CUT_REACHED",Map.of("cut",settings.get(0),"mode",mode));
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
        var trace=new Trace(root.resolve(local+"-trace.jsonl"),root.resolve(local+"-arm.txt"),args.length>3?Integer.parseInt(args[3]):1,local,manifest) {
            @Override void append(byte[] line) throws IOException {
                if(args.length>2&&args[2].equals("remote-fault")&&(line.length>4<<20||Files.exists(path)&&Files.size(path)+line.length>32L<<20))
                    throw new IOException("remote fault trace member bound");
                super.append(line);
            }
        };
        boolean promiseEvidence=Files.exists(root.resolve("promise-evidence"));
        Pressure pressure=Files.exists(root.resolve("pressure-evidence"))?new Pressure(root,trace,manifest):null;
            var hooks=new AutomaticStore.Faults(){
                private Path partialPath;private byte[] before;
                public int maximumWriteBytes(){return Files.exists(root.resolve(local+"-partial-write.txt"))?64:Integer.MAX_VALUE;}
                public void capacityRejected(String budget,long limit,long retained,long replaced,long requested) {
                    if(!Files.exists(root.resolve("resource-evidence")))return;
                    try {
                        var inventory=new ArrayList<Map<String,Object>>();Path directory=root.resolve(local);
                        try(var files=Files.walk(directory)) {
                            for(Path file:files.filter(Files::isRegularFile).sorted().toList())
                                inventory.add(Map.of("path",directory.relativize(file).toString(),"size",Files.size(file),"sha256",sha(Files.readAllBytes(file))));
                        }
                        trace.write("RESOURCE_REJECTED",Map.of("budget",budget,"limit",limit,"retained",retained,"replaced",replaced,"requested",requested,"files",inventory));
                    }
                    catch(IOException error){throw new UncheckedIOException(error);}
                }
                public void at(String event) throws IOException {
                    if((event.equals("ACCEPT_BEFORE_FORCE")||event.equals("PROOF_BEFORE_FORCE"))&&Files.exists(root.resolve(local+"-slow-force"))) {
                        trace.write("SLOW_FORCE_BEGIN",Map.of("kind",event.split("_")[0],"delayMillis",1500));
                        try {Thread.sleep(1500);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
                        trace.write("SLOW_FORCE_END",Map.of("kind",event.split("_")[0],"delayMillis",1500));
                    }
                    Path partial=root.resolve(local+"-partial-write.txt");
                    if(Files.exists(partial)) {
                        String kind=Files.readString(partial).trim();
                        if(!Set.of("ACCEPT","PROOF").contains(kind))throw new IOException("partial-write kind");
                        if(event.equals(kind+"_BEFORE_WRITE")) {
                            Path directory=root.resolve(local);
                            if(Files.exists(directory.resolve("current.gsr")))directory=directory.resolve(text(decode(Files.readAllBytes(directory.resolve("current.gsr")),"SELECTOR").value(),"generation"));
                            partialPath=directory.resolve(kind.equals("ACCEPT")?"accepted.gsr":"proofs.gsr");before=Files.readAllBytes(partialPath);
                        }
                        if(event.equals(kind+"_WRITE_CHUNK")) {
                            Files.delete(partial);
                            trace.write("PARTIAL_WRITE_FAILURE",Map.of("kind",kind,"path",root.resolve(local).relativize(partialPath).toString(),
                                    "before",b64(before),"after",b64(Files.readAllBytes(partialPath))));
                            throw new IOException("controller-owned partial "+kind+" write error");
                        }
                    }
                    if(Set.of("FLOOR_BEFORE_WRITE","FLOOR_AFTER_FORCE","FLOOR_BEFORE_ACK","SELECTOR_BEFORE_ACK","SOURCE_BEFORE_ACK","WITNESS_BEFORE_ACK","TRANSFER_PROGRESS_BEFORE_ACK").contains(event)||event.startsWith("DELETE_AFTER_")) {
                        var values=new LinkedHashMap<String,Object>();values.put("cut",event);
                        if(Files.exists(root.resolve("reclamation-evidence"))&&(event.startsWith("FLOOR_")||event.startsWith("DELETE_AFTER_")))
                            values.put("authority",reclamationFiles(root.resolve(local)));
                        trace.event("STORAGE_CUT",values);
                    }
                    for(String kind:List.of("PROMISE","ACCEPT","PROOF"))if(event.equals(kind+"_AFTER_FORCE")) {
                        trace.event("FORCE",Map.of("kind",kind,"record",b64(lastJournal(root.resolve(local),kind))));
                    }
                    if(event.startsWith("ACCEPT_")||event.startsWith("PROOF_"))
                        trace.event(event,pressure!=null&&event.endsWith("_AFTER_WRITE")?Map.of("record",b64(lastJournal(root.resolve(local),event.startsWith("ACCEPT_")?"ACCEPT":"PROOF"))):Map.of());
                    if(promiseEvidence&&(event.startsWith("PROMISE_")||event.equals("BASIS_BEFORE_ACK")))
                        trace.event(event,Map.of("journal",b64(Files.readAllBytes(root.resolve(local+"/promises.gsr")))));
                }
            };
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(hooks,new AutomaticTransport.Events(){
            public void accounting(String event,Map<String,Object> request,Object token,int bytes){if(pressure!=null)pressure.accounting(event,request,token,bytes);}
            public void at(String barrier,Map<String,Object> request,Map<String,Object> response) throws IOException {
                if(pressure!=null)pressure.hold(barrier,request);
                Path rules=root.resolve("network-rules.txt");
                if(Files.exists(rules))for(String rule:Files.readAllLines(rules)) {
                    if(rule.isBlank())continue;
                    String[] fields=rule.split(" ");
                    if(fields.length!=4)throw new IOException("invalid owned network rule");
                    if(fields[0].equals(request.get("sender"))&&fields[1].equals(request.get("recipient"))
                            &&fields[2].equals(barrier)&&(fields[3].equals("*")||fields[3].equals(request.get("type")))) {
                        trace.event("NETWORK_DROP",Map.of("barrier",barrier,"rule",rule,"request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes()))));
                        throw new IOException("controller-owned directional network fault");
                    }
                }
                if(Set.of("BASIS_CHUNK","SNAPSHOT_CHUNK","REJOIN_INSTALL").contains(request.get("type"))
                        ||Files.exists(root.resolve("selection-evidence"))&&Set.of("ACCEPT","COMMIT_PROOF").contains(request.get("type"))
                        ||Files.exists(root.resolve("final-coverage-evidence"))&&request.get("type").equals("HEARTBEAT")) {
                    var values=new LinkedHashMap<String,Object>();values.put("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())));
                    if(!response.isEmpty())values.put("frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())));
                    if(request.get("type").equals("BASIS_CHUNK"))values.put("cut",number(object(request.get("payload")),"offset")>0?"continuation":"first");
                    trace.event("WIRE_"+barrier+"_"+request.get("type"),values);
                }
                if(promiseEvidence&&request.get("type").equals("PREPARE")) {
                    var values=new LinkedHashMap<String,Object>();
                    values.put("request",b64(AutomaticWire.encode(request,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())));
                    if(!response.isEmpty()) {
                        values.put("frame",b64(AutomaticWire.encode(response,manifest,io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.bounds().maxFrameBytes())));
                        values.put("cut",response.get("type"));
                    }
                    trace.event("WIRE_"+barrier+"_PREPARE",values);
                    if(barrier.equals("BEFORE_RESPONSE_WRITE")&&response.get("type").equals("PROMISE")
                            &&Files.deleteIfExists(root.resolve(local+"-lose-promise"))) {
                        trace.write("PROMISE_REPLY_LOST",values);
                        throw new IOException("controller-owned single PROMISE response loss");
                    }
                }
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
            }
        },(name,values)->{
            if(name.equals("READ_CAPTURE_VALIDATED"))trace.write(name,values); // Observation only; never pause under the protocol monitor.
            else trace.event(name,values);
        }));
        io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.observer=(name,values)->{try{trace.event(name,values);}catch(IOException e){throw new UncheckedIOException(e);}};
        if(Files.exists(root.resolve("lifecycle-evidence")))io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.diagnostics=V51PublicWorker::queues;
        if(args.length>2&&(args[2].equals("performance-small")||args[2].equals("remote-fault"))) {
            var method=Class.forName("io.github.patricklfdm.generalsearch.replication.V51PerformanceObserver").getMethod(args[2].equals("remote-fault")?"diagnosticsIncludingQuarantine":"diagnostics",Object.class);
            io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.diagnostics=engine->{
                try {@SuppressWarnings("unchecked") var value=(Map<String,Object>)method.invoke(null,engine);return value;}
                catch(ReflectiveOperationException error){throw new IllegalStateException(error);}
            };
        }
        if(args.length>2&&(args[2].equals("qualification")||args[2].equals("lifecycle")||args[2].equals("backpressure")||(args[2].equals("performance-small")||args[2].equals("remote-fault"))))
            Class.forName("io.github.patricklfdm.generalsearch.admission."+(args[2].equals("remote-fault")?"V51RemoteFaultConsumer":args[2].equals("performance-small")?"V51SmallPerformanceConsumer":args[2].equals("lifecycle")?"PublicLifecycleConsumer":args[2].equals("backpressure")?"PublicBackpressureConsumer":"PublicQualificationConsumer")).getMethod("main",String[].class).invoke(null,(Object)args);
        else io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.main(args);
    }
}
