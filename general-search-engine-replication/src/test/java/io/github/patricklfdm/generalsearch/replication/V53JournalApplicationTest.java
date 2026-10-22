package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual local phased and checkpoint force observations. Initial provisioning is still a private fixture. */
class V53JournalApplicationTest {
    @TempDir Path temp;
    V53ApplicationReplayTest app;
    V53PendingCertificateFixture f;
    V53PendingCertificateFixture.Cohort cohort;
    byte[] base;
    void configure(Path root,byte[] original,int size,int through)throws Exception {
        app=new V53ApplicationReplayTest();app.temp=root;base=original;
        byte[] payload;try(var encoder=app.encoder()){payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(3,"new"))));}
        var capsule=new V53CapsuleFixture(new V53ContextFixture(size,"REPLACE",base,V53ApplicationImageTest.HISTORY,41),"REPLACE",through);
        String kind="DATA";
        if(through==5 || through==6){var entry=capsule.entry(through);kind=(String)entry.get("kind");payload=capsule.source.inventory.get(entry.get("payload"));}
        f=new V53PendingCertificateFixture(new V53PendingProofFixture(new V53CurrentGenerationFixture(size,capsule),payload,kind));
    }
    void setup(Path root)throws Exception {setup(root,3,0);}
    void setup(Path root,int size,int through)throws Exception {
        Files.createDirectories(root);var application=new V53ApplicationReplayTest();application.temp=root;configure(root,application.initial(41),size,through);
        // Provisioning and selected installation are real files, but not the public bootstrap contract.
        f.f.provision(root);f.f.install(root);
        var accepts=new HashSet<Owned>();for(int node:f.f.nodes)try(var store=open(root,node,f.f.resources(),e->{})){accepts.add(store.acceptCurrent(f.f.entry(),f.f.payload()));}
        var proof=f.f.proof(accepts);var proofs=new HashSet<Owned>();for(int node:f.f.nodes)try(var store=open(root,node,f.f.resources(),e->{})){proofs.add(store.proveCurrent(proof,accepts));}
        cohort=new V53PendingCertificateFixture.Cohort(proof,f.certificate(proof,proofs),accepts,proofs);
        for(int node:f.f.nodes)try(var store=open(root,node,f.f.resources(),e->{})){store.certifyCurrent(cohort.certificate(),cohort.owned());}
    }
    MembershipGrantJournal open(Path root,int node,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openApplying(f.f.node(root,node),f.f.f.root(),V53DeclarationsTest.node(node),resources,f.f.f::verify,cut);
    }
    MembershipGrantJournal.Applied apply(MembershipGrantJournal store)throws IOException {return store.applyCurrent(app.configuration(),app.storage(),cohort.owned());}
    @Test void threeActualOwnersReplayTheOriginalCertificateAndForceTheSameEndBeforeAck()throws Exception {
        setup(temp);var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();MembershipCheckpointPlan plan=null;
        var preserved=new TreeMap<Integer,Map<String,String>>();for(int n:f.f.nodes)preserved.put(n,V53ReplayFilesTest.files(f.f.node(temp,n)));
        byte[] expected=app.replay(base,41,0,List.of(new MembershipApplicationReplay.Step(1,"DATA",f.f.payload())),"expected").image();
        for(int node:f.f.nodes) {
            var r=f.f.resources();try(var store=open(temp,node,r,e->{})) {
                var result=apply(store);plan=result.plan();assertArrayEquals(expected,plan.application.image());assertEquals(42,plan.application.sequence());
                acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());
                assertEquals(0L,store.floorCopyCurrent().capsule.context.cut.get("index"),"local ACK must not move selectable generation");
                assertEquals(cohort.certificate().digest(),store.currentCertificate().orElseThrow().digest());
            }
            assertEquals(0,r.usage().leases());try(var store=open(temp,node,r,e->{})){assertEquals(acks.getLast().digest(),apply(store).endorsement().acknowledgement().digest());}
            for(var row:preserved.get(node).entrySet())assertEquals(row.getValue(),hash(Files.readAllBytes(f.f.node(temp,node).resolve(row.getKey()))),row.getKey());
            assertFalse(Files.exists(f.f.node(temp,node).resolve(MembershipReplayFiles.DIRECTORY)));
        }
        assertNotNull(plan);var capsule=plan.complete(acks,owned);assertEquals(1L,capsule.context.cut.get("index"));assertEquals(42L,capsule.context.catalog.get("applicationSequence"));
        assertThrows(IllegalArgumentException.class,()->open(temp,1,new MembershipResources(64*MembershipResources.MIB),e->{}));
        assertThrows(RuntimeException.class,()->f.f.open(temp,1,f.f.resources(),e->{}),"old storage mode cannot ignore applied-end files");
        assertFalse(Files.exists(app.storage().directory()));
    }
    @Test void everyApplicationAndEndCutRecoversWithoutChangingOriginalVoteOrSelector()throws Exception {
        var points=new ArrayList<>(V53ReplayFilesTest.CUTS);points.addAll(V53AppliedEndFilesTest.cuts());points.add("APPLICATION_AUTHORITY_VALIDATED");
        for(String point:points) {
            Path root=temp.resolve(point);setup(root);Path node=f.f.node(root,1);byte[] selector=Files.readAllBytes(node.resolve("selector.gsr")),vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));var r=f.f.resources();
            try(var store=open(root,1,r,e->{if(e.equals(point))throw new IOException(point);})){assertThrows(IOException.class,()->apply(store));}
            assertEquals(0,r.usage().leases());
            try(var store=open(root,1,r,e->{if(e.equals("APPLY_IMAGE_PREFIX_WRITTEN"))throw new IOException("again");})){assertThrows(IOException.class,()->apply(store));}
            try(var store=open(root,1,r,e->{})){assertEquals(42,apply(store).plan().application.sequence());}
            assertArrayEquals(selector,Files.readAllBytes(node.resolve("selector.gsr")));assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));assertEquals(0,r.usage().leases());
        }
    }
    @Test void missingPhasedObservationsAndUncertifiedLocalStateCannotCreateScratchOrAck()throws Exception {
        setup(temp);Path node=f.f.node(temp,1);var before=V53ReplayFilesTest.files(node);
        try(var store=open(temp,1,f.f.resources(),e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.applyCurrent(app.configuration(),app.storage(),Set.of()));
            assertThrows(IllegalArgumentException.class,()->store.applyCurrent(app.configuration(),app.storage(),cohort.accepts()));
        }
        assertEquals(before,V53ReplayFilesTest.files(node));
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        Files.write(node.resolve(MembershipPendingAccept.FILE),vote.withCertificate(null).bytes());
        try(var store=open(temp,1,f.f.resources(),e->{})){assertThrows(IllegalArgumentException.class,()->apply(store));}
        assertFalse(Files.exists(node.resolve(MembershipReplayFiles.DIRECTORY)));assertFalse(Files.exists(node.resolve(MembershipAppliedEndFiles.DIRECTORY)));
    }
    @Test void higherObservedBallotsAndPhysicalSelectorReplacementFenceEveryAckPath()throws Exception {
        for(String point:List.of("APPLICATION_AUTHORITY_VALIDATED","REPLAY_CLAIM_FORCED","REPLAY_APPLICATION_FINISHED","APPLY_END_FORCED","APPLY_ACK_DIRECTORY_FORCED","APPLY_BEFORE_RETURN")) {
            Path root=temp.resolve(point);setup(root);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=open(root,1,f.f.resources(),event->{if(event.equals(point))ref[0].observeCurrent(f.f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->apply(store));
            }
        }
        Path root=temp.resolve("inode");setup(root);Path node=f.f.node(root,1);
        try(var store=open(root,1,f.f.resources(),e->{if(e.equals("APPLY_END_FORCED")) {
            Path selector=node.resolve("selector.gsr"),copy=node.resolveSibling("copy");Files.copy(selector,copy);Files.move(copy,selector,StandardCopyOption.REPLACE_EXISTING);
        }})){assertThrows(IllegalArgumentException.class,()->apply(store));}
        assertFalse(Files.exists(node.resolve("applied-end/ack.gsr")));
    }
    @Test void completionSpaceIsReservedBeforeNewAcceptAndIncludedInJournalCeiling()throws Exception {
        setup(temp);Path node=f.f.node(temp,1);Files.write(node.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());
        var resources=f.f.resources();var held=new ArrayList<MembershipResources.Lease>();
        try(var store=open(temp,1,resources,e->{})) {
            for(int i=0;i<2;i++)held.add(resources.reserve(MembershipResources.Unit.APPLICATION,"unrelated-"+i,1));
            byte[] before=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));
            assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));assertArrayEquals(before,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        }finally{held.forEach(MembershipResources.Lease::close);}
        assertEquals(0,resources.usage().leases());
        int below=MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+(int)Files.size(node.resolve("grants.gsr"));
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openApplying(node,f.f.f.root(),V53DeclarationsTest.node(1),resources,f.f.f::verify,below,e->{}));
        assertEquals(0,resources.usage().leases());
    }
    @Test void realJointAndFinalAcknowledgementsRespectTheSuccessorVotersAndBothMajorities()throws Exception {
        for(int through:List.of(5,6)) {
            Path root=temp.resolve("cut-"+through);setup(root,3,through);var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();MembershipCheckpointPlan plan=null;
            for(int node:f.f.nodes)try(var store=open(root,node,f.f.resources(),e->{})) {
                if(through==6 && node==3){assertThrows(IllegalArgumentException.class,()->apply(store));assertFalse(Files.exists(f.f.node(root,node).resolve("applied-end/ack.gsr")));continue;}
                var result=apply(store);plan=result.plan();assertArrayEquals(base,plan.application.image());assertEquals(41,plan.application.sequence());
                acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());
            }
            assertNotNull(plan);
            if(through==5) {
                // Old majority {1,3} alone cannot attest the successor joint cut.
                var p=plan;var oldOnly=acks.stream().filter(v->!v.value().get("voter").equals("node-2")).toList();
                assertThrows(IllegalArgumentException.class,()->p.complete(oldOnly,owned));
            }
            var result=plan.complete(acks,owned);assertEquals((long)through+1,result.context.cut.get("index"));assertEquals(through==5,result.context.view.get("operation")!=null);
        }
    }
    @Test void laterGrantCaptureCannotSpendTheSpaceNeededToReopenAnAppliedCertificate()throws Exception {
        setup(temp);var resources=f.f.resources();int completed=0;boolean refused=false;
        try(var store=open(temp,1,resources,e->{})) {
            apply(store);
            for(int ballot=21;ballot<=25;ballot++) {
                try{store.prepareCurrent(f.f.f.fixture.source.ballot(ballot));completed++;}
                catch(MembershipOperationException capacity){assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,capacity.reason());refused=true;break;}
            }
        }
        assertTrue(completed>0 && refused,"capture remains bounded before loss of reopen headroom");assertEquals(0,resources.usage().leases());
        try(var store=open(temp,1,resources,e->{})) {
            assertEquals(cohort.certificate().digest(),store.currentCertificate().orElseThrow().digest());
            assertThrows(IllegalArgumentException.class,()->apply(store),"new grant fences the old ACK path");
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void actualOwnerProcessCrashesKeepOriginalAuthorityAndRecoverTheSameAcknowledgement()throws Exception {
        var points=List.of("APPLICATION_AUTHORITY_VALIDATED","REPLAY_CLAIM_PREFIX_WRITTEN","REPLAY_APPLICATION_FINISHED","APPLY_PLAN_PREFIX_WRITTEN",
                "APPLY_IMAGE_PREFIX_WRITTEN","APPLY_END_FORCED","APPLY_ACK_PREFIX_WRITTEN","APPLY_ACK_DIRECTORY_FORCED","APPLY_BEFORE_RETURN",
                "v41-backup-after-marker-force-v1","v41-backup-after-final-rename-v1");
        Path retained=Path.of("target/v53-journal-application-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                Path root=retained.resolve(mode+"-"+point);setup(root);Files.write(root.resolve("base.image"),base);
                Files.write(root.resolve("observations.json"),canonical(Map.of("accepts",observations(cohort.accepts()),"proofs",observations(cohort.proofs())),16384));
                Path node=f.f.node(root,1);copy(node,root.resolve("original"));
                child(root,"fault",point,mode);copy(node,root.resolve("crash"));
                child(root,"recovery-fault","APPLY_IMAGE_PREFIX_WRITTEN","halt");copy(node,root.resolve("recovery-crash"));
                child(root,"resume","none","none");copy(node,root.resolve("final"));
                for(var row:V53ReplayFilesTest.files(root.resolve("original")).entrySet())assertEquals(row.getValue(),hash(Files.readAllBytes(node.resolve(row.getKey()))));
                var ack=decode(Files.readAllBytes(node.resolve("applied-end/ack.gsr")),"records","CHECKPOINT_ACK");
                assertEquals(1L,object(ack.value().get("cut")).get("index"));assertFalse(Files.exists(node.resolve(MembershipReplayFiles.DIRECTORY)));
                rows.add(Map.of("mode",mode,"cut",point,"status","PASS","ack",ack.digest()));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",(long)points.size()*2,"freshJvms",(long)rows.size()*3,
                    "phasedObservations","actual-local-owners","bootstrap","private-fixture","selectorPublication",false,"powerLoss",false),65536));
            System.out.println("v53JournalApplicationEvidence="+retained.toAbsolutePath());
        }
        assertEquals(points.size()*2,rows.size());
    }
    static List<Map<String,Object>> observations(Set<Owned> rows) {
        return rows.stream().sorted(Comparator.comparing(Owned::voter)).map(v->Map.<String,Object>of("voter",v.voter(),"storage",v.storage().toString(),"record",v.record(),"parent",v.parent())).toList();
    }
    static Set<Owned> readObservations(Object value) {
        var result=new HashSet<Owned>();for(Object row:list(value)){var v=object(row);assertTrue(result.add(new Owned((String)v.get("voter"),UUID.fromString((String)v.get("storage")),(String)v.get("record"),(String)v.get("parent"))));}return result;
    }
    static void copy(Path from,Path to)throws IOException {
        Files.createDirectory(to);try(var paths=Files.walk(from)){for(Path p:paths.toList()){Path target=to.resolve(from.relativize(p));if(Files.isDirectory(p)){if(!Files.exists(target))Files.createDirectory(target);}else Files.copy(p,target);}}
    }
    static void child(Path root,String label,String point,String mode)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53JournalApplicationWorker.class.getName(),root.toAbsolutePath().toString(),point,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=point.startsWith("v41-")?"GSE_BARRIER_READY=":"AWAITING_KILL";long end=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).contains(marker)){assertTrue(proc.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"kill marker deadline");Thread.sleep(20);}proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline");
            assertEquals(mode.equals("halt")?(point.startsWith("v41-")?86:73):mode.equals("kill")?137:0,proc.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
        }finally{if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
}
