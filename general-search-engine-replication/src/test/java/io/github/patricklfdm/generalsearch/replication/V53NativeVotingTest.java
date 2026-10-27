package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53NativeVotingTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(120);
    final class Network implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<MembershipVotingEndpoint> endpoints=new ArrayList<>();
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<AtomicReference<MembershipTransport>> links=new ArrayList<>();
        final List<AtomicReference<MembershipBallotAllocator.Cut>> hooks=new ArrayList<>();
        final List<Map<String,Object>> wire=Collections.synchronizedList(new ArrayList<>()),events=Collections.synchronizedList(new ArrayList<>());
        final AtomicBoolean noOutgoing=new AtomicBoolean();
        final AtomicReference<String> dropped=new AtomicReference<>("");
        final AtomicBoolean drop=new AtomicBoolean();
        final Decoded entry,accept;
        final byte[] payload;
        final boolean applicationEnabled;
        Network(int size,boolean data)throws Exception {
            this(size,data,false);
        }
        Network(int size,boolean data,boolean applicationEnabled)throws Exception {
            this.applicationEnabled=applicationEnabled;
            Path raw=Files.createDirectories(Path.of("target/"+(applicationEnabled?"v53-native-application-ingress":"v53-native-voting")+"/run-"+UUID.randomUUID()));System.out.println("v53NativeVotingEvidence="+raw.toAbsolutePath());
            f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve(UUID.randomUUID().toString())),size,false));
            f.ownedHistory=true;f.nativeApplication=true;f.campaign(1);if(data)f.publish(1,false);f.snapshot("before-voting");
            for(var target:f.request.targets()) {
                var resources=new MembershipResources(512*MembershipResources.MIB);budgets.add(resources);var hook=new AtomicReference<MembershipBallotAllocator.Cut>(event->{});hooks.add(hook);
                owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),resources,
                        MembershipGrantJournal.MAXIMUM,event->{events.add(Map.of("node",target.identity().nodeId().value(),"event",event));hook.get().at(event);}));links.add(new AtomicReference<>());
            }
            if(data)try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().getFirst().materialization(),ReplicationBounds.defaults())) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(456,"native-payload-"+"x".repeat(1024)))));
            }else payload=new byte[0];
            var context=owners.getFirst().activationContext();entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                    "index",number(context.cut.get("index"))+1,"previous",context.cut.get("entry"),"origin",f.ballot,"kind",data?"DATA":"BARRIER","payload",hash(payload))),"records","ENTRY");
            owners.getFirst().acceptCurrent(entry,payload);accept=owners.getFirst().voting(budgets.getFirst()).record("ACCEPT").orElseThrow();
            Files.write(raw.resolve("entry.gsr"),entry.bytes());Files.write(raw.resolve("payload.bin"),payload);
            for(int i=0;i<size;i++)start(i);
        }
        void start(int index)throws Exception {
            var owner=owners.get(index);var resources=budgets.get(index);var bounds=ReplicationBounds.defaults();
            MembershipSourcePull.Link outgoing=(peer,request,kind,deadline)->{
                if(noOutgoing.get())throw new AssertionError("duplicate must use own forced vote");
                return links.get(index).get().exchange(peer,request,kind,deadline);
            };
            var endpoint=applicationEnabled?new MembershipVotingEndpoint(owner,resources,bounds,outgoing,System::nanoTime,System.nanoTime(),BUDGET,
                    builder().configuration(),f.request.targets().get(index).materialization()):
                    new MembershipVotingEndpoint(owner,resources,bounds,outgoing,System::nanoTime,System.nanoTime(),BUDGET);
            var transport=new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,resources,endpoint,(event,request,response)->{
                if(event.equals("BEFORE_RESPONSE_WRITE")){boolean withheld=response.kind().equals(dropped.get()) && drop.compareAndSet(true,false);
                    var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",withheld);wire.add(row);
                    events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                    if(withheld)throw new IOException("lost original vote acknowledgement");}
            });
            if(index==endpoints.size()){endpoints.add(endpoint);transports.add(transport);}else{endpoints.set(index,endpoint);transports.set(index,transport);}
            links.get(index).set(transport);
        }
        Decoded request(int target,Decoded record) throws Exception {
            return MembershipActivation.frame(record.kind(),owners.getFirst().activationContext(),owners.getFirst().activationIdentity(),owners.get(target).activationIdentity(),
                    f.ballot,UUID.randomUUID(),1,Map.of(record.kind().equals("ACCEPT")?"acceptance":"proof",record.digest()));
        }
        Decoded send(int target,Decoded request)throws Exception {
            return transports.getFirst().exchange(owners.get(target).activationIdentity(),request,request.kind()+"_ACK",System.nanoTime()+BUDGET).get(120,TimeUnit.SECONDS);
        }
        MembershipContext.Owned observation(int source,Decoded record)throws Exception {
            if(source==0)return owners.getFirst().voting(budgets.getFirst()).observation(record);
            try(var pull=new MembershipSourcePull(owners.getFirst().activationCapsule(),owners.getFirst().activationIdentity(),owners.get(source).activationIdentity(),f.ballot,
                    UUID.randomUUID(),budgets.getFirst(),ReplicationBounds.defaults(),(peer,request,kind,deadline)->transports.getFirst().exchange(peer,request,kind,deadline),
                    ()->owners.getFirst().voting(budgets.getFirst()).check(),System::nanoTime,System.nanoTime(),BUDGET)){return pull.fetchVoteObservation(record);}
        }
        Decoded proof()throws Exception {
            var receipts=new HashSet<MembershipContext.Owned>();for(int i=0;i<owners.size();i++)receipts.add(observation(i,accept));
            var fields=new TreeMap<>(accept.value());fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",accept,receipts));
            var proof=decode(encode("records","PROOF",fields),"records","PROOF");owners.getFirst().proveCurrent(proof,receipts);return proof;
        }
        void reopen(int index)throws Exception {
            endpoints.get(index).close();transports.get(index).close();owners.get(index).close();assertEquals(0,budgets.get(index).usage().leases());
            var target=f.request.targets().get(index);owners.set(index,MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),
                    budgets.get(index),MembershipGrantJournal.MAXIMUM,event->{events.add(Map.of("node",target.identity().nodeId().value(),"event",event));hooks.get(index).get().at(event);}));start(index);
        }
        @Override public void close()throws Exception {
            for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();for(var owner:owners)owner.close();
            for(var budget:budgets)assertEquals(0,budget.usage().leases());
            Files.write(f.raw.resolve("wire.json"),canonical(wire,8*1024*1024));Files.write(f.raw.resolve("events.json"),canonical(events,8*1024*1024));
            f.snapshot(applicationEnabled?"after-ingress":"after-voting");V53NativeApplicationTest.save(f);
        }
    }
    @Test void realTcpForcesFirstAcceptAndProofAtEveryOriginalVoter()throws Exception {
        for(int size:List.of(3,4,5))for(boolean data:List.of(false,true))try(var n=new Network(size,data)) {
            for(int i=1;i<size;i++)assertTrue(n.owners.get(i).voting(n.budgets.get(i)).record("ACCEPT").isEmpty());
            var acks=new ArrayList<Decoded>();for(int i=1;i<size;i++)acks.add(n.send(i,n.request(i,n.accept)));
            var proof=n.proof();for(int i=1;i<size;i++)acks.add(n.send(i,n.request(i,proof)));
            for(int i=0;i<size;i++){assertEquals(proof.digest(),n.owners.get(i).voting(n.budgets.get(i)).record("PROOF").orElseThrow().digest());assertEquals(proof.digest(),n.observation(i,proof).record());
                assertTrue(n.owners.get(i).currentCertificate().isEmpty());assertEquals(data?1L:0L,n.owners.get(i).activationContext().cut.get("index"));}
            Files.write(n.f.raw.resolve("proof.gsr"),proof.bytes());Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","size",size,"kind",data?"DATA":"BARRIER","acknowledgements",acks.size()),4096));
        }
    }
    @Test void lostAcknowledgementsAndReopenedDuplicatesDoNotPullOrRewrite()throws Exception {
        try(var n=new Network(3,false)) {
            for(int i=1;i<3;i++)n.send(i,n.request(i,n.accept));var proof=n.proof();
            for(var record:List.of(n.accept,proof)) {
                var request=n.request(2,record);n.dropped.set(record.kind()+"_ACK");n.drop.set(true);
                assertThrows(ExecutionException.class,()->n.send(2,request));assertFalse(n.drop.get());
                n.reopen(2);var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());n.noOutgoing.set(true);
                var first=n.send(2,request);assertArrayEquals(first.bytes(),n.send(2,request).bytes());n.noOutgoing.set(false);
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            }
        }
    }
    @Test void noOriginalVoteMeansNoReceiptEvenWithAValidExpectedHash()throws Exception {
        try(var n=new Network(3,false)) {
            String receipt=MembershipVoteReceipt.reference(MembershipVoteReceipt.bytes(n.owners.getFirst().activationContext(),n.owners.get(1).activationIdentity(),n.accept));
            var before=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->n.owners.get(1).exportTransfer(receipt,n.owners.getFirst().activationContext().authority(),n.f.ballot,System::nanoTime,System.nanoTime(),BUDGET));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
            assertThrows(Exception.class,()->n.observation(1,n.accept));assertTrue(n.owners.get(1).voting(n.budgets.get(1)).record("ACCEPT").isEmpty());
        }
    }
    @Test void higherBallotAtForcePreventsAcknowledgementAndRevokesBorrow()throws Exception {
        try(var n=new Network(3,true)) {
            var owner=n.owners.get(1);var higher=Map.<String,Object>of("counter",3L,"proposer","node-1","incarnation",n.owners.getFirst().activationIdentity().storageId().toString());
            n.hooks.get(1).set(event->{if(event.equals("ACCEPT_BEFORE_RETURN"))owner.observeCurrent(higher);});
            assertThrows(ExecutionException.class,()->n.send(1,n.request(1,n.accept)));
            assertThrows(IllegalArgumentException.class,()->owner.voting(n.budgets.get(1)));
            var source=n.owners.getFirst();try(var borrow=source.exportTransfer((String)n.entry.value().get("payload"),source.activationContext().authority(),n.f.ballot,System::nanoTime,System.nanoTime(),BUDGET)) {
                assertArrayEquals(n.payload,borrow.read((String)n.entry.value().get("payload"),0,4096));source.observeCurrent(higher);assertThrows(IllegalArgumentException.class,borrow::references);
            }
        }
    }
}
