package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Direct component probes on live native owners. Network/physical evidence is
 * collected by the enclosing fixture; these points do not claim socket custody. */
final class V53SpecialExportResources {
    static final long BUDGET=100;
    interface Open { MembershipTransferExport open(AtomicLong clock)throws Exception; }
    static MembershipResources budget() {
        return new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
    }
    static List<Map<String,Object>> probe(MembershipResources budget,List<Open> factories,Map<String,byte[]> originals)throws Exception {
        var cases=new ArrayList<Map<String,Object>>();var baseline=budget.usage();
        for(String mode:List.of("close","expiry")) {
            var rows=new ArrayList<Map<String,Object>>();cases.add(Map.of("mode",mode,"events",rows));
            var clock=new AtomicLong();var exports=new ArrayList<MembershipTransferExport>();
            V53ExportResourceBindingsTest.mark(rows,"BEGIN",budget);
            try {
                for(var factory:factories)exports.add(factory.open(clock));
                V53ExportResourceBindingsTest.mark(rows,"OPENED",budget);
                for(var export:exports)V53ExportResourceBindingsTest.read(export,originals);
                V53ExportResourceBindingsTest.mark(rows,"READS_FINISHED",budget);
                if(mode.equals("expiry"))clock.set(BUDGET);
                V53ExportResourceBindingsTest.mark(rows,"RELEASE_BEGIN",budget);
                if(mode.equals("expiry"))for(var export:exports)assertThrows(IllegalArgumentException.class,export::references);
                else for(var export:exports)export.close();
                V53ExportResourceBindingsTest.mark(rows,"INVALIDATED",budget);
                // Some wrappers retain their metadata after a refused read;
                // their explicit close must still release the nested borrow.
                for(var export:exports)export.close();
                V53ExportResourceBindingsTest.mark(rows,"RELEASED",budget);clock.set(0);
                for(var export:exports)assertThrows(IllegalArgumentException.class,export::references);
                V53ExportResourceBindingsTest.mark(rows,"REUSE_REFUSED",budget);
            }finally{for(var export:exports)export.close();}
            V53ExportResourceBindingsTest.mark(rows,"FINISHED",budget);assertEquals(baseline,budget.usage());
        }
        return cases;
    }
    static void save(Path root,String family,List<Map<String,Object>> cases,MembershipResources resources,boolean passed)throws Exception {
        V53ResourceTraceFiles.write(root.resolve("special-export-resources.json"),resources.observations());
        Files.write(root.resolve("special-export-history.json"),canonical(Map.of("schema","gse-v53-special-export-resources-v1",
                "family",family,"status",passed?"PASS":"FAIL","cases",cases,"completeMembershipHistory",false),1024*1024));
    }
}
