package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Optional test-only attachment. Original protocol events are never amended.
 * All clocks and anchors are sampled while holding their existing trace monitor.
 * A failed capture invalidates evidence, without injecting a protocol failure. */
final class V53RestartLifecycleCapture {
    static final int LIMIT=65536;
    final Path directory;
    final V53AutomaticLifecycleCapture lifecycle;
    private final List<Map<String,Object>> events;
    private final List<Map<String,Object>> clocks=new ArrayList<>(),requests=new ArrayList<>();
    private final int first;
    private final long attached;
    private final String prefix;
    private Map<String,Object> opened;
    private String failure="";
    V53RestartLifecycleCapture(Path raw,List<Map<String,Object>> events)throws IOException {
        this.events=events;
        directory=Files.createDirectory(raw.resolveSibling("restart-lifecycle-"+raw.getFileName()));
        synchronized(events) {
            first=events.size();prefix=hash(canonical(events,32*1024*1024));attached=System.nanoTime();
        }
        lifecycle=new V53AutomaticLifecycleCapture(directory,events);
    }
    void event(int index,Map<String,Object> value) {
        synchronized(events) {
            if(!failure.isEmpty())return;
            try {
                if(clocks.size()>=LIMIT || index!=first+clocks.size())throw new IllegalArgumentException("restart clock bound/order");
                clocks.add(Map.of("index",index,"nanoTime",System.nanoTime(),"sha256",hash(canonical(value,16*1024*1024))));
            }catch(RuntimeException error){failure=error.toString();}
        }
    }
    void incoming(String node,String event,Decoded request) {
        if(!node.equals("node-1") || !event.equals("AFTER_REQUEST_READ") || !request.kind().equals("HEARTBEAT"))return;
        synchronized(events) {
            if(!failure.isEmpty())return;
            if(requests.size()>=256){failure="restart incoming bound";return;}
            requests.add(Map.of("node",node,"afterEvent",events.size()-1,"nanoTime",System.nanoTime(),
                    "request",Base64.getEncoder().encodeToString(request.bytes())));
        }
    }
    void opened(long budget) {
        synchronized(events) {
            if(opened!=null)throw new IllegalArgumentException("restart capture single owner");
            opened=Map.of("node","node-1","afterEvent",events.size()-1,"nanoTime",System.nanoTime(),"budgetNanos",budget);
        }
    }
    void save(Path raw,boolean producerPassed,boolean ownerDrained,Optional<IOException> observationFailure,
            List<MembershipResources> resources)throws IOException {
        synchronized(events) {
            lifecycle.save();var value=new TreeMap<String,Object>();
            value.put("schema","gse-v53-restart-lifecycle-capture-v1");value.put("firstEvent",first);value.put("prefixSha256",prefix);
            value.put("attachedNanos",attached);value.put("events",clocks);value.put("opened",opened);value.put("requests",requests);
            value.put("captureFailure",failure);value.put("observationFailure",observationFailure.map(Throwable::toString).orElse(""));
            value.put("producerPassed",producerPassed);value.put("ownerDrained",ownerDrained);
            value.put("resourceLeases",resources.stream().map(v->v.usage().leases()).toList());
            value.put("eventsSha256",hash(Files.readAllBytes(raw.resolve("events.json"))));
            value.put("planSha256",hash(Files.readAllBytes(raw.resolve("original-plan.gsbp"))));
            Files.write(directory.resolve("capture.json"),canonical(value,16*1024*1024),StandardOpenOption.CREATE_NEW);
            if(!failure.isEmpty() || observationFailure.isPresent())throw new IOException("restart lifecycle capture failed");
        }
    }
}
