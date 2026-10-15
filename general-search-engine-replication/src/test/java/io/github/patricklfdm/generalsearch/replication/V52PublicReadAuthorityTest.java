package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V52PublicReadTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.NOT_APPLICABLE;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import java.io.IOException;
import java.net.Socket;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BooleanSupplier;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.params.provider.CsvSource;

/** Public bootstrap/read/mutation calls with real TCP. Hooks only delay/drop actual exchanges. */
class V52PublicReadAuthorityTest {
    @TempDir Path root;
    @AfterEach void reset(){AutomaticRuntimeHooks.CURRENT.remove();}
    // Deliberately bounded fault-fixture exchanges, not a production or measurement change.
    static final ReplicationBounds LIMITS=ReplicaLeaderTestSupport.bounds(1200,8);
    static final AutomaticLeadershipPolicy TIMING=new AutomaticLeadershipPolicy(1200,3600,6000,60000);
    interface Network {void at(String node,String barrier,Map<String,Object> request,Map<String,Object> response) throws IOException;}
    interface Events {void at(String node,String event,Map<String,Object> value);}
    static void until(BooleanSupplier condition,String message) throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        while(!condition.getAsBoolean()&&System.nanoTime()<end)Thread.sleep(5);
        assertTrue(condition.getAsBoolean(),message);
    }
    static void hold(CountDownLatch release) throws IOException {
        try {if(!release.await(25,TimeUnit.SECONDS))throw new IOException("qualification barrier not released");}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
    }
    final class Group implements AutoCloseable {
        final List<AutomaticReplicationGroupConfig<Integer,Doc>> configs;
        final List<AutomaticReplicatedSearchEngine<Integer,Doc>> engines=new ArrayList<>();
        final Map<String,Long> floors=new ConcurrentHashMap<>();
        volatile Network network=(n,b,q,r)->{};
        volatile Events events=(n,e,v)->{};
        Group() throws Exception {
            configs=V51PublicRuntimeTest.configs(root).stream().map(c->new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),
                    c.members(),c.replicaDirectory(),c.materialization(),LIMITS,TIMING)).toList();
            var request=new AutomaticReplicationBootstrapRequest<Integer,Doc>(ReplicationBootstrapSource.EMPTY,null,configs,root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(rich(),request,AutomaticReplicationStorageOperations.planBootstrap(rich(),request));
            for(var c:configs)engines.add(AutomaticReplicatedSearchEngines.builder(rich(),c).build());
        }
        void start(int count) throws Exception {
            for(int i=0;i<count;i++) {
                String node=configs.get(i).localNodeId().value();
                AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(AutomaticStore.Faults.NONE,
                        (b,q,r)->network.at(node,b,q,r),(e,v)->{
                            if(e.equals("RECOVERY_FLOOR"))floors.merge(node,number(v,"index"),Math::max);
                            events.at(node,e,v);
                        }));
                engines.get(i).start().get(15,TimeUnit.SECONDS);
            }
            AutomaticRuntimeHooks.CURRENT.remove();
        }
        String name(AutomaticReplicatedSearchEngine<Integer,Doc> engine){return engine.leadershipStatus().localNodeId().value();}
        AutomaticReplicatedSearchEngine<Integer,Doc> node(String name){return engines.stream().filter(e->name(e).equals(name)).findFirst().orElseThrow();}
        AutomaticReplicatedSearchEngine<Integer,Doc> leader(String except) throws Exception {
            until(()->engines.stream().anyMatch(e->!name(e).equals(except)&&e.leadershipStatus().state()==LEADER_READY),"no public leader");
            return engines.stream().filter(e->!name(e).equals(except)&&e.leadershipStatus().state()==LEADER_READY).findFirst().orElseThrow();
        }
        ReplicaReadToken baseline(AutomaticReplicatedSearchEngine<Integer,Doc> leader) throws Exception {
            leader.add(new Doc(1,"committed before fault")).get(10,TimeUnit.SECONDS);
            var token=leader.read(STRONG,v->v.get(1)).get(10,TimeUnit.SECONDS).progress();
            until(()->configs.stream().allMatch(c->floors.getOrDefault(c.localNodeId().value(),-1L)>=token.index()),"baseline source retirement incomplete");
            return token;
        }
        @Override public void close(){for(var engine:engines)engine.close();}
    }

    @Test void forcedAcceptanceWithoutProofCannotSatisfyEitherLocalPolicy() throws Exception {
        var reached=new CountDownLatch(1);var release=new CountDownLatch(1);var peer=new AtomicReference<String>();
        var acceptance=new AtomicReference<Map<String,Object>>();var armed=new AtomicBoolean();
        try(var group=new Group()) {
            group.network=(node,barrier,request,response)->{
                if(barrier.equals("AFTER_RESPONSE_READ")&&request.get("type").equals("ACCEPT")&&armed.compareAndSet(true,false)) {
                    assertEquals("ACCEPT_ACK",response.get("type"));peer.set(text(request,"recipient"));
                    acceptance.set(object(request.get("payload")));reached.countDown();hold(release);
                }
            };
            group.start(3);var leader=group.leader("");var token=group.baseline(leader);armed.set(true);
            var write=leader.add(new Doc(2,"accepted but not yet proven"));
            try {
                await(reached);var follower=group.node(peer.get());
                var accepted=decode(unbase(acceptance.get().get("acceptance")),"ACCEPT");
                var entry=decode(unbase(accepted.value().get("entry")),"ENTRY");assertEquals(token.index()+1,number(entry.value(),"index"));
                assertEquals(token.index(),follower.leadershipStatus().provenIndex());assertFalse(write.isDone());
                for(var options:List.of(STALE,minimum(token,0))) {
                    var read=follower.read(options,v->{assertNull(v.get(2));return v.get(1);}).get(5,TimeUnit.SECONDS);
                    assertEquals(token,read.progress());assertEquals(new Doc(1,"committed before fault"),read.value());assertEquals(1,read.applicationSequence());
                }
                var ahead=index(token,token.index()+1);
                readReason(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,follower.read(minimum(ahead,0),v->fail("accepted-only zero wait")));
                rejected(DEADLINE_EXCEEDED,NOT_APPLICABLE,()->follower.read(minimum(ahead,100),v->fail("accepted-only positive wait")).join());
                assertEquals(token.index(),follower.leadershipStatus().appliedIndex());
            } finally {release.countDown();}
            write.get(10,TimeUnit.SECONDS);
            var published=group.node(peer.get()).read(minimum(index(token,token.index()+1),5000),v->v.get(2)).get(10,TimeUnit.SECONDS);
            assertEquals(new Doc(2,"accepted but not yet proven"),published.value());assertEquals(2,published.applicationSequence());
        } finally {release.countDown();}
    }

    @ParameterizedTest @ValueSource(booleans={false,true})
    void isolatedOldLeaderHasLocalCoverageButCandidateRejectsNewCaptures(boolean minimumPolicy) throws Exception {
        var isolated=new AtomicReference<String>();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var group=new Group()) {
            group.network=(node,barrier,request,response)->{
                String old=isolated.get();
                if(old!=null&&(barrier.equals("BEFORE_REQUEST_WRITE")||barrier.equals("AFTER_REQUEST_READ"))&&
                        (old.equals(request.get("sender"))||old.equals(request.get("recipient"))))throw new IOException("qualification partition");
            };
            group.start(3);var old=group.leader("");var token=group.baseline(old);isolated.set(group.name(old));
            rejected(QUORUM_UNAVAILABLE,NOT_APPLICABLE,()->old.read(STRONG,v->fail("isolated strong callback")).join());
            assertEquals(UNAVAILABLE,old.leadershipStatus().state());
            for(var options:List.of(STALE,minimum(token,0)))assertEquals(token,old.read(options,v->v.get(1)).get(5,TimeUnit.SECONDS).progress());
            readReason(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,old.read(minimum(index(token,token.index()+1),0),v->fail("isolated future minimum")));
            var captured=old.read(minimumPolicy?minimum(token,0):STALE,v->{
                var before=v.get(1);entered.countDown();try {hold(release);}catch(IOException e){throw new java.io.UncheckedIOException(e);}
                assertEquals(before,v.get(1));assertNull(v.get(2));return before;
            });
            try {
                await(entered);
                var queued=old.read(STALE,v->fail("queued local read captured after candidacy"));
                var queuedMinimum=old.read(minimum(token,0),v->fail("queued minimum captured after candidacy"));
                until(()->old.leadershipStatus().state()==CANDIDATE,"isolated reader did not enter candidate state");
                rejected(NOT_READY,NOT_APPLICABLE,queued::join);rejected(NOT_READY,NOT_APPLICABLE,queuedMinimum::join);
                for(var options:List.of(STRONG,STALE,minimum(token,0)))
                    rejected(NOT_READY,NOT_APPLICABLE,()->old.read(options,v->fail("candidate captured new read")).join());
                var successor=group.leader(group.name(old));successor.add(new Doc(2,"surviving majority")).get(10,TimeUnit.SECONDS);
                assertFalse(captured.isDone());
            } finally {release.countDown();}
            var result=captured.get(5,TimeUnit.SECONDS);assertEquals(token,result.progress());assertEquals(1,result.applicationSequence());
            assertEquals(new Doc(1,"committed before fault"),result.value());
        } finally {isolated.set(null);release.countDown();}
    }

    @Test void confirmedBulkThenStrongTokenWaitsForTheLaggingFollowersActualPublication() throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var heldPeer=new AtomicReference<String>();
        var pairs=new ConcurrentHashMap<String,Set<String>>();var waitingId=new AtomicLong(-1);var admitted=new AtomicReference<Map<String,Object>>();
        try(var group=new Group()) {
            group.events=(node,event,value)->{
                if(event.equals("PROMISE_QUORUM")) {
                    var selected=decode(unbase(value.get("selected")),"SELECTED");var members=new HashSet<String>();
                    for(var basis:list(selected.value().get("bases")))members.add(text(object(basis),"node"));pairs.put(node,Set.copyOf(members));
                }
                if(node.equals(heldPeer.get())&&event.equals("REPLICA_READ_INVOKED")&&value.get("policy").equals("AT_LEAST_INDEX"))waitingId.set(number(value,"readId"));
                if(node.equals(heldPeer.get())&&event.equals("REPLICA_READ_ADMITTED")&&number(value,"readId")==waitingId.get())admitted.set(Map.copyOf(value));
            };
            // This schedule isolates ordinary proof publication from the separate
            // snapshot-install state gate, already qualified above and in process cases.
            group.network=(node,barrier,request,response)->{
                if(barrier.equals("BEFORE_REQUEST_WRITE")&&request.get("recipient").equals(heldPeer.get())&&request.get("type").equals("SNAPSHOT_OFFER"))
                    throw new IOException("hold snapshot fallback during ordinary publication test");
            };
            group.start(3);var leader=group.leader("");var original=group.baseline(leader);
            String peer=pairs.get(group.name(leader)).stream().filter(n->!n.equals(group.name(leader))).findFirst().orElseThrow();
            var follower=group.node(peer);heldPeer.set(peer);
            var held=follower.read(STALE,v->{entered.countDown();try {hold(release);}catch(IOException e){throw new java.io.UncheckedIOException(e);}
                assertNull(v.get(80));assertNull(v.get(81));return v.get(1);});
            CompletableFuture<ReplicaReadResult<List<Doc>>> waiting;ReplicaReadToken carried;
            var bulk=List.of(new Doc(80,"complete bulk a"),new Doc(81,"complete bulk b"));
            try {
                await(entered);leader.addAll(bulk).get(10,TimeUnit.SECONDS);
                carried=leader.read(STRONG,v->{assertEquals(bulk,List.of(v.get(80),v.get(81)));return null;}).get(10,TimeUnit.SECONDS).progress();
                assertTrue(carried.index()>original.index());assertEquals(original.index(),follower.leadershipStatus().appliedIndex());
                waiting=follower.read(minimum(carried,5000),v->List.of(v.get(80),v.get(81)));
                until(()->admitted.get()!=null,"minimum did not register while publication was held");
                assertFalse(waiting.isDone());assertEquals(1,number(admitted.get(),"waiting"));assertEquals(1,number(admitted.get(),"captured"));
                assertEquals(1,number(admitted.get(),"alarms"));
            } finally {release.countDown();}
            assertEquals(original,held.get(5,TimeUnit.SECONDS).progress());
            var read=waiting.get(10,TimeUnit.SECONDS);assertTrue(read.progress().index()>=carried.index());assertEquals(bulk,read.value());
            assertEquals(2,read.applicationSequence());idle(follower);
        } finally {heldPeer.set(null);release.countDown();}
    }

    @ParameterizedTest @ValueSource(booleans={false,true})
    void verifiedSnapshotRecoveryRejectsQueuedReadsButPreservesAnAlreadyCapturedCut(boolean minimumPolicy) throws Exception {
        var isolated=new AtomicReference<String>();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var pairs=new ConcurrentHashMap<String,Set<String>>();var installed=new ConcurrentHashMap<String,Long>();
        try(var group=new Group()) {
            group.events=(node,event,value)->{
                if(event.equals("PROMISE_QUORUM")) {
                    var selected=decode(unbase(value.get("selected")),"SELECTED");var members=new HashSet<String>();
                    for(var basis:list(selected.value().get("bases")))members.add(text(object(basis),"node"));
                    pairs.put(node,Set.copyOf(members));
                }
                if(event.equals("REJOIN_INSTALLED")) {
                    var snapshot=decode(unbase(value.get("snapshot")),"SNAPSHOT");
                    installed.put(node,(long)list(snapshot.value().get("anchors")).size());
                }
            };
            group.network=(node,barrier,request,response)->{
                String excluded=isolated.get();
                if(excluded!=null&&(barrier.equals("BEFORE_REQUEST_WRITE")||barrier.equals("AFTER_REQUEST_READ"))&&
                        (excluded.equals(request.get("sender"))||excluded.equals(request.get("recipient"))))throw new IOException("qualification partition");
            };
            group.start(3);var leader=group.leader("");var token=group.baseline(leader);
            String peer=group.configs.stream().map(c->c.localNodeId().value()).filter(n->!pairs.get(group.name(leader)).contains(n)).findFirst().orElseThrow();
            var follower=group.node(peer);
            var captured=follower.read(minimumPolicy?minimum(token,0):STALE,v->{
                var before=v.get(1);entered.countDown();try {hold(release);}catch(IOException e){throw new java.io.UncheckedIOException(e);}
                assertEquals(before,v.get(1));assertNull(v.get(2));return before;
            });
            ReplicaReadToken later;
            try {
                await(entered);isolated.set(peer);
                var queued=follower.read(STALE,v->fail("queued read captured during snapshot recovery"));
                var queuedMinimum=follower.read(minimum(token,0),v->fail("queued minimum captured during snapshot recovery"));
                leader.add(new Doc(2,"new snapshot publication")).get(10,TimeUnit.SECONDS);
                later=leader.read(STALE,v->v.get(2)).get(5,TimeUnit.SECONDS).progress();
                until(()->group.floors.getOrDefault(group.name(leader),-1L)>=later.index(),"new snapshot source unavailable");
                isolated.set(null);
                until(()->installed.getOrDefault(peer,-1L)>=later.index()&&follower.leadershipStatus().state()==RECOVERING,"verified install did not enter recovering state");
                rejected(NOT_READY,NOT_APPLICABLE,queued::join);rejected(NOT_READY,NOT_APPLICABLE,queuedMinimum::join);
                for(var options:List.of(STALE,minimum(token,0)))
                    rejected(NOT_READY,NOT_APPLICABLE,()->follower.read(options,v->fail("new capture during recovery")).join());
                assertFalse(captured.isDone());
            } finally {isolated.set(null);release.countDown();}
            var result=captured.get(5,TimeUnit.SECONDS);assertEquals(token,result.progress());assertEquals(1,result.applicationSequence());
            until(()->follower.leadershipStatus().state()==FOLLOWER&&follower.leadershipStatus().appliedIndex()>=later.index(),"snapshot did not publish after release");
            var recovered=follower.read(minimum(later,0),v->v.get(2)).get(5,TimeUnit.SECONDS);
            assertEquals(new Doc(2,"new snapshot publication"),recovered.value());assertEquals(2,recovered.applicationSequence());
        } finally {isolated.set(null);release.countDown();}
    }

    @ParameterizedTest @CsvSource({"false,false","false,true","true,false","true,true"})
    void higherPromisePreservesTheVerifiedLocalCutBeforeAndAfterCapture(boolean afterCapture,boolean minimumPolicy) throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var armed=new AtomicBoolean();
        try(var group=new Group()) {
            group.events=(node,event,value)->{
                if(event.equals(afterCapture?"REPLICA_READ_CAPTURED":"REPLICA_READ_BEFORE_DISPATCH")&&armed.compareAndSet(true,false)) {
                    entered.countDown();try {hold(release);}catch(IOException e){throw new java.io.UncheckedIOException(e);}
                }
            };
            group.start(1);var follower=group.engines.getFirst();var token=follower.read(STALE,v->v.currentSequence()).get(5,TimeUnit.SECONDS).progress();
            armed.set(true);var reading=follower.read(minimumPolicy?minimum(token,0):STALE,v->{assertNull(v.get(1));return v.currentSequence();});
            try {
                await(entered);long epoch=follower.leadershipStatus().promisedEpoch();
                higherPrepare(group.configs.getFirst(),epoch);
                assertTrue(follower.leadershipStatus().promisedEpoch()>epoch);assertEquals(FOLLOWER,follower.leadershipStatus().state());
            } finally {release.countDown();}
            var result=reading.get(5,TimeUnit.SECONDS);assertEquals(token,result.progress());assertEquals(0,result.value());
        } finally {release.countDown();}
    }

    static void higherPrepare(AutomaticReplicationGroupConfig<Integer,Doc> config,long previousEpoch) throws Exception {
        var manifest=decode(Files.readAllBytes(config.replicaDirectory().resolve("manifest.gsr")),"MANIFEST");
        String local=config.localNodeId().value(),peer=nodes(manifest.value()).stream().filter(n->!n.equals(local)).findFirst().orElseThrow();
        long epoch=AutomaticProtocol.nextEpoch(previousEpoch,nodes(manifest.value()).indexOf(peer));
        var ballot=decode(encode("PROMISE",Map.of("manifestDigest",manifest.digest(),"epoch",epoch,"proposer",peer,"incarnation",UUID.randomUUID().toString())),"PROMISE");
        var request=AutomaticWire.message(manifest,ballot,peer,local,"PREPARE",UUID.randomUUID(),1,Map.of("nonce",UUID.randomUUID().toString()));
        var endpoint=config.members().stream().filter(m->m.nodeId().equals(config.localNodeId())).findFirst().orElseThrow().endpoint();
        try(var socket=new Socket(endpoint.host(),endpoint.port())) {
            socket.setSoTimeout(5000);socket.getOutputStream().write(AutomaticWire.encode(request,manifest,LIMITS.maxFrameBytes()));
            byte[] header=socket.getInputStream().readNBytes(48);int size=AutomaticWire.bodyLength(header,LIMITS.maxFrameBytes());
            byte[] frame=Arrays.copyOf(header,48+size);System.arraycopy(socket.getInputStream().readNBytes(size),0,frame,48,size);
            assertEquals("PROMISE",AutomaticWire.decode(frame,manifest,LIMITS.maxFrameBytes()).get("type"));
        }
    }
}
