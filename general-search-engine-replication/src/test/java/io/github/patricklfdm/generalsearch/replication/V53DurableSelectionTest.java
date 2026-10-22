package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53DurableSelectionTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("SELECTED_BEFORE_WRITE","SELECTED_WRITTEN","SELECTED_FORCED","SELECTED_BEFORE_RETURN");
    static MembershipGrantJournal open(Path path,V53CurrentGenerationFixture f,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(1),new MembershipResources(512*MembershipResources.MIB),f::verify,cut);
    }
    static List<MembershipSelection.Source> offers(MembershipGrantJournal store,int size,long ballot,boolean alternate) throws Exception {
        return V53DurableSelectionWorker.offers(store,size,ballot,alternate);
    }
    Path create(String name,V53CurrentGenerationFixture f) throws Exception {
        Path path=temp.resolve(name);f.provision(path);try(var store=open(path,f,e->{})){store.prepareCurrent(f.fixture.source.ballot(20));}return path;
    }
    @Test void exactOriginalDecisionSurvivesReopenAndOnlyFreshBallotPermitsReselection() throws Exception {
        for(int size:List.of(3,4,5))for(boolean tail:List.of(false,true)) {
            var f=new V53CurrentGenerationFixture(size,1,tail);Path path=create(size+"-"+tail,f);Decoded selected;
            try(var store=open(path,f,e->{})) {
                var offered=offers(store,size,20,false);selected=store.selectCurrent(offered,List.of());
                assertEquals(offered.get(1).entry.digest(),selected.value().get("nextEntry"));
                assertArrayEquals(selected.bytes(),store.selectCurrent(offered,List.of()).bytes());
                assertArrayEquals(selected.bytes(),store.originalSelection().orElseThrow().bytes());
            }
            byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));
            try(var store=open(path,f,e->{})) {
                assertArrayEquals(selected.bytes(),store.selectCurrent(offers(store,size,20,false),List.of()).bytes());
                var error=assertThrows(IllegalArgumentException.class,()->store.selectCurrent(offers(store,size,20,true),List.of()));
                assertEquals("selection already fixed; fresh ballot required",error.getMessage());
                assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));
                store.prepareCurrent(f.fixture.source.ballot(21));assertTrue(store.originalSelection().isEmpty());
                assertNotEquals(selected.digest(),store.selectCurrent(offers(store,size,21,true),List.of()).digest());
            }
            try(var store=open(path,f,e->{})){assertEquals(21L,object(store.originalSelection().orElseThrow().value().get("ballot")).get("counter"));}
        }
    }
    @Test void forcedOriginalSourceIsDerivedFromFilesAndCannotBeReplacedByCaller() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);Path path=create("original",f);
        try(var store=open(path,f,e->{})) {
            var actual=store.originalSource();assertArrayEquals(store.originalBasis().orElseThrow().bytes(),actual.basis.bytes());
            var offered=offers(store,3,20,false);offered.set(0,new V53SelectionFixture(3,"REPLACE",1).source("node-1"));
            assertEquals("selection substituted local source",assertThrows(IllegalArgumentException.class,()->store.selectCurrent(offered,List.of())).getMessage());
            assertTrue(store.originalSelection().isEmpty());
            Path packet=path.resolve("sources").resolve((String)actual.basis.value().get("basisId")).resolve("source.gscp");
            byte[] old=Files.readAllBytes(packet);Files.move(packet,temp.resolve("old-packet"));Files.write(packet,old);
            assertThrows(IllegalArgumentException.class,store::originalSource);
        }
    }
    @Test void higherObservedBallotFencesEverySelectionWriteForceAndReturnCut() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);
        for(String point:CUTS) {
            Path path=create(point,f);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=open(path,f,e->{if(e.equals(point))ref[0].observeCurrent(f.fixture.source.ballot(21));})) {
                ref[0]=store;var error=assertThrows(IllegalArgumentException.class,()->store.selectCurrent(offers(store,3,20,false),List.of()));
                assertEquals("higher ballot observed; fresh campaign required",error.getMessage());
            }
            try(var store=open(path,f,e->{})) {
                assertEquals(!point.equals("SELECTED_BEFORE_WRITE"),store.originalSelection().isPresent());
                store.prepareCurrent(f.fixture.source.ballot(21));assertNotNull(store.selectCurrent(offers(store,3,21,false),List.of()));
            }
        }
    }
    @Test void lostResponseAndConcurrentDuplicatesNeverAppendAnotherDecision() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);Path path=create("lost",f);
        try(var store=open(path,f,e->{if(e.equals("SELECTED_BEFORE_RETURN"))throw new IOException("lost");})) {
            assertThrows(IOException.class,()->store.selectCurrent(offers(store,3,20,false),List.of()));
        }
        byte[] original=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,f,e->{});var executor=Executors.newFixedThreadPool(4)) {
            var offered=offers(store,3,20,false);var futures=new ArrayList<Future<Decoded>>();
            for(int i=0;i<4;i++)futures.add(executor.submit(()->store.selectCurrent(offered,List.of())));
            var expected=store.originalSelection().orElseThrow();for(var future:futures)assertArrayEquals(expected.bytes(),future.get(10,TimeUnit.SECONDS).bytes());
            assertArrayEquals(original,Files.readAllBytes(path.resolve("grants.gsr")));
        }
    }
    @Test void higherObservationDoesNotWaitForBlockedSelectionWriter() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);Path path=create("blocked",f);var written=new CountDownLatch(1);var resume=new CountDownLatch(1);
        try(var store=open(path,f,e->{if(e.equals("SELECTED_WRITTEN")) {
            written.countDown();try{if(!resume.await(10,TimeUnit.SECONDS))throw new IOException("coordination timeout");}
            catch(InterruptedException x){Thread.currentThread().interrupt();throw new IOException(x);}
        }});var executor=Executors.newSingleThreadExecutor()) {
            var offered=offers(store,3,20,false);var future=executor.submit(()->store.selectCurrent(offered,List.of()));
            try{assertTrue(written.await(10,TimeUnit.SECONDS));store.observeCurrent(f.fixture.source.ballot(21));}finally{resume.countDown();}
            assertEquals("higher ballot observed; fresh campaign required",assertThrows(ExecutionException.class,()->future.get(10,TimeUnit.SECONDS)).getCause().getMessage());
        }
    }
    @Test void selectorReplacementAtSelectionReturnRefusesAcknowledgement() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);Path path=create("selector",f);
        try(var store=open(path,f,e->{if(e.equals("SELECTED_BEFORE_RETURN")) {
            Path selector=path.resolve("selector.gsr");byte[] bytes=Files.readAllBytes(selector);Files.move(selector,temp.resolve("selector-copy"));Files.write(selector,bytes);
        }})) {assertThrows(IllegalArgumentException.class,()->store.selectCurrent(offers(store,3,20,false),List.of()));}
    }
    @Test void malformedOrDuplicateSelectionIsNeverRepairedOrDroppedOnReopen() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);
        for(String variant:List.of("torn","duplicate","root","ballot","view","local","quorum","parent","index")) {
            Path path=create("bad-"+variant,f);byte[] prefix=Files.readAllBytes(path.resolve("grants.gsr"));Decoded selection;
            try(var store=open(path,f,e->{})){selection=store.selectCurrent(offers(store,3,20,false),List.of());}
            var body=object(V53ContextFixture.mutable(selection.value()));
            switch(variant) {
                case "root" -> body.put("root","00".repeat(32));
                case "ballot" -> object(body.get("ballot")).put("counter",19L);
                case "view" -> body.put("view","00".repeat(32));
                case "local" -> object(list(body.get("sources")).getFirst()).put("basisDigest","00".repeat(32));
                case "quorum" -> object(list(body.get("sources")).get(1)).put("voter","node-9");
                case "parent" -> object(body.get("cut")).put("entry","00".repeat(32));
                case "index" -> object(body.get("cut")).put("index",0L);
            }
            byte[] bad=encode("records","SELECTED",body);
            if(variant.equals("torn"))bad=Arrays.copyOf(bad,bad.length-1);
            byte[] result=new byte[prefix.length+bad.length+(variant.equals("duplicate")?bad.length:0)];
            System.arraycopy(prefix,0,result,0,prefix.length);System.arraycopy(bad,0,result,prefix.length,bad.length);
            if(variant.equals("duplicate"))System.arraycopy(bad,0,result,prefix.length+bad.length,bad.length);
            Files.write(path.resolve("grants.gsr"),result);
            assertThrows(Exception.class,()->open(path,f,e->{}));assertArrayEquals(result,Files.readAllBytes(path.resolve("grants.gsr")));
        }
    }
    @Test void longerProvenSelectionDoesNotPublishOrSwitchCurrentGeneration() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);Path path=create("longer",f);byte[] selector=Files.readAllBytes(path.resolve("selector.gsr"));
        try(var store=open(path,f,e->{})) {
            var longer=new V53SelectionFixture(3,"REPLACE",2);var remote=longer.source("node-2");
            var selected=store.selectCurrent(List.of(store.originalSource(),remote),List.of(longer.bridge(1,2)));
            assertEquals(2L,object(selected.value().get("cut")).get("index"));
            assertArrayEquals(selector,Files.readAllBytes(path.resolve("selector.gsr")));
            assertEquals(1L,object(store.originalBasis().orElseThrow().value().get("cut")).get("index"));
        }
        try(var store=open(path,f,e->{})){assertEquals(2L,object(store.originalSelection().orElseThrow().value().get("cut")).get("index"));}
    }
    @Test void selectedFollowerRecordsItsOwnOriginalGrantAndChecksProposerInclusion() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,false);Path path=temp.resolve("follower");f.provision(path);
        for(String name:List.of("node.gsr","allocator.gsr","generations/a/generation.gsr","selector.gsr")) {
            String kind=switch(name){case "node.gsr"->"NODE";case "allocator.gsr"->"ALLOCATOR";case "selector.gsr"->"SELECTOR";default->"GENERATION";};
            var value=object(V53ContextFixture.mutable(decode(Files.readAllBytes(path.resolve(name)),"records",kind).value()));
            if(kind.equals("NODE"))value.put("identity",V53ContextFixture.member(2));else value.put("node","node-2");
            if(kind.equals("SELECTOR"))value.put("digest",hash(Files.readAllBytes(path.resolve("generations/a/generation.gsr"))));
            Files.write(path.resolve(name),encode("records",kind,value));
        }
        Decoded selected;
        try(var store=MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(2),new MembershipResources(512*MembershipResources.MIB),f::verify,e->{})) {
            store.prepareCurrent(f.fixture.source.ballot(20));var local=store.originalSource();
            var proposer=V53DurableSelectionWorker.remote(new V53SelectionFixture(3,"REPLACE",1),1,20);
            selected=store.selectCurrent(List.of(proposer,local),List.of());
            assertEquals("node-2",object(list(selected.value().get("sources")).get(1)).get("voter"));
            var missing=List.of(local,V53DurableSelectionWorker.remote(new V53SelectionFixture(3,"REPLACE",1),3,20));
            assertEquals("selection missing proposer",assertThrows(IllegalArgumentException.class,()->store.selectCurrent(missing,List.of())).getMessage());
        }
        try(var store=MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(2),new MembershipResources(512*MembershipResources.MIB),f::verify,e->{})) {
            assertArrayEquals(selected.bytes(),store.originalSelection().orElseThrow().bytes());
        }
    }
}
