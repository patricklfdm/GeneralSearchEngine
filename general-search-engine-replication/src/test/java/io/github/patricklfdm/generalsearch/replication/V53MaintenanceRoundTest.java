package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Complete TCP publications; refreshing never retries an accepted DATA entry. */
class V53MaintenanceRoundTest {
    @TempDir Path temp;
    @Test void failedFreshInstallationCannotAcceptOrReplayTheWaitingCommand()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var network=new V53NativeDispatchTest();network.temp=temp;long lifetime=TimeUnit.MINUTES.toNanos(12);
        var entries=new ArrayList<Decoded>();var selections=new ArrayList<Decoded>();
        try(var n=network.new Network(3,helper.controlBounds(),lifetime,f->{});
            var round=helper.driver(n,(event,record)->{
                if(event.equals("SLOT_BEGIN"))entries.add(record);
                if(event.equals("INSTALLED")) {
                    selections.add(record);
                    if(selections.size()==2)throw new java.io.IOException("injected refresh installation failure");
                }
            },lifetime)) {
            n.transports.get(2).close();round.start();round.submit("DATA",helper.data(n));
            var failure=assertThrows(java.io.IOException.class,()->round.submit("BARRIER",new byte[0]));
            assertEquals("injected refresh installation failure",failure.getMessage());
            assertEquals(2,selections.size());assertEquals(List.of("BARRIER","DATA"),entries.stream().map(e->e.value().get("kind")).toList());
            assertEquals(2L,number(n.owners.getFirst().activationContext().cut.get("index")));
            assertEquals(MembershipRoundDriver.State.FAILED,round.state());assertThrows(IllegalArgumentException.class,round::readiness);
            Files.write(n.f.raw.resolve("maintenance-refresh-failure.json"),canonical(Map.of("status","PASS","fault","installation",
                    "newCommandAccepted",false,"clientReplayed",false,"campaigns",2L),8192));
        }
    }
    @Test void continuousCommandsReconcileBeforeAcceptAndKeepOriginalDeadline()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var network=new V53NativeDispatchTest();network.temp=temp;long lifetime=TimeUnit.MINUTES.toNanos(12);
        var entries=new ArrayList<Decoded>();var selections=new ArrayList<Decoded>();var ready=new ArrayList<Decoded>();
        try(var n=network.new Network(3,helper.controlBounds(),lifetime,f->{});
            var round=helper.driver(n,(event,record)->{
                if(event.equals("SLOT_BEGIN"))entries.add(record);
                if(event.equals("INSTALLED"))selections.add(record);
                if(event.equals("BEFORE_READY"))ready.add(record);
            },lifetime)) {
            n.transports.get(2).close();round.start();
            for(int id=100;id<=102;id++) {
                byte[] payload;
                try(var encoder=new ReplicaApplication<>(builder().configuration(),n.f.request.targets().getFirst().materialization(),n.bounds)) {
                    payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(id,"maintenance-"+id))));
                }
                round.submit("DATA",payload);
                assertEquals(MembershipRoundDriver.State.READY,round.state());round.readiness();
            }
            assertEquals(List.of("BARRIER","DATA","BARRIER","DATA","BARRIER","DATA"),entries.stream().map(e->e.value().get("kind")).toList());
            assertEquals(List.of(1L,2L,3L,4L,5L,6L),entries.stream().map(e->e.value().get("index")).toList());
            assertEquals(3,selections.size());assertEquals(3,ready.size());
            for(int i=0;i<3;i++) {
                var ballot=object(selections.get(i).value().get("ballot"));
                assertEquals(2L+i,number(ballot.get("counter")));
                assertEquals(ballot,entries.get(i*2).value().get("origin"));
                assertEquals(ballot,entries.get(i*2+1).value().get("origin"));
            }
            assertArrayEquals(ready.getLast().bytes(),round.readiness().bytes());
            for(int voter:n.voters) {
                var context=n.owners.get(voter).activationContext();
                assertEquals(6L,number(context.cut.get("index")));
                assertEquals(n.f.result.applicationSequence()+3,number(context.catalog.get("applicationSequence")));
            }
            // All refreshes share the original invocation lifetime; no new slot
            // can start after that deadline, even though readiness was renewed.
            n.offset.set(lifetime);int count=entries.size();
            assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[0]));
            assertEquals(count,entries.size());assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            Files.write(n.f.raw.resolve("maintenance-round-result.json"),canonical(Map.of("status","PASS","campaigns",3L,
                    "data",3L,"barriers",3L,"originalDeadlineRefused",true,"publicRuntime",false),8192));
        }
    }
}
