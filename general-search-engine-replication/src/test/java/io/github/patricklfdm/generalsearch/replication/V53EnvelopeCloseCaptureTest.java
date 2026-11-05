package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Real journal close/lock observations; the Python reader qualifies their intervals. */
class V53EnvelopeCloseCaptureTest {
    @TempDir Path temp;
    final class Fixture {
        final Path raw=Files.createDirectory(temp.resolve("raw"));
        final V53BootstrapPublicationTest.Fixture bootstrap=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("seed")),raw,3,false);
        final V53EnvelopeResourceCapture capture=new V53EnvelopeResourceCapture(raw,bootstrap.result.root().manifestDigest());
        final MembershipResources budget=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
        final String scope=capture.register("node-1","",budget);
        Fixture()throws Exception {}
        V53EnvelopeResourceCapture.Opened open()throws Exception {
            var target=bootstrap.request.targets().getFirst();Path replica=target.replicaDirectory();
            capture.event(scope,"OWNER_OPEN_BEGIN",replica);
            var journal=MembershipGrantJournal.openBootstrapped(replica,target.materialization().directory(),bootstrap.result.root(),
                    target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->capture.event(scope,event,replica));
            capture.event(scope,"OWNER_OPEN_RETURNED",replica);
            return new V53EnvelopeResourceCapture.Opened(journal,capture,scope,replica);
        }
        List<String> events()throws Exception {
            return list(parse(Files.readAllBytes(raw.resolve("completion-resources/events.json")),1024*1024)).stream()
                .map(v->(String)object(v).get("event")).toList();
        }
    }
    @Test void exceptionInBodyStillClosesOriginalAndReleasesExclusiveLock()throws Exception {
        var f=new Fixture();var opened=f.open();long before=f.budget.observationCheckpoint().sequence();
        assertThrows(IllegalStateException.class,()->{try(opened){throw new IllegalStateException("body failed");}});
        assertEquals(0,f.budget.usage().leases());assertTrue(f.budget.observationCheckpoint().sequence()>before);
        f.capture.save();var events=f.events();assertEquals(List.of("RESOURCE_OWNER_CLOSE_BEGIN","RESOURCE_OWNER_CLOSE_RETURNED"),events.subList(events.size()-2,events.size()));
        var target=f.bootstrap.request.targets().getFirst();
        try(var reopened=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.bootstrap.result.root(),
                target.identity(),new MembershipResources(512*MIB),MembershipGrantJournal.MAXIMUM,event->{})) {
            assertEquals(target.identity(),reopened.activationIdentity());
        }
    }
    @Test void previouslyClosedJournalCannotForgeASecondObservedLifetime()throws Exception {
        var f=new Fixture();var opened=f.open();opened.journal().close();
        assertThrows(Exception.class,opened::close);f.capture.save();
        assertTrue(f.events().stream().noneMatch(v->v.startsWith("RESOURCE_OWNER_CLOSE")));
    }
    @Test void wrongOriginalScopeCannotCloseTheCurrentOwner()throws Exception {
        var f=new Fixture();var opened=f.open();var target=f.bootstrap.request.targets().getFirst();
        try(opened) {
            assertThrows(IllegalArgumentException.class,()->f.capture.closeOwner("open-9999",target.replicaDirectory(),opened.journal()));
            assertEquals(target.identity(),opened.journal().activationIdentity());assertTrue(f.budget.usage().leases()>0);
        }
        f.capture.save();assertEquals(1,f.events().stream().filter(v->v.equals("RESOURCE_OWNER_CLOSE_BEGIN")).count());
        assertEquals(1,f.events().stream().filter(v->v.equals("RESOURCE_OWNER_CLOSE_RETURNED")).count());
    }
}
