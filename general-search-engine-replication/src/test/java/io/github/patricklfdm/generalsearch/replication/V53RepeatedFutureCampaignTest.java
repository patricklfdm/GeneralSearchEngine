package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Native unresolved-election reachability probe; fixed eight rounds exceed the
 * six original-source slots. This is not an arbitrary-duration capacity claim. */
class V53RepeatedFutureCampaignTest {
    @TempDir Path temp;
    @Test void repeatedUnresolvedCampaignsKeepBothOriginalProofsWithOneHolderOffline()throws Exception {
        var helper=new V53SelectedFutureProofTest();helper.temp=Files.createDirectory(temp.resolve("original"));
        var setup=helper.prepared("repeated-campaigns");var f=setup.fixture();
        var survivors=f.request.targets().subList(1,3);var rows=new ArrayList<Map<String,Object>>();boolean success=false;
        System.out.println("v53RepeatedFutureEvidence="+f.raw.toAbsolutePath());
        try {
            var expected=MembershipSelectedRetention.capture(setup.decision(),f.request.targets().getLast().identity(),
                    Files.readAllBytes(f.request.targets().getLast().replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE))).futureObjects();
            assertEquals(2,expected.size());
            V53SelectedFutureContinuationTest.install(f,f.request.targets(),setup.sources(),setup.images());
            f.snapshot("initial-installed");var obsolete=new TreeMap<String,String>();
            for(var t:survivors) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve(MembershipPendingAccept.FILE)));
                obsolete.put(t.identity().nodeId().value(),(String)vote.promise().value().get("basisId"));
                try(var owner=f.open(t,"initial-carried")) {
                    owner.retireSupersededApplication(builder().configuration(),t.materialization());
                    owner.acceptCurrent(vote.entry(),vote.payload());
                }
            }
            V53DistinctMinorityTest.maintain(f,"initial-maintained",survivors,obsolete);
            var offline=V53ReplayFilesTest.files(f.request.targets().getFirst().replicaDirectory());
            var firstCounts=new TreeMap<String,Integer>();
            for(int counter=4;counter<=11;counter++) {
                var installation=V53DistinctMinorityTest.campaign(f,counter,survivors);
                for(var source:installation.sources()) {
                    var frozen=MembershipPeerRetentionSource.read(source);
                    assertEquals(expected.keySet(),frozen.proofs().stream().map(p->hash(p.bytes())).collect(java.util.stream.Collectors.toSet()));
                    for(var proof:frozen.proofs())assertArrayEquals(expected.get(hash(proof.bytes())),proof.bytes());
                }
                for(var t:survivors)try(var owner=f.open(t,"repeat-carried-"+counter)) {
                    var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve(MembershipPendingAccept.FILE)));
                    owner.acceptCurrent(vote.entry(),vote.payload());
                }
                V53DistinctMinorityTest.maintain(f,"round-"+counter+"-maintained",survivors,installation.obsolete());
                for(var t:survivors)try(var owner=f.open(t,"repeat-inspect-"+counter)) {
                    var copy=owner.floorCopyCurrent();var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
                    var retained=MembershipSelectedRetention.find(copy.capsule,selected,t.identity()).orElseThrow();
                    assertEquals(expected.keySet(),retained.futureObjects().keySet());assertTrue(retained.hasPendingFutures());
                    assertEquals(0L,copy.capsule.context.cut.get("index"));
                    for(var row:expected.entrySet())assertArrayEquals(row.getValue(),retained.futureObjects().get(row.getKey()));
                    long sources;
                    try(var paths=Files.list(t.replicaDirectory().resolve("sources"))){sources=paths.filter(Files::isDirectory).count();}
                    assertTrue(sources<=6);
                    var packet=copy.capsule.packet;String node=t.identity().nodeId().value();
                    int count=packet.objectNames().size();
                    if(counter==4)firstCounts.put(node,count);
                    else assertEquals(firstCounts.get(node).intValue(),count,"unchanged unresolved proof graph must not accumulate per-election objects");
                    long intents=packet.objectNames().stream().filter(h->packet.objectSize(h)>=4 && java.nio.ByteBuffer.wrap(packet.objectBytes(h)).getInt()==MembershipSelectedRetention.MAGIC).count();
                    long captures=packet.objectNames().stream().filter(h->packet.objectSize(h)>=4 && java.nio.ByteBuffer.wrap(packet.objectBytes(h)).getInt()==MembershipPeerRetentionSource.MAGIC).count();
                    assertEquals(1,intents,"only this generation's complete merge intent is a live selected object");
                    assertEquals(0,captures,"original capture wrappers stay in their independently owned sources");
                    rows.add(Map.of("counter",counter,"node",t.identity().nodeId().value(),"originalProofs",expected.size(),
                            "sourceDirectories",sources,"packetBytes",copy.capsule.packet.bytes().length,
                            "packetObjects",copy.capsule.packet.objectNames().size(),"selectionBytes",retained.bytes().length));
                }
                assertEquals(offline,V53ReplayFilesTest.files(f.request.targets().getFirst().replicaDirectory()));
                System.out.println("v53RepeatedFutureProgress="+counter+"/11");System.out.flush();
            }
            V53SelectedFutureContinuationTest.carry(f,survivors,Map.of(),false);
            assertEquals(offline,V53ReplayFilesTest.files(f.request.targets().getFirst().replicaDirectory()));
            assertEquals(0,f.resources.usage().leases());success=true;
        }finally {
            V53NativeApplicationTest.save(f);
            Files.write(f.raw.resolve("repeated-campaigns.json"),canonical(Map.of("status",success?"PASS":"FAIL",
                    "rounds",8,"observations",rows,"publicRuntime",false,"arbitraryCapacity",false),65536));
        }
    }
}
