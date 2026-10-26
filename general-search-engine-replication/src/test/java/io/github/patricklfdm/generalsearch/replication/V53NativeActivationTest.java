package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** A real published native history must activate without supplied old observations. */
class V53NativeActivationTest {
    @TempDir Path temp;

    @Test void threeVoterPublishedHistoryUsesNativeNetworkProof()throws Exception {
        runCase(3,false);
    }
    @Test void everyOtherStableSizeAndBackupUsesTheSameNativeNetworkPath()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true))
            if(size!=3 || backup)runCase(size,backup);
    }

    void runCase(int size,boolean backup)throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-native-activation/run-"+UUID.randomUUID()));
        System.out.println("v53NativeActivationEvidence="+evidence.toAbsolutePath());
        Path history=Files.createDirectory(evidence.resolve("history"));
        var fixture=new V53BootstrapPublicationTest.Fixture(history,
                V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),size,backup));
        fixture.ownedHistory=true;
        fixture.campaign(1);fixture.publish(1,false);fixture.publish(2,true);
        Files.write(history.resolve("calls.json"),canonical(fixture.calls,8*1024*1024));
        Files.write(history.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(fixture.observations),1024*1024));
        fixture.snapshot("before-network");
        var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();
        var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
        var links=new ArrayList<AtomicReference<MembershipTransport>>();
        var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var events=new TreeMap<String,List<String>>();
        Decoded selected=null;int campaigns=0;
        try {
            for(var target:fixture.request.targets()) {
                var budget=resources();budgets.add(budget);var trace=Collections.synchronizedList(new ArrayList<String>());
                events.put(target.identity().nodeId().value(),trace);links.add(new AtomicReference<>());
                owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),
                        fixture.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,trace::add));
            }
            for(int i=0;i<size;i++) {
                int local=i;
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->links.get(local).get().exchange(peer,request,kind,deadline);
                var endpoint=new MembershipActivationEndpoint(owners.get(i),budgets.get(i),bounds(),link,List.of(),List.of(),
                        temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);endpoints.add(endpoint);
                var transport=new MembershipTransport(owners.get(i).activationCapsule(),fixture.request.targets().get(i).identity(),bounds(),budgets.get(i),
                        endpoint,(event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(request,response));});
                transports.add(transport);links.get(i).set(transport);
            }
            try(var driver=new MembershipActivationDriver(owners.getFirst(),endpoints.getFirst(),budgets.getFirst(),bounds(),transports.getFirst()::exchange,
                    List.of(),List.of(),temp.resolve("driver-"+UUID.randomUUID()),System::nanoTime,BUDGET,2)) {
                selected=driver.run();campaigns=driver.campaigns();assertEquals(1,campaigns);
                assertEquals(2L,object(selected.value().get("cut")).get("index"));
                assertEquals(3L,object(selected.value().get("ballot")).get("counter"));assertNull(selected.value().get("nextEntry"));
                for(Object item:list(selected.value().get("sources"))) {
                    String node=(String)object(item).get("voter");int index=Integer.parseInt(node.substring(5))-1;
                    owners.get(index).checkActivation(owners.get(index).originalBasis().orElseThrow(),selected,true);
                    assertEquals(1,events.get(node).stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
                }
            }
        }finally {
            for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();for(var owner:owners)owner.close();
            Files.write(evidence.resolve("wire.json"),canonical(wire,8*1024*1024));
            Files.write(evidence.resolve("events.json"),canonical(events.entrySet().stream()
                    .map(entry->Map.of("node",entry.getKey(),"events",entry.getValue())).toList(),1024*1024));
            for(var budget:budgets){assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
        }
        assertNotNull(selected);Files.write(evidence.resolve("selected.gsr"),selected.bytes());fixture.snapshot("after-network");
        int previousCalls=fixture.calls.size();
        for(var target:fixture.request.targets())try(var owner=fixture.open(target,"native-final")) {
            assertEquals(2L,owner.activationCapsule().context.cut.get("index"));
            assertEquals(fixture.result.applicationSequence()+1,owner.activationCapsule().context.catalog.get("applicationSequence"));
        }
        Files.write(evidence.resolve("native-final.json"),canonical(fixture.calls.subList(previousCalls,fixture.calls.size()),1024*1024));
        fixture.snapshot("after-reopen");
        assertEquals(0,fixture.resources.usage().leases());
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-native-activation-v1","status","PASS",
                "size",size,"backup",backup,"campaigns",campaigns,"historicalObservationsSupplied",false,"network",true,"publicRuntime",false),65536));
    }
}
