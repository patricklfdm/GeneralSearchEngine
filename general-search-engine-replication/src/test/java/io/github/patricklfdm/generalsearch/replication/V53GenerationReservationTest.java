package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Conditional original disk histories, with explicit competing accounting pressure.
 * These do not claim a native distributed simultaneous physical maximum. */
class V53GenerationReservationTest {
    @TempDir Path temp;

    @Test void groupedExpansionRollsBackGrowthAndNewHandlesTogether() {
        var budget=new MembershipResources(HEADROOM+50,100,100);
        try(var metadata=budget.reserve(Unit.GENERATION,"b",10);
            var image=budget.reserve(Unit.APPLICATION,"old-image",10)) {
            var baseline=budget.usage();
            var growth=new LinkedHashMap<MembershipResources.Lease,Long>();growth.put(metadata,40L);growth.put(image,40L);
            var additions=List.of(new StorageReservation(Unit.APPLICATION,"new-image",20),
                    new StorageReservation(Unit.APPLICATION,"too-large",50));
            assertEquals("shared staging capacity",assertThrows(IllegalArgumentException.class,
                    ()->budget.extendGeneration(growth,additions)).getMessage());
            assertEquals(baseline,budget.usage());
            try(var available=budget.reserve(Unit.APPLICATION,"new-image",90)) {assertEquals(100,budget.usage().staging());}
            assertEquals(baseline,budget.usage());
            var acquired=budget.extendGeneration(growth,List.of(additions.getFirst()));
            assertEquals(40,budget.usage().metadata());assertEquals(60,budget.usage().staging());
            assertEquals(3,budget.usage().leases());
            acquired.forEach(MembershipResources.Lease::close);
            assertEquals(40,budget.usage().staging());
        }
        assertEquals(0,budget.usage().leases());
    }

    @Test void completionHeadroomCountForeignAndClosedHandlesRejectWithoutMutation() {
        var budget=new MembershipResources(HEADROOM+40,100,100);
        var foreign=new MembershipResources(100);
        try(var metadata=budget.reserve(Unit.GENERATION,"b",10);
            var foreignLease=foreign.reserve(Unit.APPLICATION,"foreign",1)) {
            var baseline=budget.usage();
            assertEquals("completion headroom",assertThrows(IllegalArgumentException.class,
                    ()->budget.extendGeneration(Map.of(metadata,41L),List.of())).getMessage());
            assertEquals(baseline,budget.usage());
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(foreignLease,10L),List.of()));
            assertEquals(baseline,budget.usage());assertEquals(1,foreign.usage().staging());
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(metadata,20L),
                    List.of(new StorageReservation(Unit.GENERATION,"a",1),new StorageReservation(Unit.GENERATION,"third",1))));
            assertEquals(baseline,budget.usage());
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(metadata,20L),
                    List.of(new StorageReservation(Unit.GENERATION,"b",1))));
            assertEquals(baseline,budget.usage());
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(metadata,20L),
                    List.of(new StorageReservation(Unit.SOURCE,"foreign-category",1))));
            assertEquals(baseline,budget.usage());
            var closed=budget.reserve(Unit.APPLICATION,"closed",1);closed.close();
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(closed,10L),List.of()));
            assertEquals(baseline,budget.usage());
        }
    }

    @Test void existingCompletionMaximumIsNeverShrunkOrDoubleCharged() {
        var budget=new MembershipResources(512*MIB);
        try(var metadata=budget.reserve(Unit.GENERATION,"b",20);
            var image=budget.reserve(Unit.APPLICATION,"original",10)) {
            image.reserveApplicationMaximum();var baseline=budget.usage();
            assertTrue(budget.extendGeneration(Map.of(metadata,10L,image,10L),List.of()).isEmpty());
            assertEquals(baseline,budget.usage());
            budget.extendGeneration(Map.of(metadata,30L,image,20L),List.of());
            assertEquals(30,budget.usage().metadata());assertEquals(64*MIB,budget.usage().staging());
            assertEquals(1,budget.usage().counts().get(Unit.APPLICATION));
        }
    }

    @Test void metadataRefusalAlsoRetainsAnAlreadyWrittenApplicationImage()throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);
        Path node=temp.resolve("image-partial");f.provision(node);
        var initial=new MembershipResources(512*MIB);
        try(var owner=f.open(node,initial,event->{if(event.equals("INSTALL_IMAGE_FORCED"))throw new IOException("image cut");})) {
            assertEquals("image cut",assertThrows(IOException.class,()->owner.installCurrent(f.offers(owner,20),f.bridges,f.images())).getMessage());
        }
        long metadata;
        try(var owner=f.open(node,initial,event->{})) {metadata=initial.usage().metadata();}
        // The journal and MISC reserve 34 MiB. Preserve the remaining 2 MiB
        // completion headroom while denying any growth of ordinary metadata.
        var budget=new MembershipResources(metadata+2*MIB,512*MIB,QUEUE_LIMIT);
        var original=V53ReplayFilesTest.files(node);
        try(var owner=f.open(node,budget,event->{})) {
            var before=budget.usage();assertEquals(3,before.counts().get(Unit.APPLICATION));
            assertEquals("completion headroom",assertThrows(IllegalArgumentException.class,
                    ()->owner.installCurrent(f.offers(owner,20),f.bridges,f.images())).getMessage());
            assertEquals(before,budget.usage());assertEquals(original,V53ReplayFilesTest.files(node));
        }
        assertEquals(0,budget.usage().leases());
        try(var owner=f.open(node,initial,event->{})) {
            assertNotNull(owner.installCurrent(f.offers(owner,20),f.bridges,f.images()));
        }
        assertEquals(0,initial.usage().leases());
    }

    @Test void refusedResumeKeepsPartialManifestChargedUntilOwnerClose()throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);
        Path node=temp.resolve("node");f.provision(node);
        var budget=new MembershipResources(512*MIB);
        try(var owner=f.open(node,budget,event->{if(event.equals("INSTALL_MANIFEST_FORCED"))throw new IOException("cut");})) {
            assertEquals("cut",assertThrows(IOException.class,()->owner.installCurrent(f.offers(owner,20),f.bridges,f.images())).getMessage());
        }
        assertEquals(0,budget.usage().leases());
        var original=V53ReplayFilesTest.files(node);var pressure=new ArrayList<MembershipResources.Lease>();
        try(var owner=f.open(node,budget,event->{})) {
            for(int n=budget.usage().counts().get(Unit.APPLICATION);n<7;n++)pressure.add(budget.reserve(Unit.APPLICATION,"pressure-"+n,1));
            var before=budget.usage();assertEquals(2,before.counts().get(Unit.GENERATION));
            var failure=assertThrows(IllegalArgumentException.class,()->owner.installCurrent(f.offers(owner,20),f.bridges,f.images()));
            assertEquals("resource ownership/count",failure.getMessage());
            assertEquals(original,V53ReplayFilesTest.files(node));
            assertEquals(before,budget.usage(),"rejected expansion must retain every original physical charge");
        }finally{pressure.forEach(MembershipResources.Lease::close);}
        assertEquals(0,budget.usage().leases());
        try(var owner=f.open(node,budget,event->{})) {
            assertNotNull(owner.installCurrent(f.offers(owner,20),f.bridges,f.images()));
        }
        assertEquals(0,budget.usage().leases());
    }
}
