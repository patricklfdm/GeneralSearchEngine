package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static org.junit.jupiter.api.Assertions.*;

/** Local qualification call observations, never a wire exchange or permit. */
final class V53PublishedPrefixProbe {
    @FunctionalInterface interface Open {MembershipTransferExport open()throws IOException;}
    static void run(boolean observed,List<Map<String,Object>> events,String node,Decoded request,
            MembershipResources resources,Open factory)throws IOException {
        if(observed)events.add(Map.of("node",node,"event","PUBLISHED_PREFIX_PROBE_BEGIN","request",request.digest(),
                "bytes",Base64.getEncoder().encodeToString(request.bytes())));
        try(var export=resources.observeProbeExport(factory.open())) {
            var references=export.references();assertFalse(references.isEmpty());
            if(observed) {
                var contents=new TreeMap<>(references).entrySet().stream().map(entry->Map.<String,Object>of(
                        "reference",entry.getKey(),"digest",entry.getValue().digest(),"bytes",entry.getValue().bytes(),
                        "kind",entry.getValue().kind().name())).toList();
                events.add(Map.of("node",node,"event","PUBLISHED_PREFIX_PROBE_REFERENCES","request",request.digest(),"contents",contents));
            }
        }
        if(observed)events.add(Map.of("node",node,"event","PUBLISHED_PREFIX_PROBE_RETURNED","request",request.digest()));
    }
}
