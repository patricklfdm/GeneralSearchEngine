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
class V53NativeAncestryTest {
    @TempDir Path temp;

    @Test void laggingProposerMustObtainOriginalCompactedAncestryAutomatically()throws Exception {
        runCase(3,false,1);
    }

    @Test void allStableSizesAndBackupsRecoverWithEitherLowerProposerOrLowerFollower()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true))for(int lower:List.of(1,2))
            if(size!=3 || backup || lower!=1)runCase(size,backup,lower);
    }

    @Test void compactedAcceptedTailsSurviveBothDirectionsWithoutBecomingNewVotes()throws Exception {
        runCase(3,false,1,true);runCase(3,true,2,true);
    }
    void runCase(int size,boolean backup,int lower)throws Exception {runCase(size,backup,lower,false);}
    void runCase(int size,boolean backup,int lower,boolean carry)throws Exception {
        Path evidence=Files.createDirectories(Path.of((carry?"target/v53-native-ancestry-tail/run-":"target/v53-native-ancestry/run-")+UUID.randomUUID()));
        System.out.println("v53NativeAncestryEvidence="+evidence.toAbsolutePath());
        Path history=Files.createDirectory(evidence.resolve("history"));
        var fixture=new V53BootstrapPublicationTest.Fixture(history,
                V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),size,backup));
        fixture.ownedHistory=true;
        fixture.campaign(1);fixture.publish(1,false);
        byte[] payload=V53DistinctMinorityTest.payload(fixture,404,"majority-selected");
        var proposedEntry=V53DistinctMinorityTest.entry(fixture,payload,"DATA");
        Files.write(history.resolve("entry-2.gsr"),proposedEntry.bytes());Files.write(history.resolve("payload-2.bin"),payload);
        var publishers=fixture.request.targets().stream().filter(t->!t.identity().nodeId().value().equals("node-"+lower)).toList();
        V53DistinctMinorityTest.publishWithSequence(fixture,2,proposedEntry,payload,publishers,fixture.result.applicationSequence()+1);
        Decoded tail=null;
        if(carry) {
            byte[] nextPayload=V53DistinctMinorityTest.payload(fixture,405,"uncommitted-original");
            tail=V53DistinctMinorityTest.entry(fixture,nextPayload,"DATA");
            Files.write(history.resolve("entry-3.gsr"),tail.bytes());Files.write(history.resolve("payload-3.bin"),nextPayload);
            V53DistinctMinorityTest.vote(fixture,List.of(fixture.request.targets().get(lower==1?1:0)),tail,nextPayload,"tail-accept");
            fixture.snapshot("tail-accepted");
        }
        Files.write(history.resolve("calls.json"),canonical(fixture.calls,8*1024*1024));
        Files.write(history.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(fixture.observations),1024*1024));
        fixture.snapshot("before-network");
        var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();
        var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
        var links=new ArrayList<AtomicReference<MembershipTransport>>();
        var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var events=new TreeMap<String,List<String>>();
        Decoded selected=null;int campaigns=0;Throwable primary=null;
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
                        (peer,request)->{
                            try{return endpoint.handle(peer,request);}
                            catch(java.io.IOException|RuntimeException error){
                                synchronized(wire){try(var log=new java.io.PrintWriter(Files.newBufferedWriter(evidence.resolve("endpoint-errors.log"),StandardOpenOption.CREATE,StandardOpenOption.APPEND))){error.printStackTrace(log);}}
                                throw error;
                            }
                        },(event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(request,response));});
                transports.add(transport);links.get(i).set(transport);
            }
            MembershipSourcePull.Link installationOrder=(peer,request,kind,deadline)->{
                if(lower==1 && size>=4 && request.kind().equals("SELECTED") && peer.nodeId().value().equals("node-2"))
                    assertTrue(events.get("node-3").contains("INSTALL_BEFORE_RETURN"),"longest original must remain available until other selected receivers install");
                return transports.getFirst().exchange(peer,request,kind,deadline);
            };
            try(var driver=new MembershipActivationDriver(owners.getFirst(),endpoints.getFirst(),budgets.getFirst(),bounds(),installationOrder,
                    List.of(),List.of(),temp.resolve("driver-"+UUID.randomUUID()),System::nanoTime,BUDGET,2)) {
                selected=driver.run();campaigns=driver.campaigns();assertEquals(1,campaigns);
                assertEquals(2L,object(selected.value().get("cut")).get("index"));
                assertEquals(3L,object(selected.value().get("ballot")).get("counter"));assertEquals(carry?tail.digest():null,selected.value().get("nextEntry"));
                assertTrue(list(selected.value().get("sources")).stream().anyMatch(s->object(s).get("voter").equals("node-"+lower)));
                for(Object item:list(selected.value().get("sources"))) {
                    String node=(String)object(item).get("voter");int index=Integer.parseInt(node.substring(5))-1;
                    owners.get(index).checkActivation(owners.get(index).originalBasis().orElseThrow(),selected,true);
                    assertEquals(1,events.get(node).stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
                }
            }
        }catch(Exception|Error error){primary=error;throw error;}
        finally {
            Throwable cleanup=null;var close=new ArrayList<AutoCloseable>();close.addAll(endpoints);close.addAll(transports);close.addAll(owners);
            for(var value:close)try{value.close();}catch(Exception|Error error){if(cleanup==null)cleanup=error;else cleanup.addSuppressed(error);}
            Files.write(evidence.resolve("wire.json"),canonical(wire,8*1024*1024));
            Files.write(evidence.resolve("events.json"),canonical(events.entrySet().stream()
                    .map(entry->Map.of("node",entry.getKey(),"events",entry.getValue())).toList(),1024*1024));
            for(var budget:budgets)try{assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
                catch(AssertionError error){if(cleanup==null)cleanup=error;else cleanup.addSuppressed(error);}
            if(cleanup!=null){if(primary!=null)primary.addSuppressed(cleanup);else throw new java.io.IOException("native ancestry cleanup",cleanup);}
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
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema",carry?"gse-v53-native-ancestry-tail-v1":"gse-v53-native-ancestry-v1","status","PASS",
                "size",size,"backup",backup,"lower",lower,"campaigns",campaigns,"historicalObservationsSupplied",false,"network",true,"publicRuntime",false),65536));
    }
}
