package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53OwnedRecoveryTest {
    @TempDir Path temp;
    static Map<String,Object> child(V53BootstrapPublicationTest.Fixture f,int node,String operation,Path log,Path ballot)throws Exception {
        var t=f.request.targets().get(node);var args=new ArrayList<>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53OwnedRecoveryWorker.class.getName(),t.replicaDirectory().toString(),t.materialization().directory().toString(),operation));
        if(ballot!=null)args.add(ballot.toString());
        Process process=new ProcessBuilder(args).redirectErrorStream(true).redirectOutput(log.toFile()).start();V53OwnedGenerationTest.finished(process,0,log);
        var result=object(parse(Files.readAllBytes(log),65536));assertEquals("PASS",result.get("status"));assertEquals(0L,result.get("copiedObservations"));return result;
    }
    static void freshCampaign(V53BootstrapPublicationTest.Fixture f,Path processes)throws Exception {
        var proposer=f.request.targets().getFirst();var allocated=child(f,0,"allocate",processes.resolve("allocate.json"),null);
        f.calls.add(Map.of("node","node-1","operation","allocate-2","events",allocated.get("events")));assertEquals(3L,allocated.get("counter"));
        f.ballot=Map.of("counter",3L,"proposer","node-1","incarnation",proposer.identity().storageId().toString());
        Path ballot=processes.resolve("ballot.json");Files.write(ballot,canonical(f.ballot,4096));
        var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var obsolete=new TreeMap<String,String>();
        for(int node=0;node<f.request.targets().size();node++) {
            var t=f.request.targets().get(node);
            try(var owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
                owner.originalBasis().ifPresent(b->obsolete.put(t.identity().nodeId().value(),(String)b.value().get("basisId")));
            }
            var reply=child(f,node,"prepare",processes.resolve("prepare-"+(node+1)+".json"),ballot);
            f.calls.add(Map.of("node",t.identity().nodeId().value(),"operation","prepare-2","events",reply.get("events")));
            // Reopening to collect the original is deliberately not another prepare/grant.
            try(var owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
                var offered=owner.originalSource();offers.add(offered);assertEquals(reply.get("basis"),offered.basis.digest());
                for(String h:offered.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(t.replicaDirectory().resolve("sources/"+offered.basis.value().get("basisId")+"/"+h+".image")));
            }
        }
        f.snapshot("round-2-prepared");
        for(var t:f.request.targets())try(var owner=f.open(t,"select-2")){owner.selectCurrent(offers,List.of());}
        f.snapshot("round-2-selected");
        for(var t:f.request.targets())try(var owner=f.open(t,"install-2")) {
            var installed=owner.installCurrent(offers,List.of(),List.of(),images);assertArrayEquals(installed.bytes(),owner.installCurrent(offers,List.of(),List.of(),images).bytes());
        }
        f.snapshot("round-2-installed");f.maintain("round-2-settled",obsolete);
    }
    @Test void nativeOwnerContinuesRealPublicationAndFreshProcessGrantsForEveryInitialProfile()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-owned-recovery/run-"+UUID.randomUUID()));System.out.println("v53OwnedRecoveryEvidence="+evidence.toAbsolutePath());
        Path histories=Files.createDirectory(evidence.resolve("histories")),processes=Files.createDirectory(evidence.resolve("processes"));var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path raw=Files.createDirectory(histories.resolve(name)),children=Files.createDirectory(processes.resolve(name));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),raw,size,backup);f.ownedHistory=true;
            try {
                f.campaign(1);f.publish(1,false);f.publish(2,true);freshCampaign(f,children);f.publish(3,false);
                for(int node=0;node<size;node++) {
                    var reply=child(f,node,"inspect",children.resolve("inspect-"+(node+1)+".json"),null);
                    assertEquals(3L,object(reply.get("cut")).get("index"));assertEquals(2L,object(reply.get("sourceCut")).get("index"));
                }
                cases.add(Map.of("case",name,"status","PASS","voters",size,"publications",3,"sequence",f.result.applicationSequence()+1,"peakImages",f.peakImages,"peakMetadata",f.peakMetadata,"peakStaging",f.peakStaging));
            }finally {
                Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
                Files.write(histories.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-recovery-histories-v1","status",cases.size()==6?"PASS":"INCOMPLETE","cases",cases,
                        "publicBootstrap",true,"publicRuntime",false,"freshProcesses",true,"syntheticObservations",false),65536));
            }
            System.out.println("v53OwnedRecoveryCase="+name+" PASS");System.out.flush();
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-recovery-v1","status","PASS","profiles",6,"freshProcesses",54,
                "historicalObservationsSupplied",false,"publicRuntime",false),65536));
    }
    @Test void nativeFloorAndInactiveRecoveryRejectAlteredOriginalsBeforeRetiringAnything()throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("negative-store")),Files.createDirectory(temp.resolve("negative-raw")),3,false);f.ownedHistory=true;
        f.campaign(1);f.publish(1,false);f.publish(2,true);f.observations.clear();
        f.observer=(t,operation,event)->{if(operation.equals("round-2-settled-maintain") && event.equals("FLOOR_BEFORE_RETURN"))throw new java.io.IOException("original floor retained for recovery");};
        assertEquals("original floor retained for recovery",assertThrows(java.io.IOException.class,()->f.campaign(2)).getMessage());f.observer=(t,operation,event)->{};
        var t=f.request.targets().getFirst();Path path=t.replicaDirectory();
        var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
        String active=(String)selector.value().get("generation");Path inactive=path.resolve("generations/"+(active.equals("a")?"b":"a"));
        Path floor=path.resolve(MembershipFloorFiles.DIRECTORY);var retained=decode(Files.readAllBytes(floor.resolve(MembershipFloorFiles.FLOOR)),"records","FLOOR");
        Path copy=floor.resolve((String)object(list(retained.value().get("sources")).getFirst()).get("generation"));
        for(Path altered:List.of(inactive.resolve("source.gscp"),inactive.resolve("generation.gsr"),copy.resolve("source.gscp"),copy.resolve("selected.gsr"),floor.resolve(MembershipFloorFiles.FLOOR))) {
            byte[] original=Files.readAllBytes(altered);Files.write(altered,Arrays.copyOf(original,original.length-1));
            var before=V53ReplayFilesTest.files(path);
            assertThrows(Exception.class,()->{try(var owner=f.open(t,"negative-open")){owner.retireInactive();}},altered.toString());
            assertEquals(before,V53ReplayFilesTest.files(path),"refusal must preserve original bytes");assertEquals(0,f.resources.usage().leases());Files.write(altered,original);
        }
        try(var owner=f.open(t,"recovered-retirement")) {assertTrue(owner.retireInactive().isPresent());owner.releaseFloor();}
        assertFalse(Files.exists(inactive));assertEquals(0,f.resources.usage().leases());
        try(var owner=f.open(t,"reopened-original-source")){assertEquals(2L,owner.originalSource().capsule.context.cut.get("index"));}
    }
    @Test void completeCopyCapabilitiesCannotBeMintedFromCallerRecords() {
        for(Class<?> type:List.of(MembershipGrantJournal.HistoryRead.class,MembershipBasisSources.RetainedCopy.class,
                MembershipFloorFiles.RetainedCopy.class,MembershipGenerationFiles.RetainedCopy.class,MembershipRetirementFiles.RetainedCopy.class))
            assertTrue(Arrays.stream(type.getDeclaredConstructors()).allMatch(c->java.lang.reflect.Modifier.isPrivate(c.getModifiers())),type.getSimpleName());
        assertTrue(MembershipCapsule.StoredCopy.class.isSealed());
    }
    @Test void repeatedProcessDeathResumesOriginalRetirementAfterInactiveFilesDisappear()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-owned-recovery-crash/run-"+UUID.randomUUID()));System.out.println("v53OwnedRecoveryCrashEvidence="+evidence.toAbsolutePath());
        Path raw=Files.createDirectory(evidence.resolve("history")),states=Files.createDirectory(evidence.resolve("states"));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("crash-store")),raw,3,false);f.ownedHistory=true;
        f.campaign(1);f.publish(1,false);f.publish(2,true);var obsolete=new TreeMap<String,String>();
        for(var t:f.request.targets())try(var owner=f.open(t,"before-crash-source")){obsolete.put(t.identity().nodeId().value(),(String)owner.originalBasis().orElseThrow().value().get("basisId"));}
        f.observer=(t,operation,event)->{if(operation.equals("round-2-settled-maintain") && event.equals("FLOOR_BEFORE_RETURN"))throw new java.io.IOException("floor ready");};
        assertEquals("floor ready",assertThrows(java.io.IOException.class,()->f.campaign(2)).getMessage());f.observer=(t,operation,event)->{};
        var target=f.request.targets().getFirst();V53JournalApplicationTest.copy(target.replicaDirectory(),states.resolve("before"));
        var cuts=List.of("RETIREMENT_SOURCE_FORCED","RETIREMENT_PARENT_FORCED","RETIREMENT_FILE_DELETED","RETIREMENT_FILE_DELETED");
        var cases=new ArrayList<Map<String,Object>>();
        for(int n=0;n<cuts.size();n++) {
            String cut=cuts.get(n),mode=n%2==0?"halt":"kill";Path log=evidence.resolve("death-"+n+".log");
            Process process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),V53OwnedRecoveryWorker.class.getName(),
                    target.replicaDirectory().toString(),target.materialization().directory().toString(),"retire",mode,cut).redirectErrorStream(true).redirectOutput(log.toFile()).start();
            if(mode.equals("halt"))V53OwnedGenerationTest.finished(process,23,log);
            else try {
                long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(60);
                while(process.isAlive() && System.nanoTime()<deadline && !Files.readString(log).contains("CUT "+cut))Thread.sleep(10);
                assertTrue(process.isAlive(),()->{try{return Files.readString(log);}catch(Exception e){return e.toString();}});assertTrue(Files.readString(log).contains("CUT "+cut));
                process.destroyForcibly();assertTrue(process.waitFor(10,java.util.concurrent.TimeUnit.SECONDS));assertEquals(137,process.exitValue());
            }finally {if(process.isAlive()){process.destroyForcibly();process.waitFor(10,java.util.concurrent.TimeUnit.SECONDS);}}
            V53JournalApplicationTest.copy(target.replicaDirectory(),states.resolve("death-"+n));cases.add(Map.of("ordinal",n,"cut",cut,"mode",mode,"exit",mode.equals("halt")?23:137));
        }
        child(f,0,"retire",evidence.resolve("recovered.json"),null);V53JournalApplicationTest.copy(target.replicaDirectory(),states.resolve("recovered"));
        f.maintain("round-2-settled",obsolete);
        Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-recovery-crashes-v1","status","PASS","cases",cases,"publicRuntime",false,"powerLoss",false),65536));
    }
}
