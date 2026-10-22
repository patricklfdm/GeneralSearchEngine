package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual journal publication and covered cleanup. Historical bootstrap remains a private fixture. */
class V53JournalPublicationTest {
    @TempDir Path temp;
    static final class Fixture {
        final Path root;
        final int at;
        final V53JournalApplicationTest application=new V53JournalApplicationTest();
        final Set<Owned> observations=new HashSet<>(),checkpoints=new HashSet<>();
        final List<Decoded> acknowledgements=new ArrayList<>();
        final List<MembershipSelection.Bridge> bridges=new ArrayList<>();
        final Map<Integer,MembershipGrantJournal.Applied> applied=new TreeMap<>();
        Fixture(Path root,int at)throws Exception {this(root,at,true);}
        Fixture(Path root,int at,boolean applyLocal)throws Exception {
            this.root=root;this.at=at;Files.createDirectories(root);var app=new V53ApplicationReplayTest();app.temp=root;
            application.configure(root,app.initial(41),3,at);observations.addAll(application.f.f.f.fixture.owned);
            application.f.f.provision(root);application.f.f.install(root);
            var copies=new ArrayList<MembershipFloor.Copy>();
            for(int n:nodes())try(var store=open(n,resources(),e->{})){copies.add(store.floorCopyCurrent());}
            for(int n:nodes())try(var store=open(n,resources(),e->{})) {
                store.establishFloor(copies.stream().filter(c->List.of("node-1","node-2","node-"+n).contains(c.owner.nodeId().value())).toList());
                store.retireInactive();store.releaseFloor();
            }
            var accepts=new HashSet<Owned>();for(int n:nodes())try(var store=open(n,resources(),e->{})){accepts.add(store.acceptCurrent(application.f.f.entry(),application.f.f.payload()));}
            var proof=application.f.f.proof(accepts);var proofs=new HashSet<Owned>();
            for(int n:nodes())try(var store=open(n,resources(),e->{})){proofs.add(store.proveCurrent(proof,accepts));}
            application.cohort=new V53PendingCertificateFixture.Cohort(proof,application.f.certificate(proof,proofs),accepts,proofs);
            observations.addAll(application.cohort.owned());
            for(int n:nodes())try(var store=open(n,resources(),e->{})){store.certifyCurrent(application.cohort.certificate(),application.cohort.owned());}
            var parentAcks=new ArrayList<Decoded>();var parentOwned=new HashSet<Owned>();Decoded parentStatement=null;
            for(int n:nodes())if((at!=6 || n!=3) && (n!=1 || applyLocal))try(var store=open(n,resources(),e->{})) {
                var result=application.apply(store);applied.put(n,result);acknowledgements.add(result.endorsement().acknowledgement());checkpoints.add(result.endorsement().owned());
                if(result.endorsement().parent().isPresent()) {
                    var parent=result.endorsement().parent().orElseThrow();parentStatement=parent.statement();parentAcks.add(parent.acknowledgement());parentOwned.add(parent.owned());
                }
            }
            observations.addAll(checkpoints);
            if(parentStatement!=null){bridges.add(new MembershipSelection.Bridge(parentStatement,parentAcks,parentOwned));observations.addAll(parentOwned);}
        }
        List<Integer> nodes(){return application.f.f.nodes;}
        Path node(int n){return application.f.f.node(root,n);}
        MembershipResources resources(){return application.f.f.resources();}
        MembershipGrantJournal open(int n,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
            return MembershipGrantJournal.openApplying(node(n),application.f.f.f.root(),V53DeclarationsTest.node(n),resources,
                    (r,p,i)->MembershipCapsule.verify(r,p,i,observations),cut);
        }
        Decoded publish(MembershipGrantJournal store,int n)throws IOException {return store.publishCurrent(applied.get(n),acknowledgements,checkpoints,bridges);}
        void finish(MembershipBallotAllocator.Cut cut)throws Exception {
            var r=resources();try(var store=open(1,r,cut)) {
                if(store.currentCertificate().isPresent())publish(store,1);
                assertEquals((long)at+1,store.floorCopyCurrent().capsule.context.cut.get("index"));assertTrue(store.currentCertificate().isEmpty());
            }finally{assertEquals(0,r.usage().leases());}
        }
    }
    static List<String> cuts() {
        var points=new ArrayList<>(V53GenerationInstallTest.CUTS);points.remove("INSTALL_BEFORE_RETURN");
        points.addAll(List.of("PUBLICATION_VALIDATED","PUBLICATION_SELECTOR_FORCED","PUBLICATION_COVERAGE_VALIDATED","PUBLICATION_RETIRED","PUBLICATION_BEFORE_RETURN",
                "COVERED_END_VALIDATED","COVERED_END_BEFORE_DELETE","COVERED_END_FILE_DELETED","COVERED_END_BEFORE_DIRECTORY_DELETE","COVERED_END_DIRECTORY_DELETED"));
        for(String suffix:List.of("CANDIDATE_CREATED","PREFIX_WRITTEN","CANDIDATE_WRITTEN","CANDIDATE_FORCED","CANDIDATE_PARENT_FORCED","RENAMED","PARENT_FORCED"))points.add("COVERED_VOTE_"+suffix);
        return points;
    }
    static String recoveryPoint(Path node)throws IOException {
        if(MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)))==null)return "ACCEPT_ACTIVE_FORCED";
        return decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR").value().get("generation").equals("a")?"COVERED_VOTE_CANDIDATE_FORCED":"INSTALL_IMAGE_WRITTEN";
    }
    static final List<String> PROCESS_CUTS=List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_FORCED","INSTALL_SELECTOR_RENAMED","PUBLICATION_SELECTOR_FORCED",
            "COVERED_END_FILE_DELETED","COVERED_END_DIRECTORY_DELETED","COVERED_VOTE_PREFIX_WRITTEN","COVERED_VOTE_RENAMED");
    @Test void actualJournalProcessCrashesAndRepeatedRecoveryRetainExactPublicationAuthority()throws Exception {
        Path retained=Path.of("target/v53-journal-publication-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:PROCESS_CUTS) {
                Path root=retained.resolve(mode+"-"+point);var f=new Fixture(root,0);Path node=f.node(1);
                Files.write(root.resolve("base.image"),f.application.base);
                Files.write(root.resolve("observations.json"),canonical(Map.of("accepts",V53JournalApplicationTest.observations(f.application.cohort.accepts()),
                        "proofs",V53JournalApplicationTest.observations(f.application.cohort.proofs()),"checkpoints",V53JournalApplicationTest.observations(f.checkpoints)),16384));
                for(var ack:f.acknowledgements)Files.write(root.resolve("ack-"+ack.value().get("voter")+".gsr"),ack.bytes());
                V53JournalApplicationTest.copy(node,root.resolve("original"));child(root,"fault",point,mode);V53JournalApplicationTest.copy(node,root.resolve("crash"));
                String again=recoveryPoint(node);child(root,"recovery-fault",again,"halt");V53JournalApplicationTest.copy(node,root.resolve("recovery-crash"));
                child(root,"resume","none","none");V53JournalApplicationTest.copy(node,root.resolve("final"));preserved(node,V53ReplayFilesTest.files(root.resolve("original")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                rows.add(Map.of("mode",mode,"cut",point,"recoveryCut",again,"status","PASS","manifest",selector.value().get("digest")));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",(long)PROCESS_CUTS.size()*2,"freshJvms",(long)rows.size()*3,
                    "execution","private-journal-publication","phasedObservations","actual-local-owners","checkpointObservations","actual-forced-ends",
                    "bootstrap","private-fixture","selectorPublication",true,"powerLoss",false),65536));
            System.out.println("v53JournalPublicationEvidence="+retained.toAbsolutePath());
        }
        assertEquals(PROCESS_CUTS.size()*2,rows.size());
    }
    static void child(Path root,String label,String point,String mode)throws Exception {
        child(root,label,point,mode,V53JournalPublicationWorker.class);
    }
    static void child(Path root,String label,String point,String mode,Class<?> worker)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                worker.getName(),root.toAbsolutePath().toString(),point,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                long end=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).contains("AWAITING_KILL")){assertTrue(proc.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"kill marker deadline");Thread.sleep(20);}proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline");assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,proc.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
        }finally{if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
    static void preserved(Path node,Map<String,String> original)throws IOException {
        for(var row:original.entrySet())if(!row.getKey().equals("selector.gsr") && !row.getKey().equals(MembershipPendingAccept.FILE) && !row.getKey().startsWith("applied-end/"))
            assertEquals(row.getValue(),hash(Files.readAllBytes(node.resolve(row.getKey()))),row.getKey());
    }
    @Test void actualDataJointAndFinalPublishThenRetireOnlyCoveredStateAndAllowFreshCapture()throws Exception {
        for(int at:List.of(0,5,6)) {
            var f=new Fixture(temp.resolve("at-"+at),at);
            for(int n:f.applied.keySet()) {
                var before=V53ReplayFilesTest.files(f.node(n));var r=f.resources();Decoded manifest;
                try(var store=f.open(n,r,e->{})) {
                    manifest=f.publish(store,n);assertEquals((long)at+1,object(manifest.value().get("cut")).get("index"));
                    assertTrue(store.currentOwnedTail().isEmpty());assertTrue(store.currentCertificate().isEmpty());
                    assertEquals(3,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    assertArrayEquals(manifest.bytes(),f.publish(store,n).bytes());
                }
                assertEquals(0,r.usage().leases());preserved(f.node(n),before);
                assertFalse(Files.exists(f.node(n).resolve("applied-end")));assertFalse(Files.exists(f.node(n).resolve(MembershipReplayFiles.DIRECTORY)));
                assertArrayEquals(MembershipPendingAccept.empty(),Files.readAllBytes(f.node(n).resolve(MembershipPendingAccept.FILE)));
                try(var store=f.open(n,r,e->{})) {
                    assertArrayEquals(manifest.bytes(),f.publish(store,n).bytes());
                    var basis=store.prepareCurrent(f.application.f.f.f.fixture.source.ballot(21));assertEquals((long)at+1,object(basis.value().get("cut")).get("index"));
                    assertNull(basis.value().get("accepted"));assertThrows(IllegalArgumentException.class,()->f.publish(store,n));
                }
                assertEquals(0,r.usage().leases());
            }
            var copies=new ArrayList<MembershipFloor.Copy>();for(int n:List.of(1,2))try(var store=f.open(n,f.resources(),e->{})){copies.add(store.floorCopyCurrent());}
            try(var store=f.open(1,f.resources(),e->{})){store.establishFloor(copies);store.retireInactive();store.releaseFloor();}
            assertFalse(Files.exists(f.node(1).resolve("generations/b")),"cleanup permits later governing-floor retirement");
            try(var store=f.open(1,f.resources(),e->{})) {
                assertTrue(store.currentCertificate().isEmpty());assertEquals((long)at+1,object(store.prepareCurrent(f.application.f.f.f.fixture.source.ballot(22)).value().get("cut")).get("index"));
            }
        }
    }
    @Test void everyPublicationBoundaryRecoversAndRecoveryCanBeInterruptedAgain()throws Exception {
        for(String point:cuts()) {
            var f=new Fixture(temp.resolve(point),0);var before=V53ReplayFilesTest.files(f.node(1));
            assertThrows(IOException.class,()->f.finish(e->{if(e.equals(point))throw new IOException(point);}),point);
            String again=recoveryPoint(f.node(1));assertThrows(IOException.class,()->f.finish(e->{if(e.equals(again))throw new IOException(again);}),again);
            f.finish(e->{});preserved(f.node(1),before);
            assertFalse(Files.exists(f.node(1).resolve(MembershipPendingAccept.NEXT)));assertFalse(Files.exists(f.node(1).resolve("applied-end")));
        }
    }
    @Test void publicationRequiresActualLocalEndAndAuthenticatedOriginalObservations()throws Exception {
        var f=new Fixture(temp,0);Path node=f.node(1);var before=V53ReplayFilesTest.files(node);
        try(var store=f.open(1,f.resources(),e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(2),f.acknowledgements,f.checkpoints,List.of()));
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements,Set.of(),List.of()));
            f.observations.removeAll(f.checkpoints);assertThrows(IllegalArgumentException.class,()->f.publish(store,1));f.observations.addAll(f.checkpoints);
            f.observations.removeAll(f.application.cohort.owned());assertThrows(IllegalArgumentException.class,()->f.publish(store,1));
        }
        assertEquals(before,V53ReplayFilesTest.files(node));
    }
    @Test void changedCheckpointRepresentationCannotReplaceAnInterruptedOrCompletedPublication()throws Exception {
        for(String point:List.of("INSTALL_MANIFEST_FORCED","PUBLICATION_BEFORE_RETURN")) {
            var f=new Fixture(temp.resolve(point),0);assertThrows(IOException.class,()->f.finish(e->{if(e.equals(point))throw new IOException(point);}));
            try(var store=f.open(1,f.resources(),e->{})) {
                var before=V53ReplayFilesTest.files(f.node(1));
                assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements.subList(0,2),f.checkpoints,List.of()));
                assertEquals(before,V53ReplayFilesTest.files(f.node(1)));f.publish(store,1);
            }
        }
    }
    @Test void reopeningPublishedStateStillNeedsOriginalVoteAndCheckpointObservationsBeforeCleanup()throws Exception {
        var f=new Fixture(temp,0);assertThrows(IOException.class,()->f.finish(e->{if(e.equals("PUBLICATION_SELECTOR_FORCED"))throw new IOException("stop");}));
        var before=V53ReplayFilesTest.files(f.node(1));
        for(var missing:List.of(f.checkpoints,f.application.cohort.owned())) {
            f.observations.removeAll(missing);var r=f.resources();assertThrows(IllegalArgumentException.class,()->f.open(1,r,e->{}));
            assertEquals(0,r.usage().leases());assertEquals(before,V53ReplayFilesTest.files(f.node(1)));f.observations.addAll(missing);
        }
        f.finish(e->{});
    }
    @Test void foreignCandidateAndDamagedCoveredStageRejectBeforeAnyDeletion()throws Exception {
        for(String damage:List.of("candidate","image","plan","missing-plan","extra","link","old-selector")) {
            var f=new Fixture(temp.resolve(damage),0);assertThrows(IOException.class,()->f.finish(e->{if(e.equals("PUBLICATION_SELECTOR_FORCED"))throw new IOException("stop");}));
            Path node=f.node(1),end=node.resolve("applied-end");
            switch(damage) {
                case "candidate" -> Files.write(node.resolve(MembershipPendingAccept.NEXT),Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
                case "image","plan" -> {Path file=end.resolve(damage.equals("image")?"application.image":"plan.json");byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);}
                case "missing-plan" -> Files.delete(end.resolve("plan.json"));
                case "extra" -> Files.write(end.resolve("extra"),new byte[]{1});
                case "link" -> Files.createLink(f.root.resolve("linked-image"),end.resolve("application.image"));
                case "old-selector" -> {var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));var value=new TreeMap<>(vote.selector().value());value.put("digest",V53ContextFixture.H);
                    var wrong=new MembershipPendingAccept.Vote(decode(encode("records","SELECTOR",value),"records","SELECTOR"),vote.promise(),vote.selected(),vote.entry(),vote.accept(),vote.payload(),vote.proof(),vote.certificate());Files.write(node.resolve(MembershipPendingAccept.FILE),wrong.bytes());}
            }
            var before=V53ReplayFilesTest.files(node);var r=f.resources();assertThrows(Exception.class,()->f.open(1,r,e->{}),damage);assertEquals(0,r.usage().leases());assertEquals(before,V53ReplayFilesTest.files(node));
        }
    }
    @Test void higherObservedBallotAtEachPublicationBoundaryPreventsSuccessButCoveredCleanupRemainsRecoverable()throws Exception {
        for(String point:List.of("PUBLICATION_VALIDATED","INSTALL_IMAGE_FORCED","INSTALL_SELECTOR_RENAMED","PUBLICATION_SELECTOR_FORCED","COVERED_END_FILE_DELETED","COVERED_VOTE_RENAMED","PUBLICATION_BEFORE_RETURN")) {
            var f=new Fixture(temp.resolve(point),0);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(1,f.resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.application.f.f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->f.publish(store,1),point);
            }
            // The in-memory observation is not a new durable grant; original retry remains safe after reopen.
            f.finish(e->{});
        }
    }
}
