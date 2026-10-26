package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Complete authenticated originals, then a real governing floor, from published native owners. */
class V53GenerationCopyNetworkTest {
 @TempDir Path temp;
 @Test void exactCopiesFromActualQuorumsAtEveryInitialSizeAndSource()throws Exception {
  Path evidence=Files.createDirectories(Path.of("target/v53-generation-copy/run-"+UUID.randomUUID()));
  System.out.println("v53GenerationCopyEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
  for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
   String name="size-"+size+"-"+(backup?"backup":"empty");Path root=Files.createDirectory(evidence.resolve(name)),raw=Files.createDirectory(root.resolve("history"));
   var f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve(name)),size,backup));f.ownedHistory=true;
   var copies=new ArrayList<MembershipFloor.Copy>();var wire=new TreeMap<String,List<Map<String,Object>>>();var events=new ArrayList<String>();var budget=resources();
   try {
    f.campaign(1);f.publish(1,false);f.publish(2,true);var target=f.request.targets().getFirst();
    try(var local=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,events::add)) {
     long started=System.nanoTime();events.clear();
     try(var client=new MembershipTransport(local.activationCapsule(),target.identity(),bounds(),budget,(peer,r)->{throw new AssertionError("copy does not vote");},MembershipTransport.Events.NONE)) {
      for(int i=1;i<=size/2;i++) {
       var source=f.request.targets().get(i);var sourceBudget=resources();var exchanges=new ArrayList<Map<String,Object>>();wire.put(source.identity().nodeId().value(),exchanges);
       var before=V53ReplayFilesTest.files(source.replicaDirectory());
       try(var remote=MembershipGrantJournal.openBootstrapped(source.replicaDirectory(),source.materialization().directory(),f.result.root(),source.identity(),sourceBudget,MembershipGrantJournal.MAXIMUM,e->{});
           var service=MembershipTransferService.prefix(remote,sourceBudget,bounds(),()->{},System::nanoTime,started,BUDGET);
           var server=new MembershipTransport(remote.activationCapsule(),source.identity(),bounds(),sourceBudget,service,MembershipTransport.Events.NONE)) {
        var hint=new MembershipDiscovery.Hint(source.identity(),remote.activationContext().cut,false);
        MembershipSourcePull.Link link=(peer,r,kind,deadline)->client.exchange(peer,r,kind,deadline).thenApply(reply->{exchanges.add(V53SelectedPullTest.wire(r,reply));return reply;});
        try(var prefix=MembershipSourcePull.prefix(local,hint,budget,bounds(),link,()->{},System::nanoTime,started,BUDGET);
            var generation=MembershipSourcePull.prefix(local,hint,budget,bounds(),link,()->{},System::nanoTime,started,BUDGET)) {
         prefix.fetchPrefix(temp.resolve("receive-"+UUID.randomUUID()));var copied=generation.fetchGeneration(prefix);var original=remote.floorCopyCurrent();
         assertArrayEquals(original.generation.bytes(),copied.generation.bytes());assertEquals(original.fileNames(),copied.fileNames());
         Path saved=Files.createDirectories(root.resolve("copied").resolve(source.identity().nodeId().value()));
         for(String file:copied.fileNames()){assertArrayEquals(original.fileBytes(file),copied.fileBytes(file),file);Files.write(saved.resolve(file),copied.fileBytes(file));}
         copies.add(copied);
        }
       }
       assertEquals(0,sourceBudget.usage().leases());assertEquals(before,V53ReplayFilesTest.files(source.replicaDirectory()));
      }
     }
     assertTrue(events.isEmpty());copies.addFirst(local.floorCopyCurrent());
     // Probe pure admission before starting the storage transaction: a failed
     // storage mutation deliberately fences that journal until reopen.
     if(size>3)assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.result.root(),copies.getFirst(),copies.subList(0,2)));
     events.clear();var floor=local.establishFloor(copies);Files.write(root.resolve("floor.gsr"),floor.bytes());f.snapshot("network-floor");
     local.releaseFloor();f.snapshot("network-floor-released");
    }
    assertEquals(0,budget.usage().leases());cases.add(Map.of("case",name,"status","PASS","voters",size,"backup",backup,"copies",size/2+1,"exchanges",wire.values().stream().mapToInt(List::size).sum()));
   }finally {
    Files.write(root.resolve("wire.json"),canonical(wire.entrySet().stream().map(row->Map.of("node",row.getKey(),"exchanges",row.getValue())).toList(),8*1024*1024));Files.write(root.resolve("events.json"),canonical(events,65536));
    Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
    Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-generation-copy-v1","status",cases.size()==6?"PASS":"INCOMPLETE","cases",cases,"publicRuntime",false,"publicBootstrap",true,"historicalObservationsSupplied",false),65536));
   }
  }
 }
}
