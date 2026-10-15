package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.admission.V52MeasurementConsumer;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Observation-only hooks; all bootstrap, reads and mutations remain public calls. */
public final class V52MeasurementWorker {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String node="node-"+args[1];int generation=Integer.parseInt(args[3]);
        var manifest=decode(Files.readAllBytes(root.resolve(node+"/manifest.gsr")),"MANIFEST");
        var trace=new V52MeasurementTrace(root.resolve(node+"-trace.jsonl"),root.resolve(node+"-arm.txt"),generation,node,manifest);
        var starts=ThreadLocal.withInitial(HashMap<String,Long>::new);
        var readAdmissions=new java.util.concurrent.atomic.AtomicLong();
        var recoveryFloor=new java.util.concurrent.atomic.AtomicLong();
        AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(new AutomaticStore.Faults() {
            public void at(String event) throws IOException {
                if(event.equals("SELECTOR_BEFORE_ACK")) {
                    // This hook runs after generation files, selector and parent
                    // directories were forced. Observe bytes; never open a voter.
                    Path directory=root.resolve(node);byte[] selector=Files.readAllBytes(directory.resolve("current.gsr"));
                    Path selected=directory.resolve(text(decode(selector,"SELECTOR").value(),"generation"));
                    var files=new ArrayList<Map<String,Object>>();files.add(Map.of("name","current.gsr","bytes",b64(selector)));
                    for(String name:List.of("generation.gsr","snapshot.gsr","accepted.gsr","proofs.gsr"))
                        files.add(Map.of("name",name,"bytes",b64(Files.readAllBytes(selected.resolve(name)))));
                    trace.event("STORAGE_CUT",Map.of("cut",event,"readGeneration",files));
                }
                for(String kind:List.of("PROMISE","ACCEPT","PROOF")) {
                    if(event.equals(kind+"_BEFORE_FORCE"))starts.get().put(kind,System.nanoTime());
                    if(event.equals(kind+"_AFTER_FORCE")) {
                        long end=System.nanoTime();Long start=starts.get().remove(kind);
                        if(start==null)throw new IOException("measurement force start missing");
                        trace.event("FORCE",Map.of("kind",kind,"record",b64(V51PublicWorker.lastJournal(root.resolve(node),kind)),"forceStartNanos",start,"forceEndNanos",end));
                    }
                }
            }
        },new AutomaticTransport.Events() {
            final Map<Object,Long> reservations=new IdentityHashMap<>();long serial;
            public synchronized void accounting(String event,Map<String,Object> request,Object token,int bytes) {
                try {
                    long id=0;
                    if(event.endsWith("_ADMITTED")){id=++serial;if(reservations.put(token,id)!=null)throw new IOException("measurement duplicate transport reservation");}
                    if(event.endsWith("_RELEASED")){Long found=reservations.remove(token);if(found==null)throw new IOException("measurement unmatched transport release");id=found;}
                    var row=new LinkedHashMap<String,Object>();row.put("transition",event);row.put("reservation",id);row.put("bytes",bytes);
                    if(!request.isEmpty())row.put("request",b64(AutomaticWire.encode(request,manifest,1<<20)));
                    trace.write("TRANSPORT",row);
                } catch(IOException failure){throw new UncheckedIOException(failure);}
            }
            public void at(String event,Map<String,Object> request,Map<String,Object> response) throws IOException {
                if(event.equals("BEFORE_REQUEST_WRITE"))trace.event("REQUEST",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20))));
                if(event.equals("BEFORE_RESPONSE_WRITE")||event.equals("AFTER_RESPONSE_READ"))
                    trace.event(event.equals("BEFORE_RESPONSE_WRITE")?"REPLY":"RECEIVED",Map.of("request",b64(AutomaticWire.encode(request,manifest,1<<20)),"frame",b64(AutomaticWire.encode(response,manifest,1<<20))));
            }
        },(event,values)->{
            var row=new LinkedHashMap<>(values);
            if(Set.of("PUBLIC_READ_INVOKE","REPLICA_READ_INVOKED").contains(event)) {
                String call=V52MeasurementConsumer.callId.get();if(call==null)throw new IOException("measurement read invocation lacks caller");row.put("opId",call);
            }
            if(Set.of("READ_CAPTURE_VALIDATED","REPLICA_READ_ADMITTED","REPLICA_READ_CAPTURE_VALIDATED","REPLICA_READ_SETTLING","REPLICA_READ_OWNERSHIP_RELEASED").contains(event))trace.write(event,row);
            else trace.event(event,row);
            // Controller hints update only after the complete observation write.
            // Offline replay must still prove the actual events and floor bytes.
            if(event.equals("REPLICA_READ_ADMITTED"))readAdmissions.incrementAndGet();
            if(event.equals("RECOVERY_FLOOR"))recoveryFloor.set(((Number)row.get("index")).longValue());
        }));
        V52MeasurementConsumer.observer=(name,row)->{try {trace.event(name,row);}catch(IOException failure){throw new UncheckedIOException(failure);}};
        V52MeasurementConsumer.diagnostics=engine->{
            var values=new LinkedHashMap<String,Object>(V51PublicWorker.queues(engine));
            values.put("readAdmissionsObserved",readAdmissions.get());values.put("recoveryFloorObserved",recoveryFloor.get());return values;
        };
        try {V52MeasurementConsumer.main(args);}
        finally {AutomaticRuntimeHooks.CURRENT.remove();}
    }
}
