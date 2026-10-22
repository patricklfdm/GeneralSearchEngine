package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Generation construction/reader component tests. Journal publication/covered-tail retirement remains separate. */
class V53PublishedGenerationTest {
    @TempDir Path temp;
    static final class Fixture {
        final V53SelectionFixture f;
        final MembershipCheckpointPlan checkpoint;
        final V53CheckpointPlanTest.Endorsements ends;
        final Decoded promise,basis,selected;
        final MembershipSelection.Decision decision;
        final List<MembershipSelection.Bridge> bridges;
        final Set<Owned> observations=new HashSet<>();
        Fixture(int size,String change,int at) {
            f=new V53SelectionFixture(size,change,at);
            var sources=new ArrayList<MembershipSelection.Source>();
            for(String n:f.capsule.verify().context.voters())sources.add(f.source(n,1,null,0));
            sources.sort(Comparator.comparing(s->s.owner.nodeId().value()));basis=sources.getFirst().basis;
            decision=new MembershipSelection.Campaign(sources.getFirst()).select(sources,List.of());selected=decision.selected();
            var p=new TreeMap<>(basis.value());p.keySet().retainAll(Set.of("root","view","ballot","basisId"));
            promise=decode(encode("records","PROMISE",p),"records","PROMISE");
            checkpoint=V53CheckpointPlanTest.plan(f.capsule.verify(),f.capsule.source,at);ends=V53CheckpointPlanTest.endorsements(checkpoint);
            var ordinary=checkpoint.complete(ends.acks(),ends.owned());
            bridges=ordinary.containsCut(checkpoint.originalParent().cut())?List.of():List.of(f.bridge(at,at+1));
            observations.addAll(f.capsule.owned);observations.addAll(V53CheckpointPlanTest.votes(f.capsule.source,f.capsule.source.steps.get(at)));
            observations.addAll(ends.owned());bridges.forEach(b->observations.addAll(b.owned));
        }
        MembershipRoot root(){return V53BallotAllocatorWorker.root(f.capsule.source);}
        MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images){return MembershipCapsule.verify(root,packet,images,observations);}
        MembershipGenerationPlan plan(){return plan(promise,basis,selected,bridges);}
        MembershipGenerationPlan plan(Decoded p,Decoded b,Decoded s,List<MembershipSelection.Bridge> ancestry) {
            return MembershipGenerationPlan.published(root(),V53DeclarationsTest.node(1),"b",p,b,s,checkpoint,ends.acks(),ends.owned(),ancestry);
        }
        MembershipCapsule capsule(){return checkpoint.publication(ends.acks(),ends.owned(),bridges);}
        void provision(Path path)throws Exception {
            V53BallotAllocatorWorker.provision(path,f.capsule.source);
            Files.write(path.resolve("grants.gsr"),java.nio.ByteBuffer.allocate(promise.bytes().length+basis.bytes().length+selected.bytes().length)
                    .put(promise.bytes()).put(basis.bytes()).put(selected.bytes()).array());
            Path source=path.resolve("sources").resolve((String)basis.value().get("basisId"));Files.createDirectories(source);
            Files.write(source.resolve("source.gscp"),f.capsule.packet().bytes());
            for(var row:f.capsule.source.images.entrySet())Files.write(source.resolve(row.getKey()+".image"),row.getValue());
            var initial=MembershipGenerationPlan.selected(root(),V53DeclarationsTest.node(1),"a",promise,basis,decision,List.of(),f.capsule.source.images);
            Path generation=path.resolve("generations/a");Files.createDirectories(generation);
            for(var row:initial.files.entrySet())Files.write(generation.resolve(row.getKey()),row.getValue());
            Files.write(path.resolve("selector.gsr"),initial.selector.bytes());
        }
        void install(Path path,MembershipBallotAllocator.Cut cut)throws Exception {
            var resources=new MembershipResources(512*MembershipResources.MIB);var plan=plan();
            try(var owner=MembershipBallotAllocator.openWithGenerationInstall(path,root(),V53DeclarationsTest.node(1),e->{});
                var current=new MembershipCurrentGeneration(path,root(),V53DeclarationsTest.node(1),resources,List.of(promise),List.of(basis),List.of(selected),this::verify,e->{},true);
                var inactive=new MembershipGenerationFiles(path,current.generation,resources)) {
                plan.verify(f.capsule.source.root,V53DeclarationsTest.node(1),this::verify,List.of(checkpoint.originalParent()));
                if(current.generation.equals("a"))inactive.install(plan,current.selector.bytes(),owner::checkOwner,current::check,cut);
                else {assertArrayEquals(current.manifest.bytes(),plan.manifest.bytes());assertFalse(inactive.pending());}
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void allSixtyThreeTransitionsKeepOriginalSelectionAndExactPhasedProof() {
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}})
            for(int at=0;at<9;at++) {
                var f=new Fixture((int)profile[0],(String)profile[1],at);var plan=f.plan();
                plan.verify(f.f.capsule.source.root,V53DeclarationsTest.node(1),f::verify,List.of(f.checkpoint.originalParent()));
                assertArrayEquals(f.selected.bytes(),plan.files.get("selected.gsr"));assertArrayEquals(f.promise.bytes(),plan.files.get("promise.gsr"));
                assertEquals((long)at,object(f.selected.value().get("cut")).get("index"));assertEquals((long)at+1,object(plan.manifest.value().get("cut")).get("index"));
                assertNull(plan.manifest.value().get("ownedTail"));assertEquals(1,plan.files.keySet().stream().filter(n->n.endsWith(".image")).count());
                assertTrue(plan.metadata<=MembershipResources.Unit.GENERATION.bytes);
                var packet=MembershipSourcePacket.decode(plan.files.get("source.gscp"));
                for(String kind:List.of("entry","accept","proof","certificate")) {
                    String hash=(String)f.f.capsule.source.steps.get(at).get(kind);
                    assertArrayEquals(f.f.capsule.source.inventory.get(hash),packet.objectBytes(hash));
                }
            }
    }
    @Test void compactedParentRequiresRealBridgeObservationsAndCannotBeInventedFromTheNewRange() {
        var f=new Fixture(3,"ADD",2);
        assertThrows(IllegalArgumentException.class,()->f.plan(f.promise,f.basis,f.selected,List.of()));
        var b=f.bridges.getFirst();var unowned=new MembershipSelection.Bridge(b.statement,b.acknowledgements,Set.of());
        assertThrows(IllegalArgumentException.class,()->f.plan(f.promise,f.basis,f.selected,List.of(unowned)));
        assertThrows(IllegalArgumentException.class,()->f.plan(f.promise,f.basis,f.selected,List.of(b,b)));
        var plan=f.plan();f.observations.removeAll(b.owned);
        assertThrows(IllegalArgumentException.class,()->plan.verify(f.f.capsule.source.root,V53DeclarationsTest.node(1),f::verify,List.of(f.checkpoint.originalParent())));
    }
    @Test void coverageRejectsForeignParentsRewrittenSelectionsAndMissingOriginalPhases() {
        var f=new Fixture(3,"ADD",0);var plan=f.plan();var capsule=f.capsule();byte[] bytes=plan.files.get(MembershipSelectionCoverage.FILE);
        for(String field:List.of("selection","certificate","schema","catalog","application","cut","extra")) {
            var v=new TreeMap<>(object(parse(bytes,4096)));
            if(Set.of("catalog","application","cut").contains(field)) {
                var parent=new TreeMap<>(object(v.get("parent")));
                parent.put(field,field.equals("cut")?capsule.context.cut:V53ContextFixture.H);v.put("parent",parent);
            }else v.put(field,field.equals("schema")?"other":V53ContextFixture.H);
            assertThrows(IllegalArgumentException.class,()->MembershipSelectionCoverage.verify(canonical(v,4096),capsule,f.promise,f.selected,new byte[0]),field);
        }
        assertThrows(IllegalArgumentException.class,()->MembershipSelectionCoverage.verify(Arrays.copyOf(bytes,bytes.length-1),capsule,f.promise,f.selected,new byte[0]));
        byte[] spaced=Arrays.copyOf(bytes,bytes.length+1);spaced[spaced.length-1]=' ';
        assertThrows(ReplicationException.class,()->MembershipSelectionCoverage.verify(spaced,capsule,f.promise,f.selected,new byte[0]));
        var phases=V53CheckpointPlanTest.votes(f.f.capsule.source,f.f.capsule.source.steps.getFirst());f.observations.removeAll(phases);
        // A complete RANGE with true checkpoint observations alone is insufficient for the original selected vote.
        assertThrows(IllegalArgumentException.class,()->plan.verify(f.f.capsule.source.root,V53DeclarationsTest.node(1),f::verify,List.of()));
    }
    @Test void carriedChoiceAndAcceptanceBallotCannotBeChangedOrInferredFromAnAdvancedCut() {
        var f=new Fixture(3,"ADD",0);var s=new TreeMap<>(f.selected.value());s.put("nextEntry",f.checkpoint.originalCertificate().value().get("entry"));
        var carried=decode(encode("records","SELECTED",s),"records","SELECTED");assertNotNull(f.plan(f.promise,f.basis,carried,List.of()));
        s.put("nextEntry",V53ContextFixture.H);var wrong=decode(encode("records","SELECTED",s),"records","SELECTED");
        assertThrows(IllegalArgumentException.class,()->f.plan(f.promise,f.basis,wrong,List.of()));
        var p=new TreeMap<>(f.promise.value());p.put("ballot",f.f.capsule.source.ballot(2));
        var b=new TreeMap<>(f.basis.value());b.put("ballot",p.get("ballot"));var basis=decode(encode("records","BASIS",b),"records","BASIS");
        s=new TreeMap<>(carried.value());s.put("ballot",p.get("ballot"));var sources=new ArrayList<Map<String,Object>>();
        for(Object row:list(s.get("sources"))){var source=new TreeMap<>(object(row));if(source.get("voter").equals("node-1"))source.put("basisDigest",basis.digest());sources.add(source);}s.put("sources",sources);
        var selection=decode(encode("records","SELECTED",s),"records","SELECTED");var promise=decode(encode("records","PROMISE",p),"records","PROMISE");
        assertThrows(IllegalArgumentException.class,()->f.plan(promise,basis,selection,List.of()));
        var later=new V53CapsuleFixture(3,"ADD",2).verify();
        assertThrows(IllegalArgumentException.class,()->MembershipSelectionCoverage.verify(f.plan().files.get(MembershipSelectionCoverage.FILE),later,f.promise,f.selected,new byte[0]));
    }
    @Test void copiedJointGenerationChecksOriginalElectionUnderItsOriginalVoters() {
        var f=new Fixture(3,"REPLACE",5);var value=new TreeMap<>(f.selected.value());
        value.put("sources",list(value.get("sources")).stream().map(MembershipFormat::object).filter(s->!s.get("voter").equals("node-2")).toList());
        var selected=decode(encode("records","SELECTED",value),"records","SELECTED");var plan=f.plan(f.promise,f.basis,selected,List.of());
        var packet=MembershipSourcePacket.decode(plan.files.get("source.gscp"));
        var capsule=f.verify(f.f.capsule.source.root,packet,Map.of(hash(f.checkpoint.application.image()),f.checkpoint.application.image()));
        assertThrows(IllegalArgumentException.class,()->capsule.context.quorum(List.of("node-1","node-3")),"the original election need not be a successor joint quorum");
        var local=V53DeclarationsTest.node(1);var copy=new Owned("node-1",local.storageId(),plan.manifest.digest(),cutDigest(capsule.context.cut));
        assertNotNull(MembershipFloor.Copy.verify(plan.manifest,capsule,local,Set.of(copy),plan.files));
        var invalid=new TreeMap<>(value);invalid.put("sources",list(value.get("sources")).subList(0,1));
        assertThrows(RuntimeException.class,()->f.plan(f.promise,f.basis,decode(encode("records","SELECTED",invalid),"records","SELECTED"),List.of()));
    }
    @Test void actualOwnersSupplyDataJointAndFinalEndsAndReaderReopensTheCompleteMaterialization()throws Exception {
        for(int at:List.of(0,5,6)) {
            Path root=temp.resolve("actual-"+at);Files.createDirectories(root);var app=new V53ApplicationReplayTest();app.temp=root;
            var f=new V53JournalApplicationTest();f.configure(root,app.initial(41),3,at);f.f.f.provision(root);f.f.f.install(root);
            var copies=new ArrayList<MembershipFloor.Copy>();for(int n:f.f.f.nodes)try(var store=f.open(root,n,f.f.f.resources(),e->{})){copies.add(store.floorCopyCurrent());}
            // Free the inactive slot only through the actual complete-copy quorum and governing floor.
            // This maintenance precedes ACCEPT admission: seven image slots cannot also hold
            // an old inactive image, all floor copies and three replay/end completion slots.
            for(int n:f.f.f.nodes)try(var store=f.open(root,n,f.f.f.resources(),e->{})) {
                // Nodes 1 and 2 form both governing majorities in this 3->3 replacement;
                // each floor additionally includes its own owner when needed.
                var offered=copies.stream().filter(c->List.of("node-1","node-2","node-"+n).contains(c.owner.nodeId().value())).toList();
                store.establishFloor(offered);store.retireInactive();store.releaseFloor();
            }
            var accepts=new HashSet<Owned>();for(int n:f.f.f.nodes)try(var store=f.open(root,n,f.f.f.resources(),e->{})){accepts.add(store.acceptCurrent(f.f.f.entry(),f.f.f.payload()));}
            var proof=f.f.f.proof(accepts);var proofs=new HashSet<Owned>();for(int n:f.f.f.nodes)try(var store=f.open(root,n,f.f.f.resources(),e->{})){proofs.add(store.proveCurrent(proof,accepts));}
            f.cohort=new V53PendingCertificateFixture.Cohort(proof,f.f.certificate(proof,proofs),accepts,proofs);
            for(int n:f.f.f.nodes)try(var store=f.open(root,n,f.f.f.resources(),e->{})){store.certifyCurrent(f.cohort.certificate(),f.cohort.owned());}
            var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();MembershipCheckpointPlan checkpoint=null;
            for(int n:f.f.f.nodes) {
                if(at==6 && n==3)continue;
                try(var store=f.open(root,n,f.f.f.resources(),e->{})){var result=f.apply(store);checkpoint=result.plan();acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());}
            }
            Path node=f.f.f.node(root,1),old=node.resolve("generations/b");var promise=read(old,"promise.gsr","PROMISE");var basis=read(old,"basis.gsr","BASIS");var selected=read(old,"selected.gsr","SELECTED");
            var originals=V53ReplayFilesTest.files(node);var observations=new HashSet<>(f.f.f.f.fixture.owned);observations.addAll(f.cohort.owned());observations.addAll(owned);
            MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,observations);
            var plan=MembershipGenerationPlan.published(f.f.f.f.root(),V53DeclarationsTest.node(1),"a",promise,basis,selected,checkpoint,acks,owned,List.of());
            plan.verify(f.f.f.f.fixture.source.root,V53DeclarationsTest.node(1),verifier,List.of(checkpoint.originalParent()));var resources=f.f.f.resources();
            try(var owner=MembershipBallotAllocator.openWithAppliedEnd(node,f.f.f.f.root(),V53DeclarationsTest.node(1),e->{});
                var current=new MembershipCurrentGeneration(node,f.f.f.f.root(),V53DeclarationsTest.node(1),resources,List.of(promise),List.of(basis),List.of(selected),verifier,e->{},true);
                var inactive=new MembershipGenerationFiles(node,current.generation,resources)) {
                inactive.install(plan,current.selector.bytes(),owner::checkOwner,current::check,e->{});
            }
            assertEquals(0,resources.usage().leases());
            try(var current=new MembershipCurrentGeneration(node,f.f.f.f.root(),V53DeclarationsTest.node(1),resources,List.of(promise),List.of(basis),List.of(selected),verifier,e->{},true)) {
                assertEquals((long)at+1,current.capsule.context.cut.get("index"));assertEquals(at==0?42L:41L,current.capsule.context.catalog.get("applicationSequence"));
                assertArrayEquals(selected.bytes(),Files.readAllBytes(node.resolve("generations/a/selected.gsr")));assertNull(current.accepted);
                var forced=new Owned("node-1",V53DeclarationsTest.node(1).storageId(),current.manifest.digest(),cutDigest(current.capsule.context.cut));
                assertNotNull(MembershipFloor.Copy.verify(current.manifest,current.capsule,V53DeclarationsTest.node(1),Set.of(forced),current.copyFiles()));
                assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(current.manifest,current.capsule,V53DeclarationsTest.node(1),Set.of(),current.copyFiles()));
            }
            for(var row:originals.entrySet())if(!row.getKey().equals("selector.gsr"))assertEquals(row.getValue(),hash(Files.readAllBytes(node.resolve(row.getKey()))),row.getKey());
            // This component does not prematurely discard covered pending votes or enable the journal/public runtime.
            assertThrows(IllegalArgumentException.class,()->f.open(root,1,f.f.f.resources(),e->{}));
        }
    }
    static Decoded read(Path dir,String name,String kind)throws IOException{return decode(Files.readAllBytes(dir.resolve(name)),"records",kind);}
    @Test void exactPublishedGenerationRecoversAtEveryInstallCutAndRejectsChangedCoverage()throws Exception {
        var f=new Fixture(3,"ADD",1);var cuts=new ArrayList<>(V53GenerationInstallTest.CUTS);cuts.remove("INSTALL_BEFORE_RETURN");
        for(String point:cuts) {
            Path path=temp.resolve(point);f.provision(path);var originals=V53ReplayFilesTest.files(path);
            assertThrows(IOException.class,()->f.install(path,e->{if(e.equals(point))throw new IOException(point);}));
            var selected=read(path,"selector.gsr","SELECTOR");
            if(selected.value().get("generation").equals("a"))assertThrows(IOException.class,()->f.install(path,e->{if(e.equals("INSTALL_SELECTOR_WRITTEN"))throw new IOException("again");}));
            f.install(path,e->{});f.install(path,e->{});
            for(var row:originals.entrySet())if(!row.getKey().equals("selector.gsr"))assertEquals(row.getValue(),hash(Files.readAllBytes(path.resolve(row.getKey()))));
        }
        Path path=temp.resolve("changed");f.provision(path);
        assertThrows(IOException.class,()->f.install(path,e->{if(e.equals("INSTALL_GENERATION_FORCED"))throw new IOException("cut");}));
        Path coverage=path.resolve("generations/b/"+MembershipSelectionCoverage.FILE);byte[] bytes=Files.readAllBytes(coverage);bytes[bytes.length/2]^=1;Files.write(coverage,bytes);
        var preserved=V53ReplayFilesTest.files(path);assertThrows(IllegalArgumentException.class,()->f.install(path,e->{}));assertEquals(preserved,V53ReplayFilesTest.files(path));
    }
    @Test void publishedPlanSurvivesFreshProcessHaltsAndKillsWithoutDiscardingOriginalDecision()throws Exception {
        Path root=Path.of("target/v53-published-generation-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);
        var f=new Fixture(3,"ADD",1);var cases=new ArrayList<Map<String,Object>>();
        for(String mode:List.of("halt","kill"))for(String point:List.of("INSTALL_MANIFEST_FORCED","INSTALL_GENERATION_FORCED","INSTALL_SELECTOR_FORCED","INSTALL_SELECTOR_RENAMED")) {
            Path dir=root.resolve(mode+"-"+point),node=dir.resolve("node");Files.createDirectories(dir);f.provision(node);
            V53JournalApplicationTest.copy(node,dir.resolve("original"));
            child(dir,"fault",point,mode);V53JournalApplicationTest.copy(node,dir.resolve("crash"));
            String again=read(node,"selector.gsr","SELECTOR").value().get("generation").equals("a")?"INSTALL_SELECTOR_WRITTEN":"CURRENT_VALIDATED";
            child(dir,"recovery-fault",again,"halt");V53JournalApplicationTest.copy(node,dir.resolve("recovery-crash"));
            child(dir,"resume","none","none");V53JournalApplicationTest.copy(node,dir.resolve("final"));
            for(var row:V53ReplayFilesTest.files(dir.resolve("original")).entrySet())if(!row.getKey().equals("selector.gsr"))assertEquals(row.getValue(),hash(Files.readAllBytes(node.resolve(row.getKey()))));
            cases.add(Map.of("mode",mode,"cut",point,"recoveryCut",again,"manifest",f.plan().manifest.digest(),"status","PASS"));
        }
        Files.write(root.resolve("receipt.json"),canonical(Map.of("cases",cases,"freshJvms",24L,"execution","private-published-generation",
                "observations","conditional-fixture","journalPublication",false,"powerLoss",false),65536));
        System.out.println("v53PublishedGenerationEvidence="+root.toAbsolutePath());
    }
    static void child(Path root,String label,String point,String mode)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53PublishedGenerationWorker.class.getName(),root.resolve("node").toAbsolutePath().toString(),point,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                long deadline=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).contains("AWAITING_KILL")){assertTrue(process.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"marker deadline");Thread.sleep(20);}process.destroyForcibly();
            }
            assertTrue(process.waitFor(30,java.util.concurrent.TimeUnit.SECONDS));assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
