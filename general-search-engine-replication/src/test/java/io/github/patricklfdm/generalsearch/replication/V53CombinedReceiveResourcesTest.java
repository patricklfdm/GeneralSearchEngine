package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceReceiveTest.*;

/** Real current/PROMISE files and complete receiving copies share one budget.
 * These copies are storage pressure, never additional voters or learner authority. */
class V53CombinedReceiveResourcesTest {
    @TempDir Path temp;
    static final List<String> MODES=List.of("image-count","shared-short","shared-exact");
    static final List<String> COUNTER_CUTS=List.of("ALLOCATOR_BEFORE_WRITE","ALLOCATOR_CREATED","ALLOCATOR_WRITTEN",
            "ALLOCATOR_FORCED","ALLOCATOR_RENAMED","ALLOCATOR_DIRECTORY_FORCED","ALLOCATOR_BEFORE_RETURN");

    static Map<String,Object> usage(MembershipResources budget) {
        var u=budget.usage();var counts=new TreeMap<String,Integer>();u.counts().forEach((k,v)->counts.put(k.name(),v));
        return Map.of("metadata",u.metadata(),"staging",u.staging(),"queued",u.queued(),"leases",u.leases(),"counts",counts);
    }
    static void snapshot(Path source,Path target)throws Exception {V53JournalApplicationTest.copy(source,target);}
    static void observe(Path raw,Path scratch,Path authority,String stage,MembershipResources budget,List<Map<String,Object>> events)throws Exception {
        Path output=Files.createDirectory(raw.resolve("states/"+stage));snapshot(scratch,output.resolve("scratch"));snapshot(authority,output.resolve("authority"));
        events.add(Map.of("stage",stage,"usage",usage(budget)));
    }
    static MembershipSourceReceive receive(Path path,MembershipSourceExport export,MembershipResources budget,boolean learner)throws Exception {
        if(!learner)return receiver(path,export,budget,new AtomicLong(),100);
        var source=export.source();return MembershipSourceReceive.learner(path,source.capsule.context.root,source.owner,source.capsule.context.cut,
                UUID.randomUUID(),UUID.randomUUID(),packetOffer(export),budget,1024,()->0L,0,100);
    }
    @Test void actualCopiesShareCountAndByteLimitsWithoutSpendingOriginalAuthority()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-combined-receive/run-"+UUID.randomUUID()));var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53CombinedReceiveEvidence="+root.toAbsolutePath());
        try {
            for(int size:List.of(3,4,5))for(String mode:MODES) {
                String name="stable-"+size+"-"+mode;Path raw=Files.createDirectory(root.resolve(name));scenario(raw,size,mode);
                rows.add(Map.of("case",name,"size",size,"mode",mode));System.out.println("v53CombinedReceiveCase="+name+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-combined-receive-v1","status",rows.size()==9?"PASS":"INCOMPLETE",
                "cases",rows,"network",false,"simultaneousMaximumQualified",false,"phase3Complete",false),65536));
        }
    }
    void scenario(Path raw,int size,String mode)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(raw.getFileName())),raw,size,false);f.ownedHistory=true;
        var target=f.request.targets().getFirst();Path authority=target.replicaDirectory();Path scratch=Files.createDirectory(temp.resolve(raw.getFileName()+"-scratch"));
        long packet=f.original.seed.capsule.packet.bytes().length,image=f.original.seed.application().length;
        long limit=mode.equals("image-count")?512*MIB:6*packet+7*image-(mode.equals("shared-short")?1:0);
        var budget=new MembershipResources(limit);var events=new ArrayList<Map<String,Object>>();var held=new ArrayList<MembershipSourceReceive>();
        var counterEvents=new ArrayList<Map<String,Object>>();boolean[] recordingCounter={false};
        Files.createDirectory(raw.resolve("states"));boolean success=false;String rejected=null;
        try {
            try(var owner=MembershipGrantJournal.openBootstrapped(authority,target.materialization().directory(),f.result.root(),target.identity(),budget,
                    MembershipGrantJournal.MAXIMUM,point->{if(recordingCounter[0])counterEvents.add(Map.of("point",point,"usage",usage(budget)));})) {
                var source=owner.beginActivation();
                try(var export=owner.exportSource(source.basis,V53SourceExchangeTest.BUDGET)) {
                    snapshotGroup(f,raw.resolve("captured"));Path exported=Files.createDirectory(raw.resolve("exported"));var contents=new ArrayList<Map<String,Object>>();
                    for(var content:export.contents()) {
                        Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));
                        contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                    }
                    contents.sort(Comparator.comparing(v->(String)v.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
                    var baseline=usage(budget);observe(raw,scratch,authority,"baseline",budget,events);
                    int complete=mode.equals("shared-short")?4:5;
                    for(int n=0;n<complete;n++) {
                        var receiving=receive(scratch.resolve("copy-"+n),export,budget,n==0);held.add(receiving);
                        send(receiving,export,receiving.packetBinding());for(var part:receiving.imageBindings())send(receiving,export,part);
                        assertArrayEquals(source.capsule.packet.bytes(),receiving.packet().bytes());receiving.packet().verifyImages(receiving.images());
                        observe(raw,scratch,authority,"complete-"+n,budget,events);
                    }
                    Path denied=scratch.resolve("denied");var before=usage(budget);
                    if(mode.equals("shared-exact")) {
                        assertEquals(limit,budget.usage().staging());
                        rejected=assertThrows(IllegalArgumentException.class,()->receive(denied,export,budget,false)).getMessage();
                        assertEquals("shared staging capacity",rejected);assertFalse(Files.exists(denied));assertEquals(before,usage(budget));
                        observe(raw,scratch,authority,"refused",budget,events);
                    }else {
                        try(var receiving=receive(denied,export,budget,false)) {
                            rejected=assertThrows(IllegalArgumentException.class,()->send(receiving,export,receiving.packetBinding())).getMessage();
                            assertEquals(mode.equals("image-count")?"resource ownership/count":"shared staging capacity",rejected);
                            assertThrows(IllegalArgumentException.class,receiving::imageBindings);
                            assertEquals(Set.of("source.gscp"),MembershipBasisSources.children(denied,8));
                            observe(raw,scratch,authority,"refused",budget,events);
                        }
                    }
                    assertFalse(Files.exists(denied));assertEquals(before,usage(budget));observe(raw,scratch,authority,"refused-clean",budget,events);
                    snapshotGroup(f,raw.resolve("after"));
                    // Existing durable counter work still fits while all successful copies remain charged.
                    // This does not claim that FINAL/application publication is qualified under this pressure.
                    recordingCounter[0]=true;
                    try {assertEquals(3,owner.reserveCounter());}finally {recordingCounter[0]=false;}
                    assertEquals(COUNTER_CUTS,counterEvents.stream().map(v->v.get("point")).toList());
                    for(var event:counterEvents)assertEquals(before,event.get("usage"));
                    assertEquals(before,usage(budget));observe(raw,scratch,authority,"counter-forced",budget,events);
                    for(var receiving:held)receiving.close();held.clear();assertEquals(baseline,usage(budget));
                    observe(raw,scratch,authority,"scratch-drained",budget,events);
                }finally {for(var receiving:held)receiving.close();}
            }
            assertEquals(0,budget.usage().leases());observe(raw,scratch,authority,"owner-closed",budget,events);success=true;
        }finally {
            Files.write(raw.resolve("events.json"),canonical(events,65536));
            Files.write(raw.resolve("counter-events.json"),canonical(counterEvents,65536));
            Files.write(raw.resolve("result.json"),canonical(Map.of("size",size,"mode",mode,"stagingLimit",limit,
                "rejection",rejected==null?"not-reached":rejected,"status",success?"PASS":"FAIL"),65536));
        }
    }
    static void snapshotGroup(V53BootstrapPublicationTest.Fixture f,Path output)throws Exception {
        Files.createDirectory(output);for(var member:f.request.targets())snapshot(member.replicaDirectory(),output.resolve(member.identity().nodeId().value()));
    }
}
