package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Original conditional disk histories; competing reservations are accounting
 * pressure, not simultaneous native physical maximum qualification. */
class V53SourceReservationTest {
    @TempDir Path temp;

    @Test void sourceGroupRefusalRollsBackBothMetadataAndStaging() {
        var budget=new MembershipResources(HEADROOM+100,100,100);
        try(var source=budget.reserve(Unit.SOURCE,"original",10);
            var image=budget.reserve(Unit.APPLICATION,"image",10)) {
            var before=budget.usage();
            var growth=new LinkedHashMap<MembershipResources.Lease,Long>();growth.put(source,30L);growth.put(image,20L);
            var additions=List.of(new StorageReservation(Unit.SOURCE,"new-copy",20),
                    new StorageReservation(Unit.APPLICATION,"too-large",31));
            assertEquals("shared staging capacity",assertThrows(IllegalArgumentException.class,
                    ()->budget.extendSources(growth,additions)).getMessage());
            assertEquals(before,budget.usage());
            try(var available=budget.reserve(Unit.SOURCE,"new-copy",80)) {assertEquals(100,budget.usage().staging());}
            assertEquals(before,budget.usage());
            var acquired=budget.extendSources(growth,List.of(additions.getFirst()));
            assertEquals(50,budget.usage().metadata());assertEquals(70,budget.usage().staging());
            acquired.forEach(MembershipResources.Lease::close);
            assertTrue(budget.extendSources(Map.of(source,1L,image,1L),List.of()).isEmpty());
            assertEquals(30,budget.usage().metadata());assertEquals(50,budget.usage().staging());
        }
        assertEquals(0,budget.usage().leases());
    }

    @Test void sourceGroupCannotAcquireProtectedOrForeignStorage() {
        var budget=new MembershipResources(100);var foreign=new MembershipResources(100);
        try(var original=budget.reserve(Unit.SOURCE,"original",10);
            var generation=budget.reserve(Unit.GENERATION,"a",1);
            var other=foreign.reserve(Unit.SOURCE,"foreign",1)) {
            var before=budget.usage();
            for(Unit unit:List.of(Unit.GENERATION,Unit.LEARNER,Unit.JOURNAL,Unit.CATALOG,Unit.MISC,Unit.CONTROL,Unit.WAITER)) {
                assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(original,20L),
                        List.of(new StorageReservation(unit,"wrong-category",1))));
                assertEquals(before,budget.usage());
            }
            for(var wrong:List.of(generation,other)) {
                assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(wrong,20L),List.of()));
                assertEquals(before,budget.usage());
            }
            assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(original,20L),
                    List.of(new StorageReservation(Unit.SOURCE,"original",1))));
            assertEquals(before,budget.usage());
            var closed=budget.reserve(Unit.SOURCE,"closed",1);closed.close();
            assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(closed,2L),List.of()));
            var excessive=new ArrayList<StorageReservation>();
            for(int i=0;i<14;i++)excessive.add(new StorageReservation(Unit.APPLICATION,"excess-"+i,1));
            assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(),excessive));
            assertEquals(before,budget.usage());assertEquals(1,foreign.usage().staging());
        }
    }

    @Test void handoffRefusalRollsBackCopyGrowthBeforeAnyRelease()throws Exception {
        var helper=new V53FloorFilesTest();helper.temp=temp;
        Path node=temp.resolve("handoff");var local=helper.copy(node,0,1);
        var peer=helper.copy(temp.resolve("handoff-peer"),0,2);var copies=List.of(local,peer);
        var budget=helper.resources();
        try(var owner=helper.open(node,0,budget,event->{if(event.equals("FLOOR_MANIFEST_FORCED"))throw new IOException("cut");})) {
            assertThrows(IOException.class,()->owner.establishFloor(copies,copy->fail("partial copy handed off")));
        }
        var original=V53ReplayFilesTest.files(node);var pressure=new ArrayList<MembershipResources.Lease>();
        try(var owner=helper.open(node,0,budget,event->{})) {
            for(int i=budget.usage().counts().get(Unit.APPLICATION);i<Unit.APPLICATION.count;i++)
                pressure.add(budget.reserve(Unit.APPLICATION,"pressure-"+i,1));
            var before=budget.usage();
            assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,
                    ()->owner.establishFloor(copies,copy->fail("refused copy handed off"))).getMessage());
            assertEquals(original,V53ReplayFilesTest.files(node));assertEquals(before,budget.usage());
        }finally{pressure.forEach(MembershipResources.Lease::close);}
        assertEquals(0,budget.usage().leases());
        var handed=new ArrayList<String>();
        try(var owner=helper.open(node,0,budget,event->{})) {
            owner.establishFloor(copies,copy->handed.add(copy.owner.nodeId().value()));
            assertEquals(List.of("node-2","node-1"),handed);assertTrue(owner.governingFloor().isPresent());
        }
        assertEquals(0,budget.usage().leases());
    }

    @Test void floorCountRefusalRetainsPartialManifest()throws Exception {
        floorRefusal("FLOOR_MANIFEST_FORCED");
    }
    @Test void floorCountRefusalRetainsAlreadyWrittenImage()throws Exception {
        floorRefusal("FLOOR_IMAGE_FORCED");
    }
    private void floorRefusal(String cut)throws Exception {
        var helper=new V53FloorFilesTest();helper.temp=temp;
        Path node=temp.resolve(cut);var local=helper.copy(node,0,1);
        var peer=helper.copy(temp.resolve(cut+"-peer"),0,2);var copies=List.of(local,peer);
        var budget=helper.resources();
        try(var owner=helper.open(node,0,budget,event->{if(event.equals(cut))throw new IOException(cut);})) {
            assertEquals(cut,assertThrows(IOException.class,()->owner.establishFloor(copies)).getMessage());
        }
        assertEquals(0,budget.usage().leases());
        var original=V53ReplayFilesTest.files(node);var pressure=new ArrayList<MembershipResources.Lease>();
        try(var owner=helper.open(node,0,budget,event->{})) {
            assertEquals(1,budget.usage().counts().get(Unit.SOURCE));
            for(int n=1;n<Unit.SOURCE.count;n++)pressure.add(budget.reserve(Unit.SOURCE,"pressure-"+n,1));
            var before=budget.usage();
            assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,
                    ()->owner.establishFloor(copies)).getMessage());
            assertEquals(original,V53ReplayFilesTest.files(node));
            assertEquals(before,budget.usage(),"refusal must retain original floor charges until close");
        }finally{pressure.forEach(MembershipResources.Lease::close);}
        assertEquals(0,budget.usage().leases());
        try(var owner=helper.open(node,0,budget,event->{})) {
            var floor=owner.establishFloor(copies);
            assertArrayEquals(floor.bytes(),owner.governingFloor().orElseThrow().bytes());
        }
        assertEquals(0,budget.usage().leases());
    }

    @Test void retirementStagingRefusalRetainsPartialManifest()throws Exception {
        retirementRefusal("RETIREMENT_MANIFEST_FORCED");
    }
    @Test void retirementStagingRefusalRetainsAlreadyWrittenImage()throws Exception {
        retirementRefusal("RETIREMENT_IMAGE_FORCED");
    }
    private void retirementRefusal(String cut)throws Exception {
        var helper=new V53RetirementTest();helper.temp=temp;Path node=temp.resolve(cut);helper.provision(node);
        var normal=helper.resources();var protectedFiles=helper.protectedFiles(node);
        try(var owner=helper.open(node,normal,event->{if(event.equals(cut))throw new IOException(cut);})) {
            assertEquals(cut,assertThrows(IOException.class,owner::retireInactive).getMessage());
        }
        assertEquals(0,normal.usage().leases());long staging;
        try(var owner=helper.open(node,normal,event->{})) {staging=normal.usage().staging();}
        var bounded=new MembershipResources(staging);var original=V53ReplayFilesTest.files(node);
        try(var owner=helper.open(node,bounded,event->{})) {
            var before=bounded.usage();assertEquals(3,before.counts().get(Unit.SOURCE));
            assertEquals("shared staging capacity",assertThrows(IllegalArgumentException.class,owner::retireInactive).getMessage());
            assertEquals(original,V53ReplayFilesTest.files(node));
            assertEquals(before,bounded.usage(),"refusal must retain original retirement charges until close");
        }
        assertEquals(0,bounded.usage().leases());
        try(var owner=helper.open(node,normal,event->{})) {
            assertTrue(owner.retireInactive().isPresent());assertTrue(owner.retireInactive().isEmpty());
        }
        helper.unchanged(protectedFiles,node);assertFalse(Files.exists(node.resolve("retirement")));
        assertEquals(0,normal.usage().leases());
    }
}
