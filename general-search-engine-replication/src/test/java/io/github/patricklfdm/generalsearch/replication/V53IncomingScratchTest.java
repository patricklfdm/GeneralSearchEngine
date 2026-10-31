package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Incoming maintenance receives use direct source-UUID children, unlike SELECTED. */
class V53IncomingScratchTest {
    @TempDir Path temp;
    V53ScratchTest helper(){var helper=new V53ScratchTest();helper.temp=temp;return helper;}
    Path source(Path scope)throws Exception {
        Path path=Files.createDirectory(scope.resolve("source-"+UUID.randomUUID()));
        Files.write(path.resolve("source.gscp"),new byte[]{1,2,3});
        Files.write(path.resolve(V53ScratchTest.IMAGE),new byte[]{4,5});return path;
    }
    @Test void crashCutMarkerBecomesVisibleOnlyAfterItsCompleteBody()throws Exception {
        Path ready=temp.resolve("cut.ready");var observed=new AtomicBoolean();var expected=Map.of("cut","PARTIAL_IMAGE","mode","kill");
        V53ScratchProcessTest.publishCut(ready,expected,()->{
            observed.set(true);assertFalse(Files.exists(ready),"parent must not observe a partially written cut");
        });
        assertTrue(observed.get());assertEquals(expected,V53ScratchProcessTest.read(ready));
        assertFalse(Files.exists(ready.resolveSibling("cut.ready.pending")));
    }
    @Test void directIncomingCopiesAreChargedAndDiscardedBeforeReopen()throws Exception {
        var helper=helper();
        for(int count:List.of(1,6)) {
            Path scope=helper.initialized("direct-"+count,MembershipScratch.Role.INCOMING);
            for(int n=0;n<count;n++)source(scope);
            var budget=helper.resources();var seen=new AtomicBoolean();
            try(var owner=helper.open(scope,MembershipScratch.Role.INCOMING,budget,event->{
                if(event.equals("RECOVERY_VALIDATED")) {
                    seen.set(true);assertEquals(1+2*count,budget.usage().leases());
                    assertEquals(count+2,MembershipBasisSources.children(scope,8).size());
                }
            })) {
                assertTrue(seen.get());assertEquals(count*3,owner.recovered().size());
                assertEquals(count*5L,owner.recovered().stream().mapToLong(MembershipScratch.Discarded::bytes).sum());
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scope,8));
                assertEquals(1,budget.usage().leases());
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void mixedAndForeignIncomingLayoutsPreserveEveryChild()throws Exception {
        var helper=helper();
        for(String variant:List.of("selected","extra","bad-source","nested","too-many","symlink","hardlink")) {
            Path scope=helper.initialized(variant,MembershipScratch.Role.INCOMING);Path good=source(scope);
            switch(variant) {
                case "selected" -> helper.source(scope,MembershipScratch.Role.INCOMING);
                case "extra" -> Files.writeString(scope.resolve("operator.txt"),"keep");
                case "bad-source" -> Files.createDirectory(scope.resolve("source-invalid"));
                case "nested" -> Files.createDirectory(good.resolve("nested"));
                case "too-many" -> {for(int n=0;n<6;n++)source(scope);}
                case "symlink" -> Files.createSymbolicLink(good.resolve("ef".repeat(32)+".image"),good.resolve(V53ScratchTest.IMAGE));
                case "hardlink" -> Files.createLink(temp.resolve("outside-alias"),good.resolve(V53ScratchTest.IMAGE));
            }
            var budget=helper.resources();var deletion=new AtomicBoolean();
            assertThrows(Exception.class,()->helper.open(scope,MembershipScratch.Role.INCOMING,budget,event->{
                if(event.equals("FILE_REMOVED") || event.equals("DIRECTORY_REMOVED"))deletion.set(true);
            }));
            assertFalse(deletion.get());assertArrayEquals(new byte[]{1,2,3},Files.readAllBytes(good.resolve("source.gscp")));
            assertArrayEquals(new byte[]{4,5},Files.readAllBytes(good.resolve(V53ScratchTest.IMAGE)));assertEquals(0,budget.usage().leases());
        }
    }
    @Test void capacityFailureDoesNotPartiallyDeleteIncomingMaintenance()throws Exception {
        var helper=helper();Path scope=helper.initialized("capacity",MembershipScratch.Role.INCOMING);source(scope);
        var before=V53ReplayFilesTest.files(scope);var budget=helper.resources();var held=new ArrayList<MembershipResources.Lease>();
        try {
            for(int n=0;n<7;n++)held.add(budget.reserve(MembershipResources.Unit.APPLICATION,"held-"+n,1));
            var error=assertThrows(IllegalArgumentException.class,()->helper.open(scope,MembershipScratch.Role.INCOMING,budget,e->{}));
            assertEquals("resource ownership/count",error.getMessage());
            assertEquals(before,V53ReplayFilesTest.files(scope));assertEquals(7,budget.usage().leases());
        }finally{for(var lease:held)lease.close();}
        try(var owner=helper.open(scope,MembershipScratch.Role.INCOMING,budget,e->{})){assertEquals(3,owner.recovered().size());}
        assertEquals(0,budget.usage().leases());
    }
    @Test void eachInterruptedDirectDeletionResumesUnderTheSameOwner()throws Exception {
        var helper=helper();
        for(String cut:V53ScratchProcessTest.CLEANUP) {
            Path scope=helper.initialized(cut,MembershipScratch.Role.INCOMING);source(scope);var budget=helper.resources();var hit=new AtomicBoolean();
            assertThrows(IOException.class,()->helper.open(scope,MembershipScratch.Role.INCOMING,budget,event->{
                if(event.equals(cut) && hit.compareAndSet(false,true))throw new IOException("injected");
            }));
            assertTrue(hit.get());assertEquals(0,budget.usage().leases());
            try(var owner=helper.open(scope,MembershipScratch.Role.INCOMING,budget,e->{})) {
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(owner.directory(),8));
            }
            assertEquals(0,budget.usage().leases());
        }
    }
}
