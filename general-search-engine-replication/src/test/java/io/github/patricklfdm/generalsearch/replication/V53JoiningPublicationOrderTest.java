package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Focused real TCP view switch. Its pre-network SEALED state is a conditional
 * fixture, not a substitute for the complete bootstrap/learner history. */
class V53JoiningPublicationOrderTest {
    @TempDir Path temp;
    @Test void everyTargetIsRecordedBeforeTheFirstJointPublication()throws Exception {
        var helper=new V53TransitionRoundDriverTest();helper.temp=temp;
        try(var n=helper.network("SEALED")) {
            n.transports.get(3).close();n.activate();assertEquals(List.of(0,1,2),n.voters);
            var owner=n.owners.getFirst();var row=object(list(owner.activationContext().catalog.get("results")).getLast());
            var input=V53JoiningIntentExportTest.input(n,"INTENT",Map.of("sealed",
                    V53ContextFixture.map("request",row.get("request"),"prepared",row.get("prepared"),"receipt",row.get("receipt"))));
            n.endpoints.getFirst().maintainInstalled();owner.acceptCurrent(input.entry(),input.payload(),builder().configuration(),n.f.request.targets().getFirst().materialization());
            var certificate=n.apply(owner.voting(n.resources.getFirst()).record("ACCEPT").orElseThrow());
            var recordedAtSend=Collections.synchronizedList(new ArrayList<Long>());
            n.beforeSend.set(request->{if(request.kind().equals("PUBLISH")) {
                synchronized(n.events){recordedAtSend.add(n.events.stream().filter(e->"FUTURE_QUORUM_COMPLETE".equals(e.get("event")) &&
                        certificate.value().get("index").equals(e.get("index"))).count());}
            }});
            n.publish(certificate);
            assertEquals(List.of(2L,2L),recordedAtSend,"both old-majority recordings precede either recipient's new view");
            for(int voter:n.voters) {
                var context=n.owners.get(voter).activationContext();assertNotNull(context.view.get("operation"));
                assertEquals(certificate.value().get("index"),context.cut.get("index"));
            }
            assertTrue(n.failures.isEmpty(),n.failures.toString());
        }
    }
}
