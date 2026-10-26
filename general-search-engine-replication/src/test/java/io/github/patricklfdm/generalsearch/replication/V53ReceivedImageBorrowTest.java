package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;
import static io.github.patricklfdm.generalsearch.replication.V53SourceReceiveTest.*;

/** A copied packet cannot lend an image until the complete physical owner is live. */
class V53ReceivedImageBorrowTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture()throws Exception {
        var helper=new V53SourceReceiveTest();helper.temp=temp;return helper.fixture(3);
    }
    static MembershipSourceReceive prefix(Path path,MembershipSourceExport export,MembershipResources budget,
            MembershipImageBorrow parent,AtomicLong clock)throws Exception {
        var source=export.source();return new MembershipSourceReceive(path,source.capsule.context.root,source.owner,
                source.capsule.context.cut,UUID.randomUUID(),UUID.randomUUID(),packetOffer(export),budget,1024,clock::get,0,100,parent);
    }
    static void complete(MembershipSourceReceive received,MembershipSourceExport export)throws Exception {
        send(received,export,received.packetBinding());for(var image:received.imageBindings())send(received,export,image);
    }
    @Test void completeOriginalLendsAtSevenImageCapacityWithoutAllocatingAnotherImage()throws Exception {
        var f=fixture();var target=f.request.targets().getFirst();var budget=budget();var held=new ArrayList<MembershipResources.Lease>();
        try(var owner=f.open(target,"image-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var original=receiver(temp.resolve("original"),export,budget,new AtomicLong(),100)) {
            complete(original,export);int originals=original.packet().images().size();
            try {
                for(int n=originals;n<7;n++)held.add(budget.reserve(Unit.APPLICATION,"occupied-"+n,1));
                var before=budget.usage();
                try(var borrowed=prefix(temp.resolve("prefix"),export,budget,original,new AtomicLong())) {
                    complete(borrowed,export);assertTrue(borrowed.imageBindings().isEmpty());
                    assertEquals(7,budget.usage().counts().get(Unit.APPLICATION));assertEquals(before.staging()+borrowed.packet().bytes().length,budget.usage().staging());
                    assertEquals(original.packet().images(),borrowed.packet().images());
                    for(var image:original.images().entrySet())assertArrayEquals(image.getValue(),borrowed.images().get(image.getKey()));
                    assertThrows(IllegalArgumentException.class,borrowed::basis);assertThrows(IllegalArgumentException.class,borrowed::promise);
                }
                assertEquals(before,budget.usage());original.recheck();
            }finally{for(var lease:held)lease.close();}
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void incompleteOriginalCannotReserveChildOrLendAdvertisedHashes()throws Exception {
        var f=fixture();var budget=budget();
        try(var owner=f.open(f.request.targets().getFirst(),"incomplete");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var original=receiver(temp.resolve("original"),export,budget,new AtomicLong(),100)) {
            var before=budget.usage();assertThrows(IllegalArgumentException.class,()->prefix(temp.resolve("prefix"),export,budget,original,new AtomicLong()));
            assertEquals(before,budget.usage());assertFalse(Files.exists(temp.resolve("prefix")));
            send(original,export,original.packetBinding());before=budget.usage();
            assertThrows(IllegalArgumentException.class,()->prefix(temp.resolve("prefix"),export,budget,original,new AtomicLong()));
            assertEquals(before,budget.usage());assertFalse(Files.exists(temp.resolve("prefix")));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void closedExpiredChangedOrReplacedOriginalRevokesItsBorrowAndCleanupStillWorks()throws Exception {
        for(String fault:List.of("closed","expired","packet","image","replacement")) {
            var f=fixture();var budget=budget();var clock=new AtomicLong();Path directory=temp.resolve("original-"+fault);
            try(var owner=f.open(f.request.targets().getFirst(),fault);var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
                var original=receiver(directory,export,budget,clock,100)) {
                complete(original,export);
                try(var borrowed=prefix(temp.resolve("prefix-"+fault),export,budget,original,new AtomicLong())) {
                    complete(borrowed,export);String digest=original.packet().images().keySet().iterator().next();
                    Path changed=directory.resolve(fault.equals("packet")?"source.gscp":digest+".image"),saved=temp.resolve("saved-"+fault);
                    switch(fault) {
                        case "closed" -> original.close();
                        case "expired" -> clock.set(100);
                        case "replacement" -> {Files.move(changed,saved);Files.copy(saved,changed);}
                        default -> {byte[] bytes=Files.readAllBytes(changed);bytes[bytes.length-1]^=1;Files.write(changed,bytes);}
                    }
                    try{assertThrows(Exception.class,borrowed::recheck);assertThrows(Exception.class,borrowed::images);}
                    finally{if(fault.equals("replacement")){Files.delete(changed);Files.move(saved,changed);}}
                }
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void borrowedOriginalRetainsTheActualExportLifetimeThroughBothReceivers()throws Exception {
        var f=fixture();var budget=budget();
        try(var owner=f.open(f.request.targets().getFirst(),"borrowed-original");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
            var source=export.source();
            try(var original=new MembershipSourceReceive(temp.resolve("original"),source.capsule.context.root,source.owner,export.promise(),source.basis,
                    UUID.randomUUID(),UUID.randomUUID(),packetOffer(export),budget,1024,()->0,0,100,export)) {
                complete(original,export);assertTrue(original.imageBindings().isEmpty());
                try(var borrowed=prefix(temp.resolve("prefix"),export,budget,original,new AtomicLong())) {
                    complete(borrowed,export);assertTrue(borrowed.imageBindings().isEmpty());borrowed.recheck();
                    assertEquals(0,budget.usage().counts().getOrDefault(Unit.APPLICATION,0));
                    export.close();assertThrows(IllegalArgumentException.class,borrowed::recheck);assertThrows(IllegalArgumentException.class,borrowed::images);
                }
            }
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void anotherRootIsRejectedBeforeAllocatingThePrefix()throws Exception {
        var f=fixture();var other=fixture();var budget=budget();
        try(var owner=f.open(f.request.targets().getFirst(),"original");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var original=receiver(temp.resolve("original"),export,budget,new AtomicLong(),100);
            var foreign=other.open(other.request.targets().getFirst(),"foreign");var changed=foreign.exportSource(foreign.beginActivation().basis,BUDGET)) {
            complete(original,export);var before=budget.usage();
            assertEquals("receive borrowed image root",assertThrows(IllegalArgumentException.class,
                    ()->prefix(temp.resolve("prefix"),changed,budget,original,new AtomicLong())).getMessage());
            assertEquals(before,budget.usage());assertFalse(Files.exists(temp.resolve("prefix")));original.recheck();
        }
        assertEquals(0,budget.usage().leases());
    }
}
