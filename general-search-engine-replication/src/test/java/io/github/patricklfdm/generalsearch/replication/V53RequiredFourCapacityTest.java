package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional accounting diagnosis. No new deletion authority or native
 * liveness claim: three retained sources plus four floor copies cannot fit. */
class V53RequiredFourCapacityTest {
    @TempDir Path temp;

    @Test void twoSourcesPermitTheRequiredFourOriginalFloor()throws Exception { check(2); }
    @Test void thirdSourceMakesTheRequiredFourFloorExceedTheFrozenCount()throws Exception { check(3); }

    private void check(int sources)throws Exception {
        var fixture=new V53CurrentGenerationFixture(5,6,false);
        var helper=new V53FloorTest();var copies=new ArrayList<MembershipFloor.Copy>();
        for(int node:List.of(1,2,5,6))copies.add(helper.copy(temp.resolve("node-"+node),5,6,node));
        for(int absent=0;absent<copies.size();absent++) {
            var partial=new ArrayList<>(copies);partial.remove(absent);
            assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(fixture.root(),copies.getFirst(),partial));
        }
        var budget=V53SourceExchangeTest.resources();Path path=temp.resolve("node-1");
        try(var owner=MembershipGrantJournal.openFloors(path,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,event->{})) {
            for(int i=0;i<sources;i++)owner.prepareCurrent(fixture.fixture.source.ballot(20+i));
            assertEquals(sources,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(sources+1,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));
            if(sources==2) {
                owner.establishFloor(copies);
                assertTrue(owner.governingFloor().isPresent());
                assertEquals(6,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(7,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }else {
                var files=V53ReplayFilesTest.files(path);var usage=budget.usage();
                assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,
                        ()->owner.establishFloor(copies)).getMessage());
                assertEquals(files,V53ReplayFilesTest.files(path));assertEquals(usage,budget.usage());
                // A storage failure fences the live owner. Inspect the already
                // captured physical inventory above; do not call a live-only
                // accessor after the deliberately rejected establishment.
                assertEquals("grant journal closed or failed",assertThrows(IllegalArgumentException.class,
                        owner::governingFloor).getMessage());
            }
        }
        assertEquals(0,budget.usage().leases());
    }
}
