package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** One whole native PREPARE 1/2/3 history. Kept independent for eventual hosted
 * parallel qualification; compile alone is not executed/native evidence. */
class V53CurrentHeadNetworkTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(900);
    @Test void retiredTypedSecondRevisionAcquiresThirdRevisionAcrossParentReopen()throws Exception {run(false);}
    void run(boolean installInactive)throws Exception {
        run(installInactive,false);
    }
    void run(boolean installInactive,boolean selectInactive)throws Exception {
        run(installInactive,selectInactive,false);
    }
    void run(boolean installInactive,boolean selectInactive,boolean alternate)throws Exception {
        assertTrue(installInactive || !selectInactive,"selection requires original inactive installation");
        assertTrue(!alternate || selectInactive,"alternation requires the selected original third revision");
        var driver=new V53RoundDriverTest();driver.temp=temp;var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network(3,driver.controlBounds(),BUDGET,f->{},true);
                var round=driver.driver(n,MembershipRoundDriver.Events.NONE,BUDGET)) {
            Path raw=n.f.raw;System.out.println((alternate?"v53LearnerAlternationEvidence=":selectInactive?"v53LearnerSlotHeadEvidence=":installInactive?"v53LearnerSlotEvidence=":"v53CurrentHeadEvidence=")+raw.toAbsolutePath());round.start();int port;
            try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),n.owners.getFirst().activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner-replica"),temp.resolve("learner-operation"));
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("learner-core"),2),n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            var resources=new MembershipResources(512*MIB);var events=new ArrayList<String>();var observations=new LinkedHashMap<String,Object>();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            MembershipTransport.Events capture=(event,q,a)->{if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(q,a));};
            Throwable failure=null;
            try {
            byte[] reserve=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);Files.write(raw.resolve("learner-reserve-payload.bin"),reserve);
            round.submit("RESERVE",reserve);round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));n.f.snapshot("before-current-head");
            MembershipLearnerPlan summary;
            try(var noListener=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"));
                    var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,capture,()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                var original=source.fetch(temp.resolve("first-receiving"));copy(original,raw.resolve("revision-one"));summary=source.plan(events::add);
                try(var store=source.admit(summary,events::add);
                        var first=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,events::add)) {
                    source.close();var prepared=first.retainGeneration();round.submit("PREPARE",canonical(Map.of("number",1L,"revision",2L),8192));
                    try(var refresh=MembershipLearnerSource.refresh(prepared,targets.getFirst(),n.bounds,capture,System::nanoTime,System.nanoTime(),BUDGET)) {
                        copy(refresh.fetch(temp.resolve("second-receiving")),raw.resolve("revision-two"));
                        var installed=refresh.installSuccessor(events::add);
                        try(var second=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,2),builder().configuration(),config,events::add)) {
                            Files.write(raw.resolve("current-receipt.gsr"),second.receipt().bytes());
                            if(selectInactive)observe(raw.resolve("before-seed-handoff"),summary,resources,events,wire,observations);
                            var head=second.promoteSuccessor();
                            if(selectInactive)observe(raw.resolve("selected-seed-head"),summary,resources,events,wire,observations);
                            head.retirePredecessor();
                            if(selectInactive)observe(raw.resolve("retired-seed-predecessor"),summary,resources,events,wire,observations);
                            assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                            assertFalse(Files.exists(request.replicaDirectory().resolve("learner")));assertFalse(Files.exists(MembershipLearnerMaterialization.directory(summary)));
                            V53SuccessorTypedNetworkTest.snapshotSuccessor(raw.resolve("retired-successor"),summary);
                            V53JournalApplicationTest.copy(MembershipLearnerSuccessor.typedDirectory(summary),raw.resolve("retired-typed"));
                        }
                    }
                }
            }
            assertEquals(0,resources.usage().leases());n.f.snapshot("after-current-retirement");
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",3L),8192));
            try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                    var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.promotedSuccessor(),2),builder().configuration(),config,events::add)) {
                var head=typed.currentHead();var baseline=resources.usage();var original=head.source().packet.bytes();
                MembershipLearnerSlot.View pending=null;
                try(var refresh=MembershipLearnerSource.refresh(head,targets.getFirst(),n.bounds,capture,System::nanoTime,System.nanoTime(),BUDGET)) {
                    var received=refresh.fetch(temp.resolve("third-receiving"));assertEquals(5L,number(received.capsule.context.cut.get("index")));
                    assertEquals(3L,number(object(list(received.capsule.context.catalog.get("results")).getFirst()).get("revision")));
                    assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(1,resources.usage().counts().get(Unit.LEARNER));
                    assertFalse(received.capsule.context.voters().contains(joining.nodeId().value()));copy(received,raw.resolve("revision-three"));
                    assertArrayEquals(Files.readAllBytes(raw.resolve("current-receipt.gsr")),typed.receipt().bytes());
                    if(installInactive) {
                        var slot=refresh.installSlot(events::add);pending=slot;
                        try(var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,3),builder().configuration(),config,events::add)) {
                            Files.write(raw.resolve("third-receipt.gsr"),third.receipt().bytes());
                            assertEquals("learner inactive slot is not the current head",assertThrows(IllegalArgumentException.class,third::currentHead).getMessage());
                        }
                        assertEquals(2,resources.usage().counts().get(Unit.GENERATION));assertFalse(resources.usage().counts().containsKey(Unit.LEARNER));
                        V53JournalApplicationTest.copy(MembershipLearnerSlot.directory(summary),raw.resolve("installed-slot"));
                        V53JournalApplicationTest.copy(MembershipLearnerSlot.typedDirectory(summary),raw.resolve("installed-slot-typed"));
                    }
                }
                if(selectInactive) {
                    // The source transport is already closed. Selection and
                    // retirement must use only the retained durable owner.
                    observe(raw.resolve("before-slot-selection"),summary,resources,events,wire,observations);
                    try(var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,3),builder().configuration(),config,events::add)) {
                        assertArrayEquals(Files.readAllBytes(raw.resolve("third-receipt.gsr")),third.receipt().bytes());
                        var selected=third.promoteSlot(head);assertThrows(IllegalArgumentException.class,head::check);
                        assertEquals(2,resources.usage().counts().get(Unit.GENERATION));
                        observe(raw.resolve("selected-slot-head"),summary,resources,events,wire,observations);
                        selected.retirePredecessor();assertEquals(1,resources.usage().counts().get(Unit.GENERATION));
                        assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                        assertFalse(Files.exists(MembershipLearnerSuccessor.directory(summary).resolve(MembershipLearnerSuccessor.SOURCE)));
                        assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(summary)));
                        observe(raw.resolve("retired-slot-seed"),summary,resources,events,wire,observations);
                    }
                }else {
                    if(!installInactive)assertEquals(baseline,resources.usage());
                    else assertEquals(2,resources.usage().counts().get(Unit.GENERATION));
                    assertArrayEquals(original,head.source().packet.bytes());
                }
                assertFalse(Files.exists(config.materialization().directory()));
            }
            assertEquals(0,resources.usage().leases());
            if(selectInactive) {
                try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                        var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.currentSource(),3),builder().configuration(),config,events::add)) {
                    assertArrayEquals(Files.readAllBytes(raw.resolve("third-receipt.gsr")),third.receipt().bytes());third.currentHead().check();
                    assertEquals(request.root().historyId(),third.state().history());assertTrue(third.state().documents().isEmpty());
                    assertFalse(third.currentHead().source().context.voters().contains(joining.nodeId().value()));
                    assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                    observe(raw.resolve("reopened-slot-head"),summary,resources,events,wire,observations);
                    var before=V53ReplayFilesTest.files(raw.resolve("retired-slot-seed"));var after=V53ReplayFilesTest.files(raw.resolve("reopened-slot-head"));
                    // Cold charges may conservatively differ in extent; exact
                    // authority bytes/inodes must not change during reopen.
                    before.remove("resources.json");after.remove("resources.json");assertEquals(before,after);
                }
                assertEquals(0,resources.usage().leases());
            }else if(installInactive) {
                try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                        var second=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.promotedSuccessor(),2),builder().configuration(),config,events::add)) {
                    var slot=store.resumeSlot(second.currentHead());
                    try(var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,3),builder().configuration(),config,events::add)) {
                        assertArrayEquals(Files.readAllBytes(raw.resolve("third-receipt.gsr")),third.receipt().bytes());
                        assertArrayEquals(Files.readAllBytes(raw.resolve("current-receipt.gsr")),second.receipt().bytes());
                    }
                    V53JournalApplicationTest.copy(MembershipLearnerSlot.directory(summary),raw.resolve("reopened-slot"));
                    V53JournalApplicationTest.copy(MembershipLearnerSlot.typedDirectory(summary),raw.resolve("reopened-slot-typed"));
                }
                assertEquals(0,resources.usage().leases());
            }
            n.f.snapshot("after-third-acquisition");var cycles=new ArrayList<Map<String,Object>>();
            if(alternate)try(var noListener=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"))) {
                // One reservation, native group, round deadline and learner
                // resource pool. Each whole history is an indivisible hosted unit.
                for(long revision=4;revision<=6;revision++) {
                    String stage="cycle-"+revision;int firstExchange=wire.size();byte[] receipt;
                    System.out.println("v53LearnerNativeRevision="+revision);
                    n.f.snapshot(stage+"-before-prepare");round.submit("PREPARE",canonical(Map.of("number",1L,"revision",revision),8192));n.f.snapshot(stage+"-after-prepare");
                    try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                            var current=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.currentSource(),revision-1),builder().configuration(),config,events::add)) {
                        var previous=current.currentHead();MembershipLearnerSlot.View pending;
                        observe(raw.resolve(stage+"-before-transfer"),summary,resources,events,wire,observations);
                        try(var refresh=MembershipLearnerSource.refresh(previous,targets.getFirst(),n.bounds,capture,System::nanoTime,System.nanoTime(),BUDGET)) {
                            var received=refresh.fetch(temp.resolve(stage+"-receiving"));
                            assertEquals(revision+2,number(received.capsule.context.cut.get("index")));
                            assertEquals(revision,number(object(list(received.capsule.context.catalog.get("results")).getFirst()).get("revision")));
                            assertFalse(received.capsule.context.voters().contains(joining.nodeId().value()));copy(received,raw.resolve(stage+"-received"));
                            pending=refresh.installSlot(events::add);
                        }
                        observe(raw.resolve(stage+"-installed"),summary,resources,events,wire,observations);
                        try(var next=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,revision),builder().configuration(),config,events::add)) {
                            receipt=next.receipt().bytes();Files.write(raw.resolve(stage+"-receipt.gsr"),receipt);
                            observe(raw.resolve(stage+"-before-selection"),summary,resources,events,wire,observations);
                            var selected=next.promoteSlot(previous);assertThrows(IllegalArgumentException.class,previous::check);
                            assertThrows(IllegalArgumentException.class,pending::source);assertEquals(2,resources.usage().counts().get(Unit.GENERATION));
                            observe(raw.resolve(stage+"-selected"),summary,resources,events,wire,observations);selected.retirePredecessor();
                            assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                            observe(raw.resolve(stage+"-retired"),summary,resources,events,wire,observations);
                        }
                        assertFalse(Files.exists(config.materialization().directory()));
                    }
                    assertEquals(0,resources.usage().leases());
                    try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                            var current=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.currentSource(),revision),builder().configuration(),config,events::add)) {
                        var head=current.currentHead();head.check();assertArrayEquals(receipt,current.receipt().bytes());
                        assertEquals(request.root().historyId(),current.state().history());assertTrue(current.state().documents().isEmpty());
                        assertFalse(head.source().context.voters().contains(joining.nodeId().value()));
                        assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                        observe(raw.resolve(stage+"-reopened"),summary,resources,events,wire,observations);
                        var before=V53ReplayFilesTest.files(raw.resolve(stage+"-retired"));var after=V53ReplayFilesTest.files(raw.resolve(stage+"-reopened"));
                        before.remove("resources.json");after.remove("resources.json");assertEquals(before,after);
                        var selector=object(parse(Files.readAllBytes(MembershipLearnerSlot.directory(summary).resolve(MembershipLearnerSlot.HEAD)),MembershipLearnerSlot.HEAD_MAXIMUM));
                        assertEquals(revision-2,number(selector.get("sequence")));assertEquals(revision%2==0?"a":"b",selector.get("slot"));
                        cycles.add(Map.of("revision",revision,"sequence",revision-2,"slot",selector.get("slot"),"source",selector.get("source"),
                                "generation",selector.get("generation"),"receipt",hash(receipt),"wireStart",(long)firstExchange,"wireEnd",(long)wire.size()));
                    }
                    assertEquals(0,resources.usage().leases());
                }
            }
            round.submit("CANCEL",canonical(Map.of("number",1L),8192));
            var result=new TreeMap<String,Object>(Map.of("status","PASS","scope",alternate?"native-alternating-learner-slots":selectInactive?"native-selected-slot-head":installInactive?"native-inactive-slot":"native-current-head-acquisition",
                    "installedThirdRevision",installInactive,"voter",false,"publicReady",false,"phase3Complete",false,"testBudgetSeconds",900L));
            if(selectInactive){result.put("selectedThirdRevision",true);result.put("seedRetired",true);}
            if(alternate){result.put("cycles",cycles);result.put("lastRevision",6L);result.put("independentReplayQualified",false);}
            Files.write(raw.resolve("current-head-result.json"),canonical(result,4096));
            }catch(Exception|Error error){failure=error;throw error;}
            finally {
                try{writeObservations(raw,events,wire,alternate?observations:null);}
                catch(Exception|Error error){if(failure!=null)failure.addSuppressed(error);else throw error;}
            }
        }
    }
    /** Preserve partial observations without synthesizing a successful result.
     * A failure to retain evidence must not hide the original history failure. */
    static void writeObservations(Path root,List<String> events,List<Map<String,Object>> wire,Map<String,Object> observations)throws Exception {
        Files.write(root.resolve("current-head-events.json"),canonical(events,65536));
        Files.write(root.resolve("current-head-wire.json"),canonical(wire,8*1024*1024));
        if(observations!=null)Files.write(root.resolve("current-head-stages.json"),evidenceJson(observations,16384));
    }
    private static void observe(Path target,MembershipLearnerPlan summary,MembershipResources resources,
            List<String> events,List<Map<String,Object>> wire,Map<String,Object> observations)throws Exception {
        int before=events.size(),exchanges=wire.size();snapshotLearner(target,summary,resources);
        assertEquals(before,events.size());assertEquals(exchanges,wire.size());
        assertNull(observations.put(target.getFileName().toString(),Map.of("events",(long)before,"exchanges",(long)exchanges)));
    }
    /** Copy original bytes with their original identity observations, including
     * absent retired roots. A copied tree's new inodes are not voting evidence. */
    private static void snapshotLearner(Path target,MembershipLearnerPlan summary,MembershipResources resources)throws Exception {
        Files.createDirectory(target);var roots=new TreeMap<String,Path>();
        roots.put("operation",summary.request().operationDirectory());roots.put("replica",summary.request().replicaDirectory());
        roots.put("initial-typed",MembershipLearnerMaterialization.directory(summary));
        roots.put("seed",MembershipLearnerSuccessor.directory(summary));roots.put("seed-typed",MembershipLearnerSuccessor.typedDirectory(summary));
        roots.put("slots",MembershipLearnerSlot.directory(summary));roots.put("slot-typed",MembershipLearnerSlot.typedDirectory(summary));
        var identities=new TreeMap<String,Object>();int count=0;
        for(var entry:roots.entrySet()) {
            Path root=entry.getValue();AdmissionPaths.safe(root);var members=new TreeMap<String,Object>();
            boolean present=Files.exists(root,LinkOption.NOFOLLOW_LINKS);
            if(present) {
                try(var walk=Files.walk(root)) {
                    for(Path p:walk.sorted().toList()) {
                        assertTrue(++count<=256,"learner snapshot member bound");AdmissionPaths.safe(p);
                        String name=p.equals(root)?".":root.relativize(p).toString();
                        if(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS))members.put(name,Map.of("key",MembershipBasisSources.key(p).toString(),"directory",true));
                        else {
                            byte[] bytes=AdmissionPaths.read(p,MembershipApplicationImage.MAXIMUM);
                            var original=MembershipBasisSources.inspect(p,bytes.length,hash(bytes));
                            members.put(name,Map.of("key",original.key().toString(),"bytes",original.bytes(),"sha256",original.digest()));
                        }
                    }
                }
                V53JournalApplicationTest.copy(root,target.resolve(entry.getKey()));
            }
            identities.put(entry.getKey(),Map.of("path",root.toString(),"present",present,"members",members));
        }
        var usage=resources.usage();var counts=new TreeMap<String,Object>();usage.counts().forEach((unit,value)->counts.put(unit.name(),value.longValue()));
        Files.write(target.resolve("original-identities.json"),evidenceJson(identities,1024*1024));
        Files.write(target.resolve("resources.json"),canonical(Map.of("counts",counts,"leases",(long)usage.leases(),"metadata",usage.metadata(),"staging",usage.staging(),"queued",usage.queued()),4096));
    }
    /** Evidence member paths are not protocol field names. Keep the production
     * codec's field restrictions intact and bound this test-only serializer. */
    static byte[] evidenceJson(Object value,int maximum) {
        byte[] bytes=io.github.patricklfdm.generalsearch.admission.AdmissionJson.canonical(value).getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        assertTrue(bytes.length<=maximum,"learner evidence JSON capacity");return bytes;
    }
    private static void copy(MembershipFloor.Copy copy,Path destination)throws Exception {
        copy.check();Files.createDirectory(destination);for(String name:copy.fileNames())Files.write(destination.resolve(name),copy.fileBytes(name));copy.check();
    }
}
