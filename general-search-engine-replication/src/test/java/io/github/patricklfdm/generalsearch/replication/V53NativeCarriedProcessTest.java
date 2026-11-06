package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual old applied DATA, whole-group death during carry, same-directory recovery. */
class V53NativeCarriedProcessTest {
    @TempDir Path temp;
    static void await(CountDownLatch boundary,Future<?> reader,Process child,Path stderr,long seconds)throws Exception {
        long start=System.nanoTime();
        while(!boundary.await(100,TimeUnit.MILLISECONDS)) {
            if(reader.isDone()){reader.get();fail("child ended before declared cut, exit="+(child.isAlive()?"live":child.exitValue())+"; "+stderr+"\n"+Files.readString(stderr));}
            assertTrue(System.nanoTime()-start<TimeUnit.SECONDS.toNanos(seconds),"native carried child cut timeout");
        }
    }
    void run(String point,String mode)throws Exception {run(point,mode,"DATA");}
    void run(String point,String mode,String kind)throws Exception {
        run(point,mode,kind,false);
    }
    void run(String point,String mode,String kind,boolean observeResources)throws Exception {
        run(point,mode,kind,observeResources,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,observeCompletion,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion,boolean observeLedgers)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,observeCompletion,observeLedgers,false);
    }
    void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion,boolean observeLedgers,boolean observeReplay)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,observeCompletion,observeLedgers,observeReplay,false);
    }
    void runApplicationCut(String mode,String kind)throws Exception {
        run("APPLY_ACK_DIRECTORY_FORCED",mode,kind,true,false,false,false,false,false,false,false,true);
    }
    void runApplicationRecovery(String mode,String kind)throws Exception {
        run("APPLY_ACK_DIRECTORY_FORCED",mode,kind,true,false,false,false,false,false,false,false,true,true);
    }
    void runApplicationMaintenance(String mode,String kind)throws Exception {
        run("APPLY_ACK_DIRECTORY_FORCED",mode,kind,true,false,false,false,false,false,false,false,true,true,true);
    }
    private void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion,boolean observeLedgers,boolean observeReplay,boolean observeApplicationCut)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,observeCompletion,observeLedgers,observeReplay,observeApplicationCut,false);
    }
    private void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion,boolean observeLedgers,boolean observeReplay,boolean observeApplicationCut,boolean observeApplicationRetirement)throws Exception {
        run(point,mode,kind,observeResources,observeRetirement,observeFloor,observeCampaign,observeVotes,observeCompletion,observeLedgers,observeReplay,observeApplicationCut,observeApplicationRetirement,false);
    }
    private void run(String point,String mode,String kind,boolean observeResources,boolean observeRetirement,boolean observeFloor,boolean observeCampaign,boolean observeVotes,boolean observeCompletion,boolean observeLedgers,boolean observeReplay,boolean observeApplicationCut,boolean observeApplicationRetirement,boolean observeApplicationMaintenance)throws Exception {
        assertTrue(Set.of("DATA","INTENT","FINAL").contains(kind));
        boolean data=kind.equals("DATA");int size=data?3:4,index=data?1:kind.equals("INTENT")?5:6;
        assertTrue(!observeRetirement || observeResources && !data,"retirement requires original context resources");
        assertTrue(!observeFloor || observeRetirement,"floor observation requires original retirement prefixes");
        assertTrue(!observeCampaign || observeFloor,"campaign observation requires original floor prefixes");
        assertTrue(!observeVotes || observeCampaign,"vote observation requires original campaign prefixes");
        assertTrue(!observeCompletion || observeVotes,"completion observation requires original vote prefixes");
        assertTrue(!observeLedgers || observeCompletion,"ledger observation requires original completion prefixes");
        assertTrue(!observeReplay || observeLedgers,"replay observation requires original ledger prefixes");
        assertTrue(!observeApplicationCut || observeResources && !observeRetirement && !data && point.equals("APPLY_ACK_DIRECTORY_FORCED"),"application capture explicit original resource history");
        assertTrue(!observeApplicationRetirement || observeApplicationCut,"application retirement requires original interrupted prefixes");
        assertTrue(!observeApplicationMaintenance || observeApplicationRetirement,"application maintenance requires original retirement history");
        Path applicationMaintenance=observeApplicationMaintenance?Files.createDirectories(Path.of("target/v53-native-carried-application-maintenance-prefixes/run-"+UUID.randomUUID())):null;
        if(observeApplicationMaintenance) {
            for(String family:List.of("retirement","floors","campaigns"))Files.createDirectories(applicationMaintenance.resolve("maintenance/"+family));
            System.out.println("v53NativeCarriedApplicationMaintenancePrefixesEvidence="+applicationMaintenance.toAbsolutePath());
        }
        Path applicationRetirement=observeApplicationMaintenance?Files.createDirectory(applicationMaintenance.resolve("previous")):
                observeApplicationRetirement?Files.createDirectories(Path.of("target/v53-native-carried-application-retirement-prefixes/run-"+UUID.randomUUID())):null;
        if(observeApplicationRetirement)System.out.println("v53NativeCarriedApplicationRetirementPrefixesEvidence="+applicationRetirement.toAbsolutePath());
        Path applicationCut=observeApplicationRetirement?Files.createDirectory(applicationRetirement.resolve("previous")):
                observeApplicationCut?Files.createDirectories(Path.of("target/v53-native-carried-application-prefixes/run-"+UUID.randomUUID())):null;
        if(observeApplicationCut)System.out.println("v53NativeCarriedApplicationPrefixesEvidence="+applicationCut.toAbsolutePath());
        Path replay=observeReplay?Files.createDirectories(Path.of("target/v53-native-carried-replay-prefixes/run-"+UUID.randomUUID())):null;
        if(observeReplay){Files.createDirectory(replay.resolve("replay"));System.out.println("v53NativeCarriedReplayPrefixesEvidence="+replay.toAbsolutePath());}
        Path ledgers=observeReplay?Files.createDirectory(replay.resolve("previous")):observeLedgers?Files.createDirectories(Path.of("target/v53-native-carried-ledger-prefixes/run-"+UUID.randomUUID())):null;
        if(observeLedgers){Files.createDirectory(ledgers.resolve("ledgers"));System.out.println("v53NativeCarriedLedgerPrefixesEvidence="+ledgers.toAbsolutePath());}
        Path completion=observeLedgers?Files.createDirectory(ledgers.resolve("previous")):observeCompletion?Files.createDirectories(Path.of("target/v53-native-carried-completion-prefixes/run-"+UUID.randomUUID())):null;
        if(observeCompletion){Files.createDirectory(completion.resolve("completion"));System.out.println("v53NativeCarriedCompletionPrefixesEvidence="+completion.toAbsolutePath());}
        Path votes=observeCompletion?Files.createDirectory(completion.resolve("previous")):observeVotes?Files.createDirectories(Path.of("target/v53-native-carried-vote-prefixes/run-"+UUID.randomUUID())):null;
        if(observeVotes){Files.createDirectory(votes.resolve("votes"));System.out.println("v53NativeCarriedVotePrefixesEvidence="+votes.toAbsolutePath());}
        Path campaigns=observeVotes?Files.createDirectory(votes.resolve("previous")):
                observeCampaign?Files.createDirectories(Path.of("target/v53-native-carried-campaign-prefixes/run-"+UUID.randomUUID())):null;
        if(observeCampaign){Files.createDirectory(campaigns.resolve("campaigns"));System.out.println("v53NativeCarriedCampaignPrefixesEvidence="+campaigns.toAbsolutePath());}
        Path floors=observeCampaign?Files.createDirectory(campaigns.resolve("maintenance")):
                observeFloor?Files.createDirectories(Path.of("target/v53-native-carried-floor-prefixes/run-"+UUID.randomUUID())):null;
        if(observeFloor){Files.createDirectory(floors.resolve("floors"));System.out.println("v53NativeCarriedFloorPrefixesEvidence="+floors.toAbsolutePath());}
        Path prefix=observeFloor?Files.createDirectory(floors.resolve("prefixes")):
                observeRetirement?Files.createDirectories(Path.of("target/v53-native-carried-prefixes/run-"+UUID.randomUUID())):null;
        if(observeRetirement){Files.createDirectory(prefix.resolve("retirement"));System.out.println("v53NativeCarriedPrefixesEvidence="+prefix.toAbsolutePath());}
        Path container=observeApplicationCut?Files.createDirectory(applicationCut.resolve("observed")):observeRetirement?Files.createDirectory(prefix.resolve("observed")):
                observeResources?Files.createDirectories(Path.of("target/v53-native-carried-resources/run-"+UUID.randomUUID())):null;
        Path raw=observeResources?Files.createDirectory(container.resolve("history")):Files.createDirectories(Path.of("target/"+(data?"v53-native-carried-process":"v53-native-carried-transition-process")+"/run-"+UUID.randomUUID()));
        if(observeResources){Files.createDirectory(container.resolve("resources"));System.out.println("v53NativeCarriedResourcesEvidence="+container.toAbsolutePath());}
        System.out.println("v53NativeCarriedProcessEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group")),size,false));
        f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var journal=f.open(target,"initialize-retention")){journal.initializePeerRetention();journal.initializeFutureRetention();}
        if(data)V53CarriedSlotDriverTest.prepare(f,"APPLIED",true);
        else V53TransitionRoundDriverTest.prepare(f,"CARRIED_"+kind,size);
        f.snapshot("before-network");
        byte[] original=Files.readAllBytes(raw.resolve("entry-"+index+".gsr")),payload=Files.readAllBytes(raw.resolve("payload-"+index+".bin"));
        Path process=Files.createDirectory(raw.resolve("process"));var paths=new ArrayList<Map<String,Object>>();
        for(var t:f.request.targets())paths.add(Map.of("replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString(),
                "scratch",Files.createDirectory(temp.resolve(t.identity().nodeId().value()+"-scratch")).toString()));
        Path spec=process.resolve("spec.json");Files.write(spec,canonical(data?Map.of("nodes",paths):Map.of("nodes",paths,"kind",kind),65536));
        var events=new ArrayList<Map<String,Object>>();var wire=new ArrayList<Map<String,Object>>();
        var records=new ArrayList<Map<String,Object>>();var children=new ArrayList<Process>();boolean passed=false;
        try(var readers=Executors.newCachedThreadPool()) {
            try {
                for(int life:List.of(1,2)) {
                    System.out.println("v53NativeCarriedProcessStage="+life+"-start "+point+" "+mode);
                    var stopped=new CountDownLatch(1);Path stdout=process.resolve("life-"+life+".jsonl"),stderr=process.resolve("life-"+life+".stderr");
                    var command=new ArrayList<>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                            V53NativeCarriedProcessWorker.class.getName(),spec.toAbsolutePath().toString(),Integer.toString(life),point,mode));
                    if(observeResources)command.add(container.resolve("resources/life-"+life).toAbsolutePath().toString());
                    if(observeRetirement)command.add(prefix.resolve("retirement/life-"+life).toAbsolutePath().toString());
                    if(observeFloor)command.add(floors.resolve("floors/life-"+life).toAbsolutePath().toString());
                    if(observeCampaign)command.add(campaigns.resolve("campaigns/life-"+life).toAbsolutePath().toString());
                    if(observeVotes)command.add(votes.resolve("votes/life-"+life).toAbsolutePath().toString());
                    if(observeCompletion)command.add(completion.resolve("completion/life-"+life).toAbsolutePath().toString());
                    if(observeLedgers)command.add(ledgers.resolve("ledgers/life-"+life).toAbsolutePath().toString());
                    if(observeReplay)command.add(replay.resolve("replay/life-"+life).toAbsolutePath().toString());
                    if(observeApplicationMaintenance)for(String family:List.of("retirement","floors","campaigns"))
                        command.add(applicationMaintenance.resolve("maintenance/"+family+"/life-"+life).toAbsolutePath().toString());
                    if(observeApplicationCut && life==1)command.addAll(List.of("--application-cut-capture",applicationCut.resolve("application").toAbsolutePath().toString()));
                    if(observeApplicationRetirement && life==2)command.addAll(List.of("--application-retirement-capture",applicationRetirement.resolve("retirement").toAbsolutePath().toString()));
                    Process child=new ProcessBuilder(command)
                            .redirectError(stderr.toFile()).start();children.add(child);
                    var record=new TreeMap<String,Object>();record.put("life",life);record.put("pid",child.pid());records.add(record);
                    Future<?> reader=readers.submit(()->{
                        try(var input=child.inputReader(StandardCharsets.UTF_8);var output=child.outputWriter(StandardCharsets.UTF_8);
                            var retained=Files.newBufferedWriter(stdout,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW)) {
                            String line;while((line=input.readLine())!=null) {
                                retained.write(line);retained.newLine();retained.flush();var message=object(parse(line.getBytes(StandardCharsets.UTF_8),8*1024*1024));
                                String action=(String)message.get("action");Object value=message.get("value");
                                switch(action) {
                                    case "started" -> {assertEquals(Map.of("pid",child.pid(),"life",(long)life,"mode",mode,"cut",point),value);record.put("started",value);}
                                    case "opened" -> {assertEquals(life,number(value));record.put("opened",true);f.snapshot("life-"+life+"-opened");}
                                    case "event" -> events.add(object(value));
                                    case "response" -> {var row=object(value);wire.add(object(row.get("wire")));events.add(object(row.get("event")));}
                                    case "snapshot" -> f.snapshot((String)value);
                                    case "installed" -> {
                                        var row=object(value);assertEquals(life,number(row.get("life")));String name="life-"+life+"-installed-"+number(row.get("number"));
                                        Files.write(raw.resolve(name+".gsr"),Base64.getDecoder().decode((String)row.get("bytes")));f.snapshot(name);
                                    }
                                    case "cut" -> {
                                        assertEquals(1,life);assertEquals(Map.of("name",point,"mode",mode,"pid",child.pid()),value);
                                        for(var t:f.request.targets()) {
                                            var locked=assertThrows(ReplicationException.class,()->{try(var ignored=MembershipOwnership.own(t.replicaDirectory().resolve("replica.lock"),false)){fail("live owner unlocked");}});
                                            assertEquals("membership file already owned",locked.getMessage());
                                        }
                                        record.put("allLocksHeldBeforeDeath",true);f.snapshot("at-cut");
                                    }
                                    case "ready" -> {assertEquals(2,life);Files.write(raw.resolve("ready.gsr"),Base64.getDecoder().decode((String)value));}
                                    case "closed" -> {assertEquals(2,life);var v=object(value);assertEquals(2,number(v.get("life")));assertEquals(0,number(v.get("clientCalls")));record.put("closed",v);}
                                    default -> throw new IOException("unexpected native carried observation: "+action);
                                }
                                output.write("ACK\n");output.flush();if(action.equals("cut") || action.equals("closed"))stopped.countDown();
                            }
                        }return null;
                    });
                    await(stopped,reader,child,stderr,data?210:630);if(life==1 && mode.equals("kill"))child.destroyForcibly();
                    assertTrue(child.waitFor(15,TimeUnit.SECONDS),"child terminal timeout");reader.get(10,TimeUnit.SECONDS);
                    record.put("exit",child.exitValue());assertEquals(life==2?0:mode.equals("halt")?73:137,child.exitValue(),Files.readString(stderr));
                    if(life==1) {
                        for(var t:f.request.targets())try(var ignored=MembershipOwnership.own(t.replicaDirectory().resolve("replica.lock"),false)){}
                        record.put("allLocksReleasedAfterDeath",true);f.snapshot("before-reopen");
                        events.add(Map.of("event","GROUP_CRASH","incarnation",life));
                    }
                    System.out.println("v53NativeCarriedProcessStage="+life+"-closed");
                }
                f.snapshot("after-close");
                assertArrayEquals(original,Files.readAllBytes(raw.resolve("entry-"+index+".gsr")));assertArrayEquals(payload,Files.readAllBytes(raw.resolve("payload-"+index+".bin")));
                var target=f.request.targets().getFirst();var before=V53ReplayFilesTest.files(target.replicaDirectory());
                try(var owner=f.open(target,"inspect-final")) {
                    var copy=owner.floorCopyCurrent();var context=copy.capsule.context;
                    assertEquals(data?2L:7L,context.cut.get("index"));assertEquals(data?1L:0L,context.catalog.get("applicationSequence"));
                    if(data)assertEquals(1L,context.catalog.get("lastDataIndex"));
                    else {
                        assertNull(context.catalog.get("active"));assertNull(context.view.get("operation"));
                        assertEquals(List.of("node-1","node-2","node-3"),list(context.view.get("new")));
                        assertEquals("COMPLETED",object(list(context.catalog.get("results")).getLast()).get("phase"));
                    }
                    var image=MembershipApplicationImage.read(builder().configuration(),target.materialization(),
                            copy.fileBytes(copy.capsule.terminal().application()+".image"),temp.resolve("inspect-image"));
                    assertEquals(data?List.of(new Doc(303,"admitted-original")):List.of(),image.documents());
                }
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));passed=true;
            } finally {
                for(var child:children)if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(10,TimeUnit.SECONDS));}
                Files.write(raw.resolve("events.json"),V53EvidenceArray.encode(events,16*1024*1024));Files.write(raw.resolve("wire.json"),V53EvidenceArray.encode(wire,32*1024*1024));
                V53NativeApplicationTest.save(f);
                Files.write(process.resolve("result.json"),canonical(Map.of("status",passed?"PARTIAL":"FAIL","producerPassed",passed,"phase3Complete",false,
                        "mode",mode,"cut",point,"oldPhase",data?"APPLIED":"ACCEPTED","carriedKind",kind,"children",records,"clientCalls",0,"powerLoss",false),65536));
            }
        }
    }
    @Test void haltDuringCarriedCertificateCleanup()throws Exception{run("NATIVE_RETIREMENT_CERTIFICATE_RETAINED","halt");}
    @Test void killDuringCarriedCertificateCleanup()throws Exception{run("NATIVE_RETIREMENT_CERTIFICATE_RETAINED","kill");}
    @Test void haltAfterCarriedAcceptRename()throws Exception{run("ACCEPT_RENAMED","halt");}
    @Test void killAfterCarriedAcceptRename()throws Exception{run("ACCEPT_RENAMED","kill");}
    @Test void haltAfterCarriedProofRename()throws Exception{run("PROOF_RENAMED","halt");}
    @Test void killAfterCarriedProofRename()throws Exception{run("PROOF_RENAMED","kill");}
    @Test void haltAfterCarriedApplicationForce()throws Exception{run("APPLY_ACK_DIRECTORY_FORCED","halt");}
    @Test void killAfterCarriedApplicationForce()throws Exception{run("APPLY_ACK_DIRECTORY_FORCED","kill");}
}
