package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CurrentGenerationTest {
    @TempDir Path temp;
    static final List<String> OPEN_CUTS=List.of("CURRENT_VALIDATED","CURRENT_FILES_FORCED","CURRENT_GENERATION_FORCED","CURRENT_SELECTOR_FORCED","CURRENT_DIRECTORY_FORCED");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,V53CurrentGenerationFixture f,MembershipResources resources,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,cut);
    }
    Path create(String name,V53CurrentGenerationFixture f) throws Exception {Path path=temp.resolve(name);f.provision(path);return path;}
    Map<String,Object> ballot(long n){return new V53ContextFixture(3,"REPLACE").ballot(n);}
    @Test void selectedPhysicalParentTailAndImagesAreTheOnlyGrantSource() throws Exception {
        for(int size:List.of(3,4,5))for(boolean tail:List.of(false,true)) {
            var f=new V53CurrentGenerationFixture(size,1,tail);Path path=create(size+"-"+tail,f);var resources=resources();Decoded first;
            try(var store=open(path,f,resources,e->{})) {
                assertEquals(tail,store.currentOwnedTail().isPresent());
                if(tail){var owned=store.currentOwnedTail().orElseThrow();assertEquals(f.accepted,owned.record());assertEquals(MembershipContext.cutDigest(f.admitted.context.cut),owned.parent());assertEquals(V53DeclarationsTest.node(1).storageId(),owned.storage());}
                first=store.prepareCurrent(ballot(20));assertEquals(f.admitted.context.cut,first.value().get("cut"));assertEquals(f.accepted,first.value().get("accepted"));
                assertArrayEquals(first.bytes(),store.prepareCurrent(ballot(20)).bytes());
                var other=new V53CapsuleFixture(size,"REPLACE",0);
                assertThrows(IllegalArgumentException.class,()->store.prepare(other.verify(),ballot(21),null,other.source.images));
                assertThrows(IllegalArgumentException.class,()->store.observe(other.verify().context,ballot(21)));
                assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=open(path,f,resources,e->{})){assertArrayEquals(first.bytes(),store.prepareCurrent(ballot(20)).bytes());store.prepareCurrent(ballot(21));}
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void interruptedOpenReleasesOwnerAndReservationsWithoutRewritingAuthority() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);
        for(String cut:OPEN_CUTS) {
            Path path=create(cut,f);var resources=resources();byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));
            assertThrows(IOException.class,()->open(path,f,resources,e->{if(e.equals(cut))throw new IOException("injected");}));
            assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(0,resources.usage().leases());
            try(var store=open(path,f,resources,e->{})){assertNotNull(store.prepareCurrent(ballot(20)));}
        }
    }
    @Test void currentAuthorityCannotChangeDuringCaptureOrJustBeforeGrantReturn() throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,true);
        for(String cut:List.of("CURRENT_BEFORE_CAPTURE","PROMISE_BEFORE_WRITE","SOURCE_DIRECTORY_FORCED","BASIS_FORCED","GRANT_BEFORE_RETURN")) {
            Path path=create("changed-"+cut,f);Path selector=path.resolve("selector.gsr");
            try(var store=open(path,f,resources(),e->{if(e.equals(cut)){byte[] bytes=Files.readAllBytes(selector);Files.move(selector,temp.resolve("old-"+cut));Files.write(selector,bytes);}})) {
                assertThrows(Exception.class,()->store.prepareCurrent(ballot(20)));
            }
        }
    }
    @Test void higherObservationStillFencesWithoutAcquiringWriterMonitor() throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,true);Path path=create("concurrent",f);var written=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var store=open(path,f,resources(),e->{if(e.equals("SOURCE_PACKET_FORCED")){
            written.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new IOException("coordination timeout");}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
        }});var executor=Executors.newSingleThreadExecutor()) {
            Future<?> future=executor.submit(()->{try{return store.prepareCurrent(ballot(20));}catch(IOException error){throw new RuntimeException(error);}});
            try{assertTrue(written.await(10,TimeUnit.SECONDS));store.observeCurrent(ballot(21));}finally{release.countDown();}
            assertTrue(assertThrows(ExecutionException.class,()->future.get(10,TimeUnit.SECONDS)).getCause().getMessage().contains("higher ballot"));
        }
    }
    @Test void concurrentDuplicateCapturesSerializeToOneOriginalBasis() throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,true);Path path=create("duplicates",f);
        try(var store=open(path,f,resources(),e->{});var executor=Executors.newFixedThreadPool(4)) {
            var futures=new ArrayList<Future<Decoded>>();for(int i=0;i<4;i++)futures.add(executor.submit(()->store.prepareCurrent(ballot(20))));
            byte[] expected=futures.getFirst().get(10,TimeUnit.SECONDS).bytes();
            for(var future:futures)assertArrayEquals(expected,future.get(10,TimeUnit.SECONDS).bytes());
            try(var files=Files.list(path.resolve("sources"))){assertEquals(1,files.count());}
        }
    }
    @Test void missingCorruptLinkedOrExtraCurrentFilesRefuseOpenWithoutRepair() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);
        for(String variant:List.of("selector","manifest","packet","image","tail","promise","extra","inactive","symlink","hardlink")) {
            Path path=create("bad-"+variant,f);var resources=resources();Path generation=path.resolve("generations/a");
            Path image=generation.resolve(f.admitted.terminal().application()+".image");
            switch(variant) {
                case "selector" -> Files.delete(path.resolve("selector.gsr"));
                case "manifest" -> Files.write(generation.resolve("generation.gsr"),new byte[]{1});
                case "packet" -> Files.write(generation.resolve("source.gscp"),new byte[]{1});
                case "image" -> Files.delete(image);
                case "tail" -> Files.delete(generation.resolve("owned-tail.gsr"));
                case "promise" -> Files.write(path.resolve("grants.gsr"),new byte[0]);
                case "extra" -> Files.write(generation.resolve("extra"),new byte[]{1});
                case "inactive" -> Files.createDirectory(path.resolve("generations/b"));
                case "symlink" -> {Path target=temp.resolve("image-copy");Files.move(image,target);Files.createSymbolicLink(image,target);}
                case "hardlink" -> Files.createLink(temp.resolve("image-alias"),image);
            }
            byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));assertThrows(Exception.class,()->open(path,f,resources,e->{}));
            assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    static void rewrite(Path path,java.util.function.Consumer<Map<String,Object>> change) throws Exception {
        Path file=path.resolve("generations/a/generation.gsr");var body=object(V53ContextFixture.mutable(decode(Files.readAllBytes(file),"records","GENERATION").value()));
        change.accept(body);byte[] bytes=encode("records","GENERATION",body);Files.write(file,bytes);
        var selector=object(V53ContextFixture.mutable(decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR").value()));
        selector.put("digest",hash(bytes));Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",selector));
    }
    @Test void validChecksumsCannotRebindParentTailPromiseOrLocalIdentity() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);
        for(String field:List.of("root","node","cut","promise","ownedTail","catalog","application","capsule","selection","basis")) {
            Path path=create("rebound-"+field,f);rewrite(path,value->{
                if(field.equals("node"))value.put(field,"node-2");
                else if(field.equals("cut"))object(value.get("cut")).put("index",0L);
                else value.put(field,"00".repeat(32));
            });assertThrows(Exception.class,()->open(path,f,resources(),e->{}));
        }
        Path omitted=create("omitted-tail",f);rewrite(omitted,value->value.put("ownedTail",null));assertThrows(Exception.class,()->open(omitted,f,resources(),e->{}));
    }
    @Test void verifierCannotSubstituteAnotherCutAndResourceRefusalReleasesLock() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);Path path=create("verifier",f);var resources=resources();
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(1),resources,
                (root,packet,images)->new V53CapsuleFixture(3,"REPLACE",0).verify(),e->{}));assertEquals(0,resources.usage().leases());
        var small=new MembershipResources(1);assertThrows(Exception.class,()->open(path,f,small,e->{}));assertEquals(0,small.usage().leases());
        try(var store=open(path,f,resources,e->{})){assertNotNull(store.prepareCurrent(ballot(20)));}
        try(var store=open(path,f,resources,e->{})) {
            assertThrows(Exception.class,()->MembershipGrantJournal.openRetained(path,f.root(),V53DeclarationsTest.node(1),resources(),e->{}));
            assertThrows(Exception.class,()->open(path,f,resources(),e->{}));
        }
    }
    @Test void slotBUsesItsExactSelectorAndKnownJournalCutRejectsAValidOlderGeneration() throws Exception {
        var f=new V53CurrentGenerationFixture(3,1,true);Path path=create("slot-b",f);
        var manifest=object(V53ContextFixture.mutable(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value()));
        manifest.put("generation","b");byte[] bytes=encode("records","GENERATION",manifest);
        Files.move(path.resolve("generations/a"),path.resolve("generations/b"));Files.write(path.resolve("generations/b/generation.gsr"),bytes);
        var selector=object(V53ContextFixture.mutable(decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR").value()));
        selector.put("generation","b");selector.put("digest",hash(bytes));Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",selector));
        try(var store=open(path,f,resources(),e->{})){assertNotNull(store.prepareCurrent(ballot(20)));}
        var old=new V53CurrentGenerationFixture(3,0,true);Path oldPath=create("older-generation",old);
        Files.move(path.resolve("generations/b"),temp.resolve("saved-current"));
        Files.move(oldPath.resolve("generations/a"),path.resolve("generations/a"));
        Files.copy(oldPath.resolve("selector.gsr"),path.resolve("selector.gsr"),StandardCopyOption.REPLACE_EXISTING);
        var resources=resources();var error=assertThrows(IllegalArgumentException.class,()->open(path,old,resources,e->{}));
        assertEquals("current generation differs from retained grant cut",error.getMessage());assertEquals(0,resources.usage().leases());
    }
}
