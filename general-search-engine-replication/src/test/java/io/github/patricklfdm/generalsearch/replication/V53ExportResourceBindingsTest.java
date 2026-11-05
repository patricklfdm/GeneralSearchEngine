package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original public-bootstrap storage, native grant, overlapping read-only
 * exports and exact resource transitions. No transport or view change. */
class V53ExportResourceBindingsTest {
    @TempDir Path temp;
    static final long BUDGET=100;
    static Map<String,Object> point(MembershipResources resources) {
        var p=resources.observationCheckpoint();assertTrue(p.complete());
        return Map.of("sequence",p.sequence(),"usage",V53ResourceTraceFiles.usage(p.usage()));
    }
    static void mark(List<Map<String,Object>> events,String name,MembershipResources resources) {
        events.add(Map.of("event",name,"point",point(resources)));
    }
    static void read(MembershipTransferExport export,Map<String,byte[]> originals)throws Exception {
        for(var content:new HashSet<>(export.references().values())) {
            var bytes=originals.get(content.digest());assertNotNull(bytes);assertEquals(bytes.length,content.bytes());
            for(int at=0;at<bytes.length;) {
                var part=export.read(content.digest(),at,1024);assertTrue(part.length>0 && part.length<=1024);
                assertArrayEquals(Arrays.copyOfRange(bytes,at,at+part.length),part);at+=part.length;
            }
        }
    }
    @ParameterizedTest @ValueSource(ints={3,4,5})
    void originalExportsOverlapThenReleaseOnCloseOrExpiry(int size)throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-export-resources/run-"+UUID.randomUUID()));
        System.out.println("v53ExportResources="+raw.toAbsolutePath()+" size="+size);
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,size,false);
        var budget=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,MembershipResources.QUEUE_LIMIT,
                MembershipResourceObservations.MAXIMUM);
        var target=f.request.targets().getFirst();var cases=new ArrayList<Map<String,Object>>();Throwable failure=null;
        try(var owner=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),
                target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{})) {
            var source=owner.beginActivation();var promise=owner.promised().orElseThrow();var context=source.capsule.context;
            var ballot=object(source.basis.value().get("ballot"));var baseline=budget.usage();
            Path captured=Files.createDirectory(raw.resolve("captured"));
            for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
            Path exported=Files.createDirectory(raw.resolve("exported"));var originals=new HashMap<String,byte[]>();var contents=new ArrayList<Map<String,Object>>();
            for(String mode:List.of("close","expiry")) {
                var rows=new ArrayList<Map<String,Object>>();cases.add(Map.of("mode",mode,"events",rows));var clock=new AtomicLong();
                mark(rows,"BEGIN",budget);
                try(var frozen=owner.exportSource(source.basis,clock::get,BUDGET)) {
                    mark(rows,"SOURCE_OPENED",budget);
                    if(originals.isEmpty()) {
                        for(var content:frozen.contents()) {
                            var bytes=V53SourceExportTest.complete(frozen,content);originals.put(content.digest(),bytes);
                            Files.write(exported.resolve(content.digest()+".bin"),bytes);
                            contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                        }
                        contents.sort(Comparator.comparing(v->(String)v.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
                    }
                    try(var record=owner.exportRecord(promise.digest(),"PROMISE",ballot,clock::get,0,BUDGET)) {
                        mark(rows,"RECORD_OPENED",budget);
                        try(var prefix=owner.exportPrefix(MembershipContext.cutDigest(context.cut),ballot,context.authority(),budget,clock::get,0,BUDGET)) {
                            mark(rows,"PREFIX_OPENED",budget);read(frozen,originals);read(record,originals);read(prefix,originals);mark(rows,"READS_FINISHED",budget);
                            if(mode.equals("expiry"))clock.set(BUDGET);
                            mark(rows,"RECORD_RELEASE_BEGIN",budget);
                            if(mode.equals("expiry"))assertThrows(IllegalArgumentException.class,record::references);else record.close();
                            mark(rows,"RECORD_RELEASED",budget);
                            mark(rows,"SOURCE_RELEASE_BEGIN",budget);
                            if(mode.equals("expiry"))assertThrows(IllegalArgumentException.class,frozen::references);else frozen.close();
                            mark(rows,"SOURCE_RELEASED",budget);
                            mark(rows,"PREFIX_RELEASE_BEGIN",budget);
                            if(mode.equals("expiry"))assertThrows(IllegalArgumentException.class,prefix::references);else prefix.close();
                            mark(rows,"PREFIX_RELEASED",budget);clock.set(0);
                            assertThrows(IllegalArgumentException.class,record::references);assertThrows(IllegalArgumentException.class,frozen::references);
                            assertThrows(IllegalArgumentException.class,prefix::references);mark(rows,"REUSE_REFUSED",budget);
                        }
                    }
                }
                mark(rows,"FINISHED",budget);assertEquals(baseline,budget.usage());
            }
        }catch(Throwable error){failure=error;throw error;}
        finally {
            f.snapshot("after");V53ResourceTraceFiles.write(raw.resolve("resources.json"),budget.observations());
            Files.write(raw.resolve("history.json"),canonical(Map.of("schema","gse-v53-export-resources-v1","size",size,"status",failure==null?"PASS":"FAIL",
                    "cases",cases,"completeMembershipHistory",false),4*1024*1024));assertEquals(0,budget.usage().leases());
        }
    }
    @Test void observationNamesBindOriginalDigestsWithoutSharingAllocationIdentity() {
        for(String role:List.of("source-export","record-export","prefix-export")) {
            String first=MembershipSourceResources.export(role,"a".repeat(64)),second=MembershipSourceResources.export(role,"a".repeat(64));
            assertNotEquals(first,second);assertTrue(first.startsWith(role+"-"+"a".repeat(64)+"-"));assertTrue(first.length()<=128);
            assertThrows(IllegalArgumentException.class,()->MembershipSourceResources.export(role,"bad"));
        }
    }
}
