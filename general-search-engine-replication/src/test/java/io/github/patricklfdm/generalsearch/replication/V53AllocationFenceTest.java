package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53AllocationFenceTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("ALLOCATOR_BEFORE_WRITE","ALLOCATOR_CREATED","ALLOCATOR_WRITTEN",
            "ALLOCATOR_FORCED","ALLOCATOR_RENAMED","ALLOCATOR_DIRECTORY_FORCED","ALLOCATOR_BEFORE_RETURN");

    @Test void completedReservationLostToAnObservationBurnsItsCounterWithoutPoisoningTheJournal()throws Exception {
        var fixture=new V53GrantJournalTest();fixture.temp=temp;var source=fixture.source(3,0);
        for(String point:CUTS)for(long observed:List.of(1L,20L)) {
            Path path=fixture.create(point+observed,3);var holder=new MembershipGrantJournal[1];
            try(var journal=fixture.open(path,event->{if(event.equals(point))holder[0].observe(source.context,fixture.ballot(observed));})) {
                holder[0]=journal;
                var lost=assertThrows(MembershipCampaignLost.class,()->MembershipRoundDriver.campaignCall(journal::reserveCounter));
                assertEquals(MembershipCampaignLost.Reason.HIGHER_BALLOT,lost.reason);
                assertInstanceOf(MembershipGrantJournal.HigherBallot.class,lost.getCause());
                assertEquals(1L,decode(java.nio.file.Files.readAllBytes(path.resolve("allocator.gsr")),"records","ALLOCATOR").value().get("counter"));
                assertTrue(journal.promised().isEmpty());assertEquals(0,fixture.bytes(path).length);
                assertEquals(observed+1,journal.reserveCounter());
                assertNotNull(journal.prepare(source,fixture.ballot(observed+1),null));
            }
            try(var reopened=fixture.open(path,3)){assertEquals(observed+2,reopened.reserveCounter());}
        }
    }

    @Test void failedDurabilityStillPoisonsTheOwnerEvenWithAHigherObservation()throws Exception {
        var fixture=new V53GrantJournalTest();fixture.temp=temp;var source=fixture.source(3,0);
        for(String point:CUTS) {
            Path path=fixture.create("failed-"+point,3);var holder=new MembershipGrantJournal[1];
            var injected=new IOException("allocation force interrupted");
            try(var journal=fixture.open(path,event->{if(event.equals(point)) {
                holder[0].observe(source.context,fixture.ballot(20));throw injected;
            }})) {
                holder[0]=journal;
                assertSame(injected,assertThrows(IOException.class,()->MembershipRoundDriver.campaignCall(journal::reserveCounter)));
                assertThrows(IllegalArgumentException.class,journal::reserveCounter);
                assertThrows(IllegalArgumentException.class,journal::promised);
                assertEquals(0,fixture.bytes(path).length);
            }
        }
    }
}
