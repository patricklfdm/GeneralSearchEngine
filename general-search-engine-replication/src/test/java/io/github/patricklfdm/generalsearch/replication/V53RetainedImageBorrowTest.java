package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceReceiveTest.*;

/** Reuse is a live local physical borrow, not an expanded remote source or old vote. */
class V53RetainedImageBorrowTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture()throws Exception {
        var helper=new V53SourceExportTest();helper.temp=temp;var f=helper.fixture(3);f.ownedHistory=true;
        f.campaign(1);f.publish(1,false);f.publish(2,true);return f;
    }
    @Test void retainedOldImageFitsFullCapacityButCannotExpandWireInventory()throws Exception {
        var f=fixture();var target=f.request.targets().getFirst();var extra=new ArrayList<MembershipResources.Lease>();
        try(var owner=f.open(target,"retained-image-borrow")) {
            var old=owner.originalBasis().orElseThrow();String id=(String)old.value().get("basisId");
            var fresh=owner.beginActivation();assertNotEquals(old.digest(),fresh.basis.digest());
            try(var original=owner.exportSource(old,BUDGET);var local=owner.exportSource(fresh.basis,BUDGET)) {
                var image=original.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                var contents=local.contents();var references=local.references();assertFalse(references.containsKey(image.digest()));
                try {
                    for(int n=f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION);n<7;n++)
                        extra.add(f.resources.reserve(MembershipResources.Unit.APPLICATION,"occupied-"+n,1));
                    var before=f.resources.usage();assertTrue(local.hasImage(image.digest(),image.bytes()));assertTrue(local.pinsSource(id));
                    assertEquals(before,f.resources.usage());assertEquals(contents,local.contents());assertEquals(references,local.references());
                    assertThrows(IllegalArgumentException.class,()->local.read(image.digest(),0,1));
                    var source=original.source();
                    try(var received=new MembershipSourceReceive(temp.resolve("received"),source.capsule.context.root,source.owner,original.promise(),source.basis,
                            UUID.randomUUID(),UUID.randomUUID(),packetOffer(original),f.resources,1024,()->0,0,100,local)) {
                        send(received,original,received.packetBinding());assertTrue(received.imageBindings().isEmpty());
                        assertEquals(7,f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                        assertArrayEquals(original.image(image.digest(),image.bytes()),received.images().get(image.digest()));
                    }
                    assertEquals(before,f.resources.usage());original.close();
                    var files=V53ReplayFilesTest.files(target.replicaDirectory());
                    assertEquals("source export pins original files",assertThrows(IllegalArgumentException.class,()->owner.retireSource(id)).getMessage());
                    assertEquals(files,V53ReplayFilesTest.files(target.replicaDirectory()));
                }finally{extra.forEach(MembershipResources.Lease::close);}
            }
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void originalDeadlineAndCloseRevokeSupplementalImageBorrow()throws Exception {
        var f=fixture();var target=f.request.targets().getFirst();var clock=new AtomicLong();
        try(var owner=f.open(target,"borrow-expiry")) {
            var old=owner.originalBasis().orElseThrow();var fresh=owner.beginActivation();
            try(var original=owner.exportSource(old,BUDGET);var local=owner.exportSource(fresh.basis,clock::get,10)) {
                var image=original.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                var before=f.resources.usage();assertFalse(local.hasImage(image.digest(),image.bytes()+1));assertFalse(local.hasImage("0".repeat(64),1));
                assertEquals(before,f.resources.usage());assertTrue(local.hasImage(image.digest(),image.bytes()));
                clock.set(10);assertThrows(IllegalArgumentException.class,()->local.image(image.digest(),image.bytes()));
                clock.set(0);assertThrows(IllegalArgumentException.class,()->local.hasImage(image.digest(),image.bytes()));
            }
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void changedOrReplacedBackingImageCannotBeReadThroughTheNewSource()throws Exception {
        for(boolean replacement:List.of(false,true)) {
            var f=fixture();var target=f.request.targets().getFirst();
            try(var owner=f.open(target,"borrow-corruption")) {
                var old=owner.originalBasis().orElseThrow();var fresh=owner.beginActivation();
                try(var original=owner.exportSource(old,BUDGET);var local=owner.exportSource(fresh.basis,BUDGET)) {
                    var image=original.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                    assertTrue(local.hasImage(image.digest(),image.bytes()));
                    Path path=target.replicaDirectory().resolve("sources").resolve((String)old.value().get("basisId")).resolve(image.digest()+".image");
                    byte[] bytes=Files.readAllBytes(path);Path saved=temp.resolve("saved-"+UUID.randomUUID());
                    if(replacement){Files.move(path,saved);Files.write(path,bytes);}else{bytes[bytes.length-1]^=1;Files.write(path,bytes);}
                    try{assertThrows(Exception.class,()->local.image(image.digest(),image.bytes()));}
                    finally{if(replacement){Files.delete(path);Files.move(saved,path);}}
                }
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
}
