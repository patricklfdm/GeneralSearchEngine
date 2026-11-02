package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;

/** Test-only state transitions anchored to the untouched native event stream.
 * Never polls a final state to reconstruct transitions or takes a protocol lock. */
final class V53AutomaticLifecycleCapture {
    static final String FILE="automatic-lifecycle.json";
    private final Path raw;
    private final List<Map<String,Object>> events;
    private final List<Map<String,Object>> observations=new ArrayList<>();
    private final Map<String,Integer> ordinals=new HashMap<>();
    V53AutomaticLifecycleCapture(Path raw,List<Map<String,Object>> events) {
        this.raw=raw;this.events=Objects.requireNonNull(events);
    }
    void at(String node,MembershipAutomaticOwner.Observation observation)throws IOException {
        synchronized(events) {
            if(observations.size()>=256)throw new IOException("automatic lifecycle capture bound");
            var row=new TreeMap<String,Object>();row.put("node",node);row.put("ordinal",ordinals.merge(node,1,Integer::sum));
            row.put("event",observation.event());row.put("state",observation.state().name());
            row.put("rounds",observation.rounds());row.put("pending",observation.pending());
            row.put("originalStarted",observation.originalStarted());row.put("detail",observation.detail());
            row.put("afterEvent",events.size()-1);row.put("nanoTime",System.nanoTime());observations.add(row);
        }
    }
    /** Called only after all nodes drain, including failed experiments. */
    void save()throws IOException {
        synchronized(events){Files.write(raw.resolve(FILE),canonical(observations,1024*1024),StandardOpenOption.CREATE_NEW);}
    }
}
