package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import io.github.patricklfdm.generalsearch.durability.DurableApplicationState;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceImageValidationTest {
    @TempDir Path temp;
    static final long BUDGET=1_000_000;
    V53BootstrapPublicationTest.Fixture fixture(int documents)throws Exception {
        Path base=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
        var config=builder().configuration();var docs=new ArrayList<Doc>();
        for(int n=0;n<documents;n++)docs.add(new Doc(n,"x".repeat(60000)));
        Path source=base.resolve("source");
        MembershipApplicationImage.capture(config,storage(base.resolve("source-core"),2),
                new DurableApplicationState<>(V53BootstrapSeedTest.IMPORTED,41,docs,config.indexes()),source);
        var helper=new V53BootstrapSeedTest();helper.temp=base;
        return new V53BootstrapPublicationTest.Fixture(Files.createDirectory(base.resolve("raw")),helper.request(base.resolve("group"),3,source));
    }
    @Test void wholeImageValidationWorkDoesNotGrowWithTransferChunkCount()throws Exception {
        var counts=new ArrayList<Long>();
        for(int documents:List.of(1,144)) {
            var f=fixture(documents);var target=f.request.targets().getFirst();var calls=new AtomicLong();
            LongSupplier clock=()->{calls.incrementAndGet();return 0;};
            try(var owner=f.open(target,"whole-image");var export=owner.exportSource(owner.beginActivation().basis,clock,BUDGET)) {
                var image=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                if(documents==144)assertTrue(image.bytes()>8*1024*1024);
                var usage=f.resources.usage();calls.set(0);byte[] bytes=export.image(image.digest(),image.bytes());
                counts.add(calls.get());assertEquals(image.bytes(),bytes.length);assertEquals(image.digest(),hash(bytes));
                assertEquals(usage,f.resources.usage());
                // Wire callers retain the independent 4 MiB chunk cap.
                assertThrows(IllegalArgumentException.class,()->export.read(image.digest(),0,4*1024*1024+1));
            }
            assertEquals(0,f.resources.usage().leases());
        }
        assertEquals(counts.getFirst(),counts.getLast(),"one guarded whole-image read must not revalidate all storage per transfer chunk");
    }
    @Test void checkingAnImageUsesTheExistingPhysicalOwnerValidation()throws Exception {
        var f=fixture(1);var calls=new AtomicLong();LongSupplier clock=()->{calls.incrementAndGet();return 0;};
        try(var owner=f.open(f.request.targets().getFirst(),"check-image");var export=owner.exportSource(owner.beginActivation().basis,clock,BUDGET)) {
            var image=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
            calls.set(0);assertTrue(export.hasImage(image.digest(),image.bytes()));long physicalCheck=calls.get();
            calls.set(0);export.checkImage(image.digest(),image.bytes());
            assertEquals(physicalCheck,calls.get(),"validation must not materialize and reread a borrowed image");
            assertThrows(IllegalArgumentException.class,()->export.checkImage(image.digest(),image.bytes()+1));
            assertThrows(IllegalArgumentException.class,()->export.checkImage("0".repeat(64),1));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void wholeImageReadRechecksBytesInodeExpiryAndCloseBeforeReturning()throws Exception {
        for(String fault:List.of("bytes","inode","expiry","close")) {
            var f=fixture(1);var target=f.request.targets().getFirst();var calls=new AtomicInteger();
            var armed=new AtomicBoolean();var expired=new AtomicBoolean();var action=new AtomicReference<Runnable>(()->{});
            LongSupplier clock=()->{
                if(armed.get() && calls.incrementAndGet()==3)action.get().run();
                return expired.get()?BUDGET:0;
            };
            try(var owner=f.open(target,"late-change");var export=owner.exportSource(owner.beginActivation().basis,clock,BUDGET)) {
                var image=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                Path path=target.replicaDirectory().resolve("sources").resolve(export.basisId()).resolve(image.digest()+".image");
                byte[] original=Files.readAllBytes(path);
                assertArrayEquals(original,export.image(image.digest(),image.bytes()));
                action.set(()->{
                    try {
                        switch(fault) {
                            case "bytes" -> {byte[] changed=original.clone();changed[changed.length-1]^=1;Files.write(path,changed);}
                            case "inode" -> {Path replacement=path.resolveSibling("replacement");Files.write(replacement,original);Files.move(replacement,path,StandardCopyOption.REPLACE_EXISTING);}
                            case "expiry" -> expired.set(true);
                            case "close" -> export.close();
                            default -> throw new AssertionError(fault);
                        }
                    }catch(Exception error){throw new AssertionError(error);}
                });
                calls.set(0);armed.set(true);
                assertThrows(IllegalArgumentException.class,()->export.image(image.digest(),image.bytes()),fault);
                armed.set(false);
                assertThrows(IllegalArgumentException.class,()->export.checkImage(image.digest(),image.bytes()),fault);
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
}
