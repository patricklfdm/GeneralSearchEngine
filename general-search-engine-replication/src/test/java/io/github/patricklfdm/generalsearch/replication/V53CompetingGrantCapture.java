package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;

/** Test-only copies linked to the unmodified monotonic owner/transport trace.
 * No selected winner, reconstructed grant, extra campaign or mutation retry. */
final class V53CompetingGrantCapture {
    static final String FILE="grant-capture-events.json";
    private final Path raw;
    private final List<Map<String,Object>> events;
    private final List<Map<String,Object>> copies=new ArrayList<>(), links=new ArrayList<>();
    private final V53GrantCapture capture;

    V53CompetingGrantCapture(Path raw,List<Map<String,Object>> events)throws IOException {
        this.raw=raw;this.events=Objects.requireNonNull(events);this.capture=new V53GrantCapture(raw,copies);
    }

    void at(String node,Path replica,String event)throws IOException {
        final int position;
        synchronized(events) {
            V53CompetingNodeQualification.observe(events,Map.of("node",node,"event",event));
            position=events.size()-1;
        }
        if(!event.equals("GRANT_BEFORE_RETURN"))return;
        // The journal writer remains held by the callback. Do not hold the
        // shared trace monitor during disk I/O: other nodes keep their events.
        synchronized(capture) {
            capture.at(node,"network-owner",replica,event);
            synchronized(events) {
                var row=new TreeMap<>(copies.getLast());row.put("returnEvent",position);
                row.put("capturedAfterEvent",events.size()-1);row.put("nanoTime",System.nanoTime());links.add(row);
            }
        }
    }

    /** Call after all owners drain, including failed runs. No completed marker
     * is manufactured for a failed copy; partial directories remain on disk. */
    void save()throws IOException {
        synchronized(capture) {
            Files.write(raw.resolve(FILE),canonical(links,1024*1024),StandardOpenOption.CREATE_NEW);
        }
    }
}
