package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53OwnedGenerationTest {
    @TempDir Path temp;
    static MembershipResources budget(){return new MembershipResources(512*MembershipResources.MIB);}
    V53BootstrapPublicationTest.Fixture fixture(Path raw,int size)throws Exception {
        return new V53BootstrapPublicationTest.Fixture(Files.createDirectories(temp.resolve(UUID.randomUUID().toString())),Files.createDirectories(raw),size,false);
    }
    static MembershipGrantJournal.RetainedHistory read(V53BootstrapPublicationTest.Fixture f,int node,MembershipResources resources)throws Exception {
        var t=f.request.targets().get(node);
        return MembershipGrantJournal.readRetainedHistory(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),resources,e->{});
    }
    static Process child(V53BootstrapPublicationTest.Fixture f,int node,String mode,Path log)throws Exception {
        var t=f.request.targets().get(node);
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53OwnedGenerationWorker.class.getName(),t.replicaDirectory().toString(),t.materialization().directory().toString(),mode)
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
    static void finished(Process process,int expected,Path log)throws Exception {
        try {assertTrue(process.waitFor(60,TimeUnit.SECONDS),"fresh reader deadline: "+log);assertEquals(expected,process.exitValue(),()->{try{return Files.readString(log);}catch(Exception e){return e.toString();}});}
        finally {if(process.isAlive()){process.destroyForcibly();assertTrue(process.waitFor(10,TimeUnit.SECONDS));}}
    }
    @Test void publishedCurrentAndSupplementalHistoryReopenWithoutFixtureObservationsInFreshProcesses()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-owned-generation/run-"+UUID.randomUUID()));System.out.println("v53OwnedGenerationEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=evidence.resolve("stable-"+size);var f=fixture(raw,size);f.campaign(1);f.publish(1,false);f.publish(2,true);
            f.snapshot("before-read");var receipts=new ArrayList<Map<String,Object>>();
            for(int node=0;node<size;node++) {
                Path log=raw.resolve("read-"+(node+1)+".log");finished(child(f,node,"read",log),0,log);
                var receipt=object(parse(Files.readAllBytes(log),65536));assertEquals("PASS",receipt.get("status"));assertEquals(0L,receipt.get("copiedObservations"));receipts.add(receipt);
            }
            f.snapshot("after-read");Files.write(raw.resolve("reads.json"),canonical(receipts,65536));
            cases.add(Map.of("size",size,"freshReaders",size));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-generation-v1","status","PASS","cases",cases,
                "scope","owned-selected-history-reopen","publicRuntime",false,"freshVotes",false),65536));
    }
    @Test void deathDuringResealingReleasesTheOwnerAndPreservesExactOriginalBytes()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-owned-generation-crash/run-"+UUID.randomUUID()));
        System.out.println("v53OwnedGenerationCrashEvidence="+evidence.toAbsolutePath());
        var f=fixture(evidence,3);f.campaign(1);f.publish(1,false);f.publish(2,true);f.snapshot("before-read");
        var t=f.request.targets().getFirst();var before=V53ReplayFilesTest.files(t.replicaDirectory());var cases=new ArrayList<Map<String,Object>>();
        for(String mode:List.of("halt","kill"))for(String cut:List.of("CURRENT_VALIDATED","CURRENT_FILES_FORCED","CURRENT_GENERATION_FORCED","CURRENT_SELECTOR_FORCED","CURRENT_DIRECTORY_FORCED")) {
            Path log=evidence.resolve(mode+"-"+cut+".log");Process process=child(f,0,(mode.equals("kill")?"hold":mode)+":"+cut,log);
            if(mode.equals("halt"))finished(process,23,log);
            else try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
                while(process.isAlive() && System.nanoTime()<deadline && !Files.readString(log).contains("CUT "+cut))Thread.sleep(10);
                assertTrue(process.isAlive(),()->{try{return Files.readString(log);}catch(Exception e){return e.toString();}});
                assertTrue(Files.readString(log).contains("CUT "+cut));process.destroyForcibly();assertTrue(process.waitFor(10,TimeUnit.SECONDS));
            }finally {if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
            assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));f.snapshot("death-"+mode+"-"+cut);
            Path recovered=evidence.resolve("recovered-"+mode+"-"+cut+".log");
            finished(child(f,0,"read",recovered),0,recovered);assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
            f.snapshot("recovered-"+mode+"-"+cut);cases.add(Map.of("mode",mode,"cut",cut,"exit",process.exitValue()));
        }
        Files.write(evidence.resolve("cases.json"),canonical(cases,65536));
    }
    @Test void owningJournalAndSelectorCannotBeSubstitutedByCallerLists()throws Exception {
        var f=fixture(temp.resolve("ownership-raw"),3);f.campaign(1);f.publish(1,false);var resources=budget();var t=f.request.targets().getFirst();
        try(var read=read(f,0,resources)) {
            assertThrows(Exception.class,()->read(f,0,budget()));assertEquals(1L,read.capsule().context.cut.get("index"));
            var grant=t.replicaDirectory().resolve("grants.gsr");byte[] original=Files.readAllBytes(grant);Files.write(grant,new byte[0]);
            assertThrows(Exception.class,read::capsule);Files.write(grant,original);
            var selector=t.replicaDirectory().resolve("selector.gsr");byte[] selected=Files.readAllBytes(selector);
            Files.move(selector,temp.resolve("held-original-selector"));Files.write(selector,selected);assertThrows(Exception.class,read::images);
        }
        assertEquals(0,resources.usage().leases());
        for(var constructor:MembershipGrantJournal.HistoryRead.class.getDeclaredConstructors())assertTrue(java.lang.reflect.Modifier.isPrivate(constructor.getModifiers()));
        for(var constructor:MembershipCurrentGeneration.RetainedCopy.class.getDeclaredConstructors())assertTrue(java.lang.reflect.Modifier.isPrivate(constructor.getModifiers()));
    }
    @Test void closedScopeCannotExposeRetainedDataAndFreshVotesStillRequireActualOwners()throws Exception {
        var f=fixture(temp.resolve("fresh-raw"),3);f.campaign(1);f.publish(1,false);var resources=budget();var read=read(f,0,resources);
        var capsule=read.capsule();var manifest=read.manifest();var path=f.request.targets().getFirst().replicaDirectory().resolve("generations").resolve((String)manifest.value().get("generation"));
        var coverage=object(parse(Files.readAllBytes(path.resolve(MembershipSelectionCoverage.FILE)),4096));var parent=object(object(coverage.get("parent")).get("cut"));
        var certificate=capsule.context.record((String)coverage.get("certificate"),"CERTIFICATE");assertDoesNotThrow(()->capsule.publicationCertificate(certificate,parent));
        assertThrows(IllegalArgumentException.class,()->capsule.context.certificateAt(certificate,Set.of(),parent));
        var root=decode(capsule.packet.objectBytes(capsule.context.recordRootDigest()),"records","ROOT");var images=read.images();
        assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(root,capsule.packet,images,Set.of()));
        read.close();assertThrows(IllegalArgumentException.class,read::capsule);assertThrows(IllegalArgumentException.class,read::images);
        assertThrows(IllegalArgumentException.class,read::manifest);assertThrows(IllegalArgumentException.class,read::ancestry);assertEquals(0,resources.usage().leases());
    }
    static void rewrite(Path replica,String name,byte[] bytes)throws Exception {
        Path selector=replica.resolve("selector.gsr");var s=object(V53ContextFixture.mutable(decode(Files.readAllBytes(selector),"records","SELECTOR").value()));
        Path directory=replica.resolve("generations").resolve((String)s.get("generation"));Path manifest=directory.resolve("generation.gsr");
        var m=object(V53ContextFixture.mutable(decode(Files.readAllBytes(manifest),"records","GENERATION").value()));Files.write(directory.resolve(name),bytes);
        for(Object row:list(m.get("files"))) {var file=object(row);if(name.equals(file.get("path"))){file.put("size",(long)bytes.length);file.put("sha256",hash(bytes));}}
        byte[] encoded=encode("records","GENERATION",m);Files.write(manifest,encoded);s.put("digest",hash(encoded));Files.write(selector,encode("records","SELECTOR",s));
    }
    @Test void completeHashInventoryCannotHideInvalidCoverageOrAncestry()throws Exception {
        var f=fixture(temp.resolve("negative-raw"),3);f.campaign(1);f.publish(1,false);f.publish(2,true);var t=f.request.targets().getFirst();Path replica=t.replicaDirectory();
        var selected=decode(Files.readAllBytes(replica.resolve("selector.gsr")),"records","SELECTOR");Path directory=replica.resolve("generations").resolve((String)selected.value().get("generation"));
        byte[] manifest=Files.readAllBytes(directory.resolve("generation.gsr")),coverage=Files.readAllBytes(directory.resolve(MembershipSelectionCoverage.FILE)),ancestry=Files.readAllBytes(directory.resolve("ancestry.gsr"));
        for(String fault:List.of("selection","first-certificate","parent","schema","ancestry-torn","ancestry-duplicate","ancestry-omitted")) {
            byte[] changed=coverage;String file=MembershipSelectionCoverage.FILE;
            if(fault.startsWith("ancestry")) {file="ancestry.gsr";changed=switch(fault){case "ancestry-torn"->Arrays.copyOf(ancestry,ancestry.length-1);case "ancestry-duplicate"->{var out=new java.io.ByteArrayOutputStream();out.writeBytes(ancestry);out.writeBytes(ancestry);yield out.toByteArray();}default->new byte[]{0};};}
            else {var c=object(V53ContextFixture.mutable(parse(coverage,4096)));switch(fault){case "selection"->c.put("selection","a".repeat(64));case "first-certificate"->object(c.get("first")).put("certificate",c.get("certificate"));case "parent"->object(object(c.get("parent")).get("cut")).put("entry","b".repeat(64));case "schema"->c.put("schema","untrusted");}changed=canonical(c,4096);}
            rewrite(replica,file,changed);var before=V53ReplayFilesTest.files(replica);var resources=budget();
            assertThrows(Exception.class,()->read(f,0,resources),fault);assertEquals(before,V53ReplayFilesTest.files(replica));assertEquals(0,resources.usage().leases());
            Files.write(directory.resolve(MembershipSelectionCoverage.FILE),coverage);Files.write(directory.resolve("ancestry.gsr"),ancestry);
            Files.write(directory.resolve("generation.gsr"),manifest);Files.write(replica.resolve("selector.gsr"),selected.bytes());
        }
        try(var good=read(f,0,budget())){assertEquals(2L,good.capsule().context.cut.get("index"));}
    }
    @Test void missingExtraLinkedAndForeignStoreRefuseBeforeReturningAuthority()throws Exception {
        var f=fixture(temp.resolve("files-raw"),3);f.campaign(1);f.publish(1,false);var t=f.request.targets().getFirst();Path replica=t.replicaDirectory();
        var selector=decode(Files.readAllBytes(replica.resolve("selector.gsr")),"records","SELECTOR");Path directory=replica.resolve("generations").resolve((String)selector.value().get("generation"));
        Path packet=directory.resolve("source.gscp");byte[] original=Files.readAllBytes(packet);
        for(String fault:List.of("missing","corrupt","extra","hardlink","symlink","journal")) {
            Path alias=temp.resolve("alias-"+fault),extra=directory.resolve("unknown");byte[] journal=Files.readAllBytes(replica.resolve("grants.gsr"));
            switch(fault){case "missing"->Files.delete(packet);case "corrupt"->Files.write(packet,new byte[]{1});case "extra"->Files.write(extra,new byte[]{1});case "hardlink"->Files.createLink(alias,packet);case "symlink"->{Files.move(packet,alias);Files.createSymbolicLink(packet,alias);}case "journal"->Files.write(replica.resolve("grants.gsr"),new byte[0]);}
            var resources=budget();var before=V53ReplayFilesTest.files(replica);assertThrows(Exception.class,()->read(f,0,resources),fault);assertEquals(before,V53ReplayFilesTest.files(replica));assertEquals(0,resources.usage().leases());
            if(fault.equals("symlink"))Files.delete(packet);if(Files.exists(alias))Files.delete(alias);if(Files.exists(extra))Files.delete(extra);
            Files.write(packet,original);Files.write(replica.resolve("grants.gsr"),journal);
        }
        var wrong=f.request.targets().get(1);assertThrows(Exception.class,()->MembershipGrantJournal.readRetainedHistory(replica,t.materialization().directory(),f.result.root(),wrong.identity(),budget(),e->{}));
        var small=new MembershipResources(1);assertThrows(Exception.class,()->read(f,0,small));assertEquals(0,small.usage().leases());
        try(var recovered=read(f,0,budget())){assertNotNull(recovered.manifest());}
    }
}
