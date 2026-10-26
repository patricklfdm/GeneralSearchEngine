package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.net.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Integration probe for native history through an actual admitted REMOVE chain. */
class V53OwnedCrossViewTest {
    @TempDir Path temp;
    static MembershipBootstrapRequest<Integer,Doc> networkRequest(Path path,int size,boolean backup)throws Exception {
        var original=V53BootstrapPublicationTest.Fixture.request(path,size,backup);
        var sockets=new ArrayList<ServerSocket>();var targets=new ArrayList<MembershipBootstrapTarget<Integer,Doc>>();
        try {
            for(var target:original.targets()) {
                var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));sockets.add(socket);
                var identity=new MembershipIdentity(target.identity().nodeId(),target.identity().storageId(),new ReplicationEndpoint("127.0.0.1",socket.getLocalPort()));
                targets.add(new MembershipBootstrapTarget<>(identity,target.replicaDirectory(),target.materialization()));
            }
        }finally{for(var socket:sockets)socket.close();}
        return new MembershipBootstrapRequest<>(original.groupId(),original.configurationId(),original.source(),original.sourcePath(),targets,
                original.operationDirectory(),original.maxSourceBytes(),original.maxOperationBytes());
    }
    void adoptOverTcp(V53BootstrapPublicationTest.Fixture f,MembershipBootstrapTarget<Integer,Doc> removed,
            MembershipFloor.Copy remote,Map<String,byte[]> expectedImages,int number,Path evidence)throws Exception {
        var source=f.request.targets().getFirst();var budget=resources();var sourceEvents=new ArrayList<String>();var wire=new ArrayList<Map<String,Object>>();
        var sourceBefore=V53ReplayFilesTest.files(source.replicaDirectory());var before=V53ReplayFilesTest.files(removed.replicaDirectory());
        try(var serverOwner=MembershipGrantJournal.openBootstrapped(source.replicaDirectory(),source.materialization().directory(),f.result.root(),source.identity(),budget,MembershipGrantJournal.MAXIMUM,sourceEvents::add);
            var owner=f.open(removed,"removed-adopt-"+number)) {
            sourceEvents.clear();long started=System.nanoTime();
            try(var service=MembershipTransferService.prefix(serverOwner,budget,bounds(),()->{},System::nanoTime,started,BUDGET);
                var server=new MembershipTransport(serverOwner.activationCapsule(),source.identity(),bounds(),budget,
                    (peer,request)->request.kind().equals("STATUS_PROBE")?serverOwner.discoveryStatus(peer,request):service.handle(peer,request),MembershipTransport.Events.NONE);
                var client=new MembershipTransport(owner.activationCapsule(),removed.identity(),bounds(),f.resources,
                    (peer,request)->{throw new AssertionError("removed receiver cannot serve a vote");},MembershipTransport.Events.NONE)) {
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->client.exchange(peer,request,kind,deadline).thenApply(reply->{wire.add(V53SelectedPullTest.wire(request,reply));return reply;});
                MembershipDiscovery.Hint hint;
                try(var discovery=new MembershipDiscovery(owner,f.resources,bounds(),link,()->{},System::nanoTime,started,BUDGET)){hint=discovery.query(source.identity());}
                try(var prefix=MembershipSourcePull.prefix(owner,hint,f.resources,bounds(),link,()->{},System::nanoTime,started,BUDGET);
                    var ancestry=MembershipSourcePull.prefix(owner,hint,f.resources,bounds(),link,()->{},System::nanoTime,started,BUDGET)) {
                    var received=prefix.fetchPrefix(temp.resolve("receive-"+UUID.randomUUID()));
                    Files.write(evidence.resolve("prefix-wire.json"),canonical(wire,4*1024*1024));wire.clear();
                    var verified=ancestry.fetchAncestry(prefix.verifiedPrefix());
                    assertArrayEquals(remote.capsule.packet.bytes(),verified.packet.bytes());
                    for(var entry:expectedImages.entrySet())assertArrayEquals(entry.getValue(),received.images().get(entry.getKey()));
                    assertTrue(ancestry.ancestry().stream().allMatch(b->b.owned.isEmpty()));
                    assertTrue(assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(received.packet(),received.images(),List.of())).getMessage().contains("original historical prefix"));
                    assertTrue(assertThrows(IllegalArgumentException.class,()->owner.fenceMembershipPrefix(received.packet(),received.images(),List.of())).getMessage().contains("original historical prefix"));
                    var changed=new TreeMap<String,byte[]>(received.images());String image=changed.firstKey();byte[] bytes=changed.get(image).clone();bytes[bytes.length-1]^=1;changed.put(image,bytes);
                    assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(verified,changed,ancestry.ancestry()));
                    assertEquals(before,V53ReplayFilesTest.files(removed.replicaDirectory()));
                    var bridges=ancestry.ancestry();assertTrue(bridges.isEmpty());
                    Files.write(evidence.resolve("source.gscp"),received.packet().bytes());for(var entry:received.images().entrySet())Files.write(evidence.resolve(entry.getKey()+".image"),entry.getValue());
                    Files.write(evidence.resolve("manifest.gsr"),ancestry.ancestryManifest().bytes());Files.write(evidence.resolve("ancestry.gsr"),ancestry.ancestryBytes());
                    var manifest=owner.adoptCurrent(verified,received.images(),bridges);
                    assertArrayEquals(manifest.bytes(),owner.adoptCurrent(verified,received.images(),bridges).bytes());
                    assertThrows(IllegalArgumentException.class,prefix::verifiedPrefix); // original view guard is now fenced
                    Files.write(evidence.resolve("adopted.gsr"),manifest.bytes());
                }
            }
            assertTrue(sourceEvents.isEmpty());assertEquals(sourceBefore,V53ReplayFilesTest.files(source.replicaDirectory()));
        }
        assertEquals(0,budget.usage().leases());assertEquals(0,f.resources.usage().leases());
        Files.write(evidence.resolve("ancestry-wire.json"),canonical(wire,4*1024*1024));Files.write(evidence.resolve("source-events.json"),canonical(sourceEvents,65536));
        var stable=V53ReplayFilesTest.files(removed.replicaDirectory());Path log=evidence.resolve("reopened.json");
        Process child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53OwnedAdoptionWorker.class.getName(),removed.replicaDirectory().toString(),removed.materialization().directory().toString()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        V53OwnedGenerationTest.finished(child,0,log);assertEquals(stable,V53ReplayFilesTest.files(removed.replicaDirectory()));
    }
    @Test void nativeOwnersCompleteCertifiedRemovalThenContinueOriginalHistory()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-owned-cross-view/run-"+UUID.randomUUID()));
        System.out.println("v53OwnedCrossViewEvidence="+evidence.toAbsolutePath());Path histories=Files.createDirectory(evidence.resolve("histories")),transfers=Files.createDirectory(evidence.resolve("transfers"));
        var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(5,4))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path raw=Files.createDirectory(histories.resolve(name)),copies=Files.createDirectory(transfers.resolve(name));
            var f=new V53BootstrapPublicationTest.Fixture(raw,networkRequest(Files.createDirectory(temp.resolve(name)),size,backup));f.ownedHistory=true;
            var walk=new V53AdmittedCrossViewTest.Walk(f);
            walk.adoption=(target,remote,images,number)->adoptOverTcp(f,target,remote,images,number,Files.createDirectory(copies.resolve("remove-"+number)));
            try {
            walk.publish("BARRIER",null);for(int number=1;walk.active.size()>3;number++)walk.removeLast(number);
            walk.publish("DATA",V53DistinctMinorityTest.payload(f,707,"after-removal"));walk.publish("BARRIER",null);
            for(var t:walk.active)try(var owner=f.open(t,"inspect-final")) {
                var copy=owner.floorCopyCurrent();assertEquals((long)size-3,copy.capsule.context.view.get("generation"));
                assertEquals(f.result.applicationSequence()+1,copy.capsule.context.catalog.get("applicationSequence"));
                var loaded=MembershipApplicationImage.read(builder().configuration(),t.materialization(),copy.fileBytes(copy.capsule.terminal().application()+".image"),raw.resolve("typed-"+t.identity().nodeId().value()));
                assertEquals(1,loaded.documents().stream().filter(d->d.equals(new Doc(707,"after-removal"))).count());assertEquals(f.result.root().historyId(),loaded.history());
            }
            assertEquals(0,f.resources.usage().leases());rows.add(Map.of("case",name,"status","PASS","slots",walk.slot,"generations",size-3,"peakImages",f.peakImages));
        }finally {
            Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
            Files.write(histories.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-admitted-cross-view-v1","status",rows.size()==4?"PASS":"INCOMPLETE","cases",rows,"publicBootstrap",true,"publicRuntime",false),65536));
            Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-cross-view-v1","status",rows.size()==4?"PASS":"INCOMPLETE", "publicRuntime",false,"profiles",4,"historicalObservationsSupplied",false,"tcpAdoptions",6,"freshProcesses",6),65536));
        }
        }
    }
}
