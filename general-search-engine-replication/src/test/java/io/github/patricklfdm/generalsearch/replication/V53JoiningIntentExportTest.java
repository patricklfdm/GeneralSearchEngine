package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual bootstrap/typed learner/old-quorum INTENT originals. Only the separate
 * durable pending owner may supply a new-side ACK. Publication still requires
 * native checkpoint pulls and the unchanged future-retention quorum. */
class V53JoiningIntentExportTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(12);
    record Input(Decoded entry,byte[] payload) {}
    static Input input(V53NativeDispatchTest.Network n,String kind,Object command)throws Exception {
        var context=n.owners.getFirst().activationContext();byte[] payload=canonical(command,8192);
        return new Input(decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                "index",number(context.cut.get("index"))+1,"previous",context.cut.get("entry"),"origin",n.ballot,
                "kind",kind,"payload",hash(payload))),"records","ENTRY"),payload);
    }
    static void publish(V53NativeDispatchTest.Network n,String kind,Object command)throws Exception {
        var input=input(n,kind,command);
        try(var driver=new MembershipSlotDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                n.transports.getFirst(),System::nanoTime,System.nanoTime(),BUDGET,builder().configuration(),
                n.f.request.targets().getFirst().materialization(),MembershipSlotDriver.Events.NONE)) {
            assertEquals("PUBLISH_ACK",driver.run(input.entry,input.payload).kind());
        }
    }
    static Decoded initial(MembershipLearnerRequest request,MembershipIdentity peer,Map<String,Object> cut) {
        return frame(request,peer,UUID.randomUUID(),1,"CHUNK",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST",
                "offset",0L,"digest",MembershipJoiningIntentExport.reference(request,cut),"bytes",""));
    }
    static Decoded frame(MembershipLearnerRequest request,MembershipIdentity peer,UUID trace,long sequence,String kind,Map<String,Object> payload) {
        return decode(encode("wire",kind,Map.of("root",request.root().manifestDigest(),"view",request.change().expectedConfigurationDigest(),
                "ballot",MembershipLearnerDiscovery.correlation(request.identity()),"sender",MembershipBootstrapSeed.identity(request.identity()),
                "recipient",MembershipBootstrapSeed.identity(peer),"trace",trace.toString(),"sequence",sequence,"payload",payload)),"wire",kind);
    }
    static Decoded exchange(MembershipTransport contact,MembershipIdentity peer,Decoded request,String kind)throws Exception {
        var response=contact.exchange(peer,request,kind,System.nanoTime()+TimeUnit.SECONDS.toNanos(30)).get(35,TimeUnit.SECONDS);
        MembershipWire.correlated(request,response,kind);assertEquals(kind,response.kind());return response;
    }
    static byte[] fetch(MembershipTransport contact,MembershipLearnerRequest learner,MembershipIdentity peer,Decoded first)throws Exception {
        var offer=exchange(contact,peer,first,"SOURCE_OFFER");var content=object(offer.value().get("payload"));
        assertEquals("RECORD",content.get("kind"));assertEquals(object(first.value().get("payload")).get("id"),content.get("id"));
        assertArrayEquals(offer.bytes(),exchange(contact,peer,first,"SOURCE_OFFER").bytes());
        var out=new java.io.ByteArrayOutputStream();long sequence=1;var trace=UUID.fromString((String)first.value().get("trace"));
        while(out.size()<number(content.get("bytes"))) {
            var request=frame(learner,peer,trace,++sequence,"CHUNK",Map.of("id",content.get("id"),"action","REQUEST",
                    "offset",(long)out.size(),"digest",content.get("digest"),"bytes",""));
            var response=exchange(contact,peer,request,"CHUNK");var payload=object(response.value().get("payload"));
            assertEquals((long)out.size(),payload.get("offset"));assertEquals(content.get("id"),payload.get("id"));
            byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));assertEquals(hash(bytes),payload.get("digest"));out.writeBytes(bytes);
        }
        assertEquals(number(content.get("bytes")),out.size());assertEquals(hash(out.toByteArray()),content.get("digest"));
        var last=frame(learner,peer,trace,++sequence,"TRANSFER_COMMIT",Map.of("id",content.get("id"),"digest",content.get("digest")));
        var done=exchange(contact,peer,last,"TRANSFER_COMMIT");
        assertArrayEquals(done.bytes(),exchange(contact,peer,last,"TRANSFER_COMMIT").bytes());return out.toByteArray();
    }
    @Test void minimalOldMajorityCanServeOriginalIntentBeforeJointCheckpointExists()throws Exception {
        nativeJoining(false);
    }
    @Test void originalTypedLearnerForcesTheMissingNewSideEndWithoutPublishingJoint()throws Exception {
        nativeJoining(true);
    }
    @Test void minimalOldMajorityPublishesJointUsingTheActualJoiningEndpoint()throws Exception {
        nativeJoining(true,true);
    }
    @Test void minimalOldMajorityPublicationInstallsActualJoiningNativeOwnerAndReopensIt()throws Exception {
        nativeJoining(true,true,true);
    }
    @Test void actualJoiningCopyReconcilesTheOldLedgerOnlyAfterTheGoverningFloorForces()throws Exception {
        nativeJoining(true,true,true,true);
    }
    @Test void unusedJoiningOwnerCapturesExactOldMajorityRetentionAndRefusesAfterUse()throws Exception {
        nativeJoining(true,true,true,true,true);
    }
    @Test void originalJoiningRetentionRecoversInterruptedInitializationAndRefusesMissingCompletedLedger()throws Exception {
        nativeJoining(true,true,true,true,true,true);
    }
    @Test void actualJoiningVoterCompletesJointFinalAndFreshStableBarrier()throws Exception {
        nativeJoining(true,true,true,true,true,true,true);
    }
    @Test void actualJoiningVoterAcquiresRetentionOverTcpThenCompletesFinalAndBarrier()throws Exception {
        nativeJoining(true,true,true,true,true,true,true,true);
    }
    @Test void joiningInitializerStartsBeforeOldPreparationAndCompletesNativeHistory()throws Exception {
        nativeJoining(true,true,true,true,true,true,true,true,true);
    }
    private void nativeJoining(boolean retainPending)throws Exception {
        nativeJoining(retainPending,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint)throws Exception {
        nativeJoining(retainPending,publishJoint,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,maintainJoined,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined,boolean seedJoined)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,maintainJoined,seedJoined,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined,boolean seedJoined,boolean initializeJoined)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,maintainJoined,seedJoined,initializeJoined,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined,boolean seedJoined,boolean initializeJoined,boolean continueJoint)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,maintainJoined,seedJoined,initializeJoined,continueJoint,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined,boolean seedJoined,boolean initializeJoined,boolean continueJoint,boolean remoteRetention)throws Exception {
        nativeJoining(retainPending,publishJoint,installJoined,maintainJoined,seedJoined,initializeJoined,continueJoint,remoteRetention,false);
    }
    private void nativeJoining(boolean retainPending,boolean publishJoint,boolean installJoined,boolean maintainJoined,boolean seedJoined,boolean initializeJoined,boolean continueJoint,boolean remoteRetention,boolean earlyStartup)throws Exception {
        assertTrue(!earlyStartup || remoteRetention && initializeJoined && continueJoint);
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        // The additional complete installation/cold-open scenario has one
        // declared owner lifetime from its start. Existing scenarios keep
        // their 12 minutes; no RPC timeout or production bound is changed.
        long lifetime=continueJoint?TimeUnit.MINUTES.toNanos(40):installJoined?TimeUnit.MINUTES.toNanos(20):BUDGET;
        try(var n=network.new Network(3,helper.controlBounds(),lifetime,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learners")){owner.initializeLearnerRetention();}
        },true);var round=helper.driver(n,MembershipRoundDriver.Events.NONE,lifetime)) {
            // The short Network.activate helper fixes a 180-second campaign.
            // This complete typed-learner history uses one declared
            // owner lifetime from its start, without extending any RPC timeout.
            n.transports.get(2).close();round.start();assertEquals(List.of(0,1),n.voters);
            if(installJoined)probeOldLocks(n);
            int port;try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var owner=n.owners.getFirst();var resources=n.resources.getFirst();
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),owner.activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner"),temp.resolve("operation"));
            round.submit("RESERVE",canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192));
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));
            long preparedIndex=number(owner.activationContext().cut.get("index"));
            System.out.println("v53JoiningIntentStage=prepared");
            var pool=new MembershipResources(512*MembershipResources.MIB);
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("core"),2),
                    n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            try(var source=new MembershipLearnerSource(request,targets.getFirst(),pool,n.bounds,MembershipTransport.Events.NONE,
                    ()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                source.fetch(temp.resolve("receiving"));var plan=source.plan(e->{});
                try(var store=source.admit(plan,e->{})) {
                    source.close();
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,e->{})) {
                        round.submit("READY",canonical(Map.of("number",1L,"receipt",typed.receipt().value().get("receipt")),8192));
                        round.maintainReady(); // Preserve real pre-SEAL retention reconciliation and its fresh BARRIER.
                        publish(n,"SEAL",Map.of("number",1L));var before=owner.activationContext();var first=initial(request,targets.getFirst(),before.cut);
                        long sealedIndex=number(before.cut.get("index"));
                        System.out.println("v53JoiningIntentStage=sealed");
                        if(installJoined)assertThrows(IllegalArgumentException.class,()->owner.publishedLearnerSource(joining,resources));
                        // A SEALED catalog alone cannot mint an original pending source.
                        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,resources,
                                System::nanoTime,System.nanoTime(),BUDGET));
                        // Fetch the still-published SEALED history before the
                        // pending slot, using the original retained learner head.
                        // The pending metadata route cannot replace that history.
                        try(var progress=retainPending?new MembershipLearnerProgress(typed.retainGeneration(),targets.getFirst(),n.bounds,
                                MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),BUDGET):null) {
                            if(progress!=null) {
                                progress.fetch(temp.resolve("joining-progress"));
                                System.out.println("v53JoiningIntentStage=original-sealed-received");
                            }
                            var row=object(list(before.catalog.get("results")).getLast());var sealed=new TreeMap<String,Object>();
                            for(String field:List.of("request","prepared","receipt"))sealed.put(field,row.get(field));
                            var next=input(n,"INTENT",Map.of("sealed",sealed));n.endpoints.getFirst().maintainInstalled();
                            owner.acceptCurrent(next.entry,next.payload,builder().configuration(),n.f.request.targets().getFirst().materialization());
                            assertThrows(IllegalArgumentException.class,()->owner.joiningIntent(joining));
                            var certificate=n.apply(owner.voting(resources).record("ACCEPT").orElseThrow());
                            var applied=owner.voting(resources).application().orElseThrow();
                            var other=n.owners.get(1).voting(n.resources.get(1)).application().orElseThrow();
                            assertEquals(List.of("node-1","node-2"),list(certificate.value().get("proofs")).stream().map(v->object(v).get("voter")).toList());
                            // Old majority certificate is real, but old 2/3 alone is
                            // not new 3/4. Keep that required refusal unchanged.
                            assertThrows(IllegalArgumentException.class,()->applied.plan().complete(
                                    List.of(applied.endorsement().acknowledgement(),other.endorsement().acknowledgement()),
                                    Set.of(applied.endorsement().owned(),other.endorsement().owned())));
                            assertSame(before,owner.activationContext());assertFalse(before.voters().contains("node-4"));
                            var files=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                            var learnerFiles=V53ReplayFilesTest.files(request.operationDirectory());
                            var wire=new ArrayList<Map<String,Object>>();
                            try(var contact=MembershipTransport.learnerJoiningIntent(request,new MembershipDiscovery.Hint(targets.getFirst(),before.cut,false),n.bounds,pool,(event,q,a)->{
                                if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(q,a));
                            })) {
                                var forbidden=new TreeMap<>(first.value());var p=new TreeMap<>(object(first.value().get("payload")));
                                p.put("digest",MembershipLearnerDiscovery.reference(request));forbidden.put("payload",p);
                                assertEquals(MembershipTransport.Reason.PROTOCOL,V53MembershipTransportTest.failure(contact.exchange(targets.getFirst(),
                                        decode(encode("wire","CHUNK",forbidden),"wire","CHUNK"),"SOURCE_OFFER",System.nanoTime()+BUDGET)).reason);
                                var bytes=fetch(contact,request,targets.getFirst(),first);var value=object(parse(bytes,FRAME));var records=object(value.get("records"));
                                assertEquals("gse-v53-joining-intent-metadata/1.3",value.get("schema"));assertEquals(sealed.get("request"),value.get("request"));
                                assertEquals(MembershipRetentionIntent.anchor(owner.activationCapsule().terminal()),value.get("parent"));
                                assertEquals(MembershipBootstrapSeed.identity(joining),value.get("learner"));
                                assertEquals(Set.of("ENTRY","ACCEPT","PROOF","CERTIFICATE","CATALOG","CHECKPOINT"),records.keySet());
                                assertArrayEquals(certificate.bytes(),Base64.getDecoder().decode((String)records.get("CERTIFICATE")));
                                assertArrayEquals(next.entry.bytes(),Base64.getDecoder().decode((String)records.get("ENTRY")));
                                assertArrayEquals(next.payload,Base64.getDecoder().decode((String)value.get("payload")));
                                assertArrayEquals(applied.plan().catalog.bytes(),Base64.getDecoder().decode((String)records.get("CATALOG")));
                                assertArrayEquals(applied.plan().statement.bytes(),Base64.getDecoder().decode((String)records.get("CHECKPOINT")));
                                Files.write(n.f.raw.resolve("joining-intent.json"),bytes);
                            }
                            assertEquals(files,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                            assertEquals(learnerFiles,V53ReplayFilesTest.files(request.operationDirectory()));assertSame(before,owner.activationContext());
                            if(progress!=null) {
                                var original=progress.joiningMetadata().fetch();
                                assertArrayEquals(certificate.bytes(),original.record("CERTIFICATE").bytes());
                                var events=new ArrayList<String>();
                                try(var pending=progress.retainPendingIntent(events::add)) {
                                    var added=pending.endorse();
                                    assertArrayEquals(applied.plan().statement.bytes(),pending.originals().record("CHECKPOINT").bytes());
                                    var checkpoint=applied.plan().complete(
                                            List.of(applied.endorsement().acknowledgement(),other.endorsement().acknowledgement(),added.acknowledgement()),
                                            Set.of(applied.endorsement().owned(),other.endorsement().owned(),added.owned()));
                                    assertEquals("JOINT",MembershipLearnerProgressAccess.operation(checkpoint.context,joining).get("phase"));
                                    assertSame(before,owner.activationContext());assertFalse(before.voters().contains("node-4"));
                                    assertEquals(files,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                                    assertTrue(events.indexOf("LEARNER_JOINING_SOURCE_PARENTS_FORCED")<events.indexOf("LEARNER_JOINING_ACK_CREATED"));
                                    assertTrue(events.indexOf("LEARNER_JOINING_ACK_FORCED")<events.indexOf("LEARNER_JOINING_ACK_BEFORE_RETURN"));
                                    assertFalse(Files.exists(config.materialization().directory()));
                                    Files.write(n.f.raw.resolve("joining-forced-ack.gsr"),added.acknowledgement().bytes());
                                    Files.write(n.f.raw.resolve("joining-force-events.json"),canonical(events,16384));
                                    Files.write(n.f.raw.resolve("joining-complete-capsule.gscp"),checkpoint.packet.bytes());
                                    System.out.println("v53JoiningIntentStage=new-side-end-forced");
                                    if(publishJoint) {
                                        var readers=java.util.concurrent.ConcurrentHashMap.<String>newKeySet();
                                        var ackWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                                        try(var listener=pending.listen(n.bounds,(event,requestFrame,response)->{
                                            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                                readers.add((String)object(requestFrame.value().get("sender")).get("node"));
                                                ackWire.add(V53SelectedPullTest.wire(requestFrame,response));
                                            }
                                        },System::nanoTime,System.nanoTime(),BUDGET)) {
                                            n.publish(certificate);
                                            assertEquals(Set.of("node-1","node-2"),readers);
                                            for(int voter:n.voters)assertEquals("JOINT",MembershipLearnerProgressAccess.operation(n.owners.get(voter).activationContext(),joining).get("phase"));
                                            assertEquals("SEALED",MembershipLearnerProgressAccess.operation(pending.source().context,joining).get("phase"));
                                            assertFalse(Files.exists(config.materialization().directory()));
                                            assertEquals(0,listener.usage().exports());
                                        }
                                        Files.write(n.f.raw.resolve("joining-ack-wire.json"),canonical(ackWire,1024*1024));
                                        System.out.println("v53JoiningIntentStage=joint-published-by-old-majority");
                                        if(installJoined) {
                                            probeOldLocks(n);
                                            // Consume the actual retained owner and native published
                                            // source. No fixture history, decoded replacement owner
                                            // or direct checkpoint insertion supplies this joining end.
                                            progress.close();var retained=pending.retainSource();Decoded nativeBasis;long nativeCounter=0;
                                            var confirmationWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                                            try(var headEndpoint=retained.listenHead(n.bounds,(event,q,a)->{
                                                if(event.equals("BEFORE_RESPONSE_WRITE"))confirmationWire.add(V53SelectedPullTest.wire(q,a));
                                            })) {
                                                for(int voter:n.voters) {
                                                    var sourceOwner=n.owners.get(voter);var sourcePool=n.resources.get(voter);
                                                    assertEquals(List.of(preparedIndex,sealedIndex),sourceOwner.learnerRetentionState().plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                                                    try(var probe=new MembershipLearnerHeadProbe(sourceOwner,joining,sourcePool,n.bounds,
                                                            n.transports.get(voter)::exchange,System::nanoTime,System.nanoTime(),BUDGET)) {
                                                        var received=probe.run();assertEquals(sealedIndex,number(received.endpoint().cut().get("index")));
                                                        assertThrows(IllegalArgumentException.class,()->received.confirmation(n.owners.get(1-voter),n.resources.get(1-voter)));
                                                        var confirmed=sourceOwner.retainLearnerConfirmation(received);
                                                        assertEquals(List.of(sealedIndex),confirmed.plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                                                        var ledger=object(parse(confirmed.plan().bytes(),MembershipLearnerRetentionPlan.MAXIMUM));
                                                        assertEquals(List.of(preparedIndex),list(ledger.get("renewals")).stream().map(v->number(object(object(v).get("cut")).get("index"))).toList());
                                                        assertTrue(ledger.containsKey("confirmation"));
                                                        Files.write(n.f.raw.resolve("joining-confirmed-node-"+(voter+1)+".json"),canonical(ledger,MembershipLearnerRetentionPlan.MAXIMUM));
                                                    }
                                                }
                                            }
                                            // Published-prefix permits are issued only by the exact
                                            // native owner; bare/foreign capabilities remain refused.
                                            var permit=owner.publishedLearnerSource(joining,resources);
                                            permit.checkExport(owner,joining,resources);
                                            assertThrows(IllegalArgumentException.class,()->permit.checkExport(n.owners.get(1),joining,n.resources.get(1)));
                                            assertThrows(IllegalArgumentException.class,()->permit.checkExport(owner,targets.getFirst(),resources));
                                            assertThrows(IllegalArgumentException.class,()->permit.checkExport(owner,joining,pool));
                                            assertThrows(IllegalArgumentException.class,owner::checkLearnerRetentionExport);
                                            assertThrows(IllegalArgumentException.class,()->owner.publishedLearnerSource(targets.get(1),resources));
                                            var originalLedger=owner.learnerRetentionState();
                                            var readRequest=frame(request,targets.getFirst(),UUID.randomUUID(),1,"CHUNK",Map.of("id",UUID.randomUUID().toString(),
                                                    "action","REQUEST","offset",0L,"bytes","","digest",MembershipLearnerProgressAccess.reference(request,owner.activationContext().cut,"prefix")));
                                            assertThrows(IllegalArgumentException.class,()->new MembershipLearnerPrefixExport(owner,joining,readRequest,resources,
                                                    System::nanoTime,System.nanoTime(),BUDGET,true));
                                            try(var export=new MembershipLearnerPrefixExport(owner,joining,readRequest,resources,
                                                    System::nanoTime,System.nanoTime(),BUDGET,true,null,permit)) {
                                                assertFalse(export.references().isEmpty());
                                            }
                                            assertEquals(originalLedger,owner.learnerRetentionState());
                                            Files.write(n.f.raw.resolve("joining-head-wire.json"),canonical(confirmationWire,1024*1024));
                                            assertEquals(2,confirmationWire.size());
                                            System.out.println("v53JoiningIntentStage=both-old-voters-confirmed-original-sealed-source");
                                            try(var published=new MembershipLearnerProgress(retained,targets.getFirst(),n.bounds,
                                                    MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),BUDGET)) {
                                                published.fetch(temp.resolve("joining-published-progress"));
                                                assertEquals(originalLedger,owner.learnerRetentionState(),"configured-member read does not add learner uncertainty");
                                                assertEquals(sealedIndex+1,number(published.source().capsule.context.cut.get("index")));
                                                System.out.println("v53JoiningIntentStage=original-joint-source-received");
                                                try(var intent=published.retainPublishedIntent(e->{})) {
                                                    published.close();
                                                    try(var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                                                            var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{});
                                                            var placement=MembershipLearnerPlacement.install(custody,e->{})) {
                                                        var joined=MembershipLearnerJoinedAdmission.install(placement,builder().configuration(),config,e->{});
                                                        MembershipLearnerJoinedOriginal.verify(joined,builder().configuration(),config);
                                                        joinedSnapshot(plan,config.materialization().directory(),n.f.raw.resolve("joining-originals-placed"));
                                                        System.out.println("v53JoiningIntentStage=actual-joined-placement");
                                                        try(var retired=MembershipLearnerJoinedRetirement.retire(joined,builder().configuration(),config,e->{});
                                                                var journal=MembershipGrantJournal.openJoined(retired,builder().configuration(),config,e->{})) {
                                                            assertEquals(1,pool.usage().counts().get(MembershipResources.Unit.GENERATION));
                                                            assertFalse(pool.usage().counts().containsKey(MembershipResources.Unit.SOURCE));
                                                            if(maintainJoined) {
                                                                assertEquals(Set.of("node-4"),owner.maintenanceJoiningPeers());
                                                                var beforePeers=owner.peerRetentionState();
                                                                var permission=owner.publishedMaintenance(resources);permission.check();
                                                                assertEquals(beforePeers,owner.peerRetentionState());
                                                                assertThrows(IllegalArgumentException.class,owner::reconcileMaintenancePeers);
                                                                assertEquals(beforePeers,owner.peerRetentionState());
                                                                // Every copy comes from its actual still-open native
                                                                // owner, including the newly installed joining root.
                                                                owner.establishFloor(List.of(owner.floorCopyCurrent(),
                                                                        n.owners.get(1).floorCopyCurrent(),journal.floorCopyCurrent()));
                                                                permission.check();owner.reconcileMaintenancePeers();permission.check();
                                                                assertTrue(owner.maintenanceJoiningPeers().isEmpty());
                                                                var reconciled=owner.peerRetentionState();
                                                                assertEquals(List.of(sealedIndex+1),reconciled.plan().possible(joining).stream().map(a->number(a.cut().get("index"))).toList());
                                                                for(var old:n.f.request.targets())assertEquals(beforePeers.plan().possible(old.identity()),
                                                                        reconciled.plan().possible(old.identity()),"adding a peer cannot erase old uncertainty");
                                                                owner.reconcileMaintenancePeers();assertEquals(reconciled,owner.peerRetentionState());
                                                                assertEquals(originalLedger,owner.learnerRetentionState());
                                                                Files.write(n.f.raw.resolve("joining-floor-reconciled.json"),reconciled.plan().bytes());
                                                                probeOldLocks(n);
                                                                System.out.println("v53JoiningIntentStage=actual-joining-floor-reconciled");
                                                            }
                                                            if(seedJoined) {
                                                                var copies=List.of(owner.floorCopyCurrent(),n.owners.get(1).floorCopyCurrent(),journal.floorCopyCurrent());
                                                                for(int i=0;i<2;i++) {
                                                                    var old=n.owners.get(i);var seedMaintenance=old.publishedMaintenance(n.resources.get(i));
                                                                    if(i!=0)old.establishFloor(copies);
                                                                    // This is optional maintenance after forcing the complete
                                                                    // floor. Preserve full renewal debt until the actual
                                                                    // joining-source merge, just as native maintenance does.
                                                                    old.reconcileMaintenancePeers();for(var copy:copies)old.retainMaintenancePeerObservation(copy);
                                                                    old.retireInactive();
                                                                    for(String obsolete:old.supersededPublishedSources(seedMaintenance))old.retireSource(obsolete);
                                                                    old.releaseFloor();seedMaintenance.check();
                                                                }
                                                                long retentionStarted=System.nanoTime();
                                                                var seedWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                                                                // Capture the actual unused joining copy before the
                                                                // concurrent initializer may force its ledgers. This
                                                                // pure expectation never authorizes initialization.
                                                                var earlyCopy=earlyStartup?journal.floorCopyCurrent():null;
                                                                byte[] earlyAncestry=earlyStartup?earlyCopy.fileBytes("ancestry.gsr"):null;
                                                                var firstAbsent=new java.util.concurrent.CountDownLatch(1);
                                                                var absence=new java.util.concurrent.atomic.AtomicReference<Map<String,Object>>();
                                                                // The installed joining owner serves read-only copies
                                                                // for governing-floor maintenance before it can vote.
                                                                var joiningLink=new java.util.concurrent.atomic.AtomicReference<MembershipTransport>();
                                                                try(var initializer=earlyStartup?java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor():null;
                                                                        var joiningEndpoint=remoteRetention?new MembershipJoiningEndpoint<>(journal,pool,n.bounds,(peer,q,kind,deadline)->{
                                                                            var channel=joiningLink.get();return channel==null?java.util.concurrent.CompletableFuture.failedFuture(new java.io.IOException("joining listener starting")):
                                                                                    channel.exchange(peer,q,kind,deadline).thenApply(answer->{
                                                                                        var observed=V53SelectedPullTest.wire(q,answer);seedWire.add(observed);
                                                                                        if(earlyStartup && q.kind().equals("CHUNK") && number(q.value().get("sequence"))==1
                                                                                                && object(q.value().get("payload")).get("digest").equals(MembershipJoiningPreparation.reference(earlyCopy.capsule.context,joining))
                                                                                                && answer.kind().equals("REJECT") && object(answer.value().get("payload")).get("reason").equals("NOT_READY")
                                                                                                && absence.compareAndSet(null,observed))firstAbsent.countDown();
                                                                                        return answer;
                                                                                    });
                                                                        },temp.resolve("joining-initial-endpoint"),System::nanoTime,retentionStarted,BUDGET,builder().configuration(),config.materialization()):null;
                                                                        var transport=remoteRetention?new MembershipTransport(journal,n.bounds,pool,joiningEndpoint,MembershipTransport.Events.NONE):null;
                                                                        var retentionPreparation=remoteRetention?new MembershipJoiningRetentionCampaign(owner,n.endpoints.getFirst(),resources,n.bounds,
                                                                                (peer,q,kind,deadline)->n.transports.getFirst().exchange(peer,q,kind,deadline).thenApply(answer->{seedWire.add(V53SelectedPullTest.wire(q,answer));return answer;}),
                                                                                ()->{},temp.resolve("old-retention-preparation-"+UUID.randomUUID()),System::nanoTime,retentionStarted,BUDGET,joining):null) {
                                                                if(remoteRetention) {
                                                                    joiningLink.set(transport);assertEquals(MembershipEndpointHandoff.State.READ_ONLY,joiningEndpoint.state());
                                                                    assertThrows(IllegalArgumentException.class,()->journal.joiningEndpointReady(pool));
                                                                    assertThrows(IllegalArgumentException.class,joiningEndpoint::votingEndpoint);
                                                                }
                                                                MembershipJoiningRetentionCampaign.Hint prepared=null;
                                                                java.util.concurrent.Future<?> initializing=null;
                                                                var originals=new ArrayList<MembershipSelection.Source>();
                                                                if(remoteRetention) {
                                                                    if(earlyStartup) {
                                                                        Files.write(n.f.raw.resolve("joining-early-generation.gsr"),earlyCopy.generation.bytes());
                                                                        Files.write(n.f.raw.resolve("joining-early-capsule.gscp"),earlyCopy.capsule.packet.bytes());
                                                                        Files.write(n.f.raw.resolve("joining-early-ancestry.gsr"),earlyAncestry);
                                                                        initializing=initializer.submit(()->{joiningEndpoint.initialize();return null;});
                                                                        assertTrue(firstAbsent.await(n.bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"actual absent preparation response before old campaign");
                                                                        assertFalse(initializing.isDone(),"no published preparation may initialize the new owner");
                                                                        System.out.println("v53JoiningIntentStage=initializer-observed-absence-before-old-preparation");
                                                                    }
                                                                    prepared=retentionPreparation.run();
                                                                    if(!earlyStartup)assertFalse(retentionPreparation.probeInitialized(),"original read-only joining owner is not initialized");
                                                                    for(String node:new TreeSet<>(prepared.sources().keySet()))originals.add(n.owners.stream()
                                                                            .filter(old->old.activationIdentity().nodeId().value().equals(node)).findFirst().orElseThrow().originalSource());
                                                                    System.out.println("v53JoiningIntentStage=old-majority-retention-prepared-over-tcp");
                                                                }else {
                                                                    long counter=owner.reserveCounter();var ballot=Map.<String,Object>of("counter",counter,
                                                                            "proposer",owner.activationIdentity().nodeId().value(),"incarnation",owner.activationIdentity().storageId().toString());
                                                                    for(int i=0;i<2;i++){n.owners.get(i).prepareCurrent(ballot);originals.add(n.owners.get(i).originalSource());}
                                                                }
                                                                assertThrows(IllegalArgumentException.class,()->owner.joiningRetentionSeed(originals));
                                                                var beforeSeed=earlyStartup?null:V53ReplayFilesTest.files(request.replicaDirectory());
                                                                var seed=earlyStartup?MembershipJoiningRetentionSeed.capture(earlyCopy.capsule,earlyAncestry,joining,originals):journal.joiningRetentionSeed(originals);
                                                                if(!earlyStartup)assertEquals(beforeSeed,V53ReplayFilesTest.files(request.replicaDirectory()),"seed preparation must not install ledgers");
                                                                assertEquals(List.of(preparedIndex,sealedIndex),V53PeerRetentionPlanTest.cuts(seed.learner.recorded()));
                                                                var ownCopy=journal.floorCopyCurrent();
                                                                var replay=MembershipJoiningRetentionSeed.read(seed.bytes(),ownCopy.capsule,ownCopy.fileBytes("ancestry.gsr"),joining);
                                                                assertArrayEquals(seed.peers.bytes(),replay.peers.bytes());assertArrayEquals(seed.learner.bytes(),replay.learner.bytes());
                                                                Files.write(n.f.raw.resolve("joining-retention-seed.json"),seed.bytes());
                                                                Files.write(n.f.raw.resolve("joining-retention-peers.json"),seed.peers.bytes());
                                                                Files.write(n.f.raw.resolve("joining-retention-learner.json"),seed.learner.bytes());
                                                                for(var frozenOriginal:originals){String name=frozenOriginal.owner.nodeId().value();
                                                                    Files.write(n.f.raw.resolve("joining-retention-"+name+".gsr"),frozenOriginal.basis.bytes());
                                                                    Files.write(n.f.raw.resolve("joining-retention-"+name+".gscp"),frozenOriginal.capsule.packet.bytes());}
                                                                if(initializeJoined) {
                                                                    if(remoteRetention) {
                                                                        if(earlyStartup) {
                                                                            long left=BUDGET-(System.nanoTime()-retentionStarted);assertTrue(left>0,"original initialization budget remains");
                                                                            initializing.get(left,TimeUnit.NANOSECONDS);
                                                                            Files.write(n.f.raw.resolve("joining-early-start.json"),canonical(Map.of("schema","gse-v53-joining-early-start-v1",
                                                                                    "initialAbsence",absence.get(),"beforeOldPreparation",true,"completed",true),8192));
                                                                        }else joiningEndpoint.initialize();
                                                                        assertJoinedRetention(journal,seed.bytes(),joining);
                                                                        assertEquals(MembershipEndpointHandoff.State.ACTIVE,joiningEndpoint.state());
                                                                        assertNotNull(joiningEndpoint.votingEndpoint());
                                                                        assertTrue(retentionPreparation.probeInitialized(),"old proposer observes native completion through TCP");
                                                                        Files.write(n.f.raw.resolve("joining-retention-wire.json"),canonical(seedWire,8*1024*1024));
                                                                        System.out.println("v53JoiningIntentStage=remote-old-majority-retention-initialized-and-endpoint-promoted");
                                                                    }else if(continueJoint)journal.initializeJoinedRetention(originals);
                                                                    if(transport!=null)transport.close();if(joiningEndpoint!=null)joiningEndpoint.close();
                                                                    journal.close();
                                                                    if(!continueJoint)initializeRetention(plan,pool,config,originals,seed,n.f.raw);
                                                                }else {
                                                                    nativeCounter=journal.reserveCounter();
                                                                    assertThrows(IllegalArgumentException.class,()->journal.joiningRetentionSeed(originals));
                                                                }
                                                                probeOldLocks(n);
                                                                System.out.println("v53JoiningIntentStage=original-old-majority-retention-seed-read-only");
                                                                }
                                                            }
                                                            // Recovery owns the original joining root; it is never
                                                            // copied to manufacture a second initialization history.
                                                            try(var recovered=initializeJoined?MembershipGrantJournal.reopenJoinedRetaining(plan,pool,builder().configuration(),config,e->{}):null) {
                                                            var active=initializeJoined?recovered:journal;
                                                            if(!seedJoined || initializeJoined)nativeCounter=active.reserveCounter();
                                                            nativeBasis=active.prepareCurrent(Map.of("counter",nativeCounter,
                                                                    "proposer",joining.nodeId().value(),"incarnation",joining.storageId().toString()));
                                                            assertEquals("BASIS",nativeBasis.kind());assertEquals("node-4",nativeBasis.value().get("voter"));
                                                            if(initializeJoined)assertJoinedRetention(active,seedFrom(n.f.raw),joining);
                                                            new V53MembershipOwnershipTest().probe(request.replicaDirectory().resolve("replica.lock"));
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            assertEquals(0,pool.usage().leases());
                                            try(var journal=initializeJoined?MembershipGrantJournal.reopenJoinedRetaining(plan,pool,builder().configuration(),config,e->{}):
                                                    MembershipGrantJournal.reopenJoined(plan,pool,builder().configuration(),config,e->{})) {
                                                assertArrayEquals(nativeBasis.bytes(),journal.prepareCurrent(Map.of("counter",nativeCounter,
                                                        "proposer",joining.nodeId().value(),"incarnation",joining.storageId().toString())).bytes());
                                                assertTrue(journal.reserveCounter()>nativeCounter);
                                            }
                                            assertEquals(0,pool.usage().leases());
                                            joinedSnapshot(plan,config.materialization().directory(),n.f.raw.resolve("joining-originals-native"));
                                            Files.write(n.f.raw.resolve("joining-native-basis.gsr"),nativeBasis.bytes());
                                            assertFalse(Files.exists(request.replicaDirectory().resolve(MembershipBootstrapAdmissionData.FILE)));
                                            System.out.println("v53JoiningIntentStage=actual-joined-native-cold-reopened");
                                            if(continueJoint) {
                                                round.close();n.f.snapshot("before-joint-continuation");
                                                continueJoint(n,plan,pool,config,lifetime,remoteRetention);
                                            }
                                        }
                                    }
                                }
                            }
                            if(!publishJoint)guardChecks(n,request,first);
                            Files.write(n.f.raw.resolve("joining-intent-wire.json"),canonical(wire,8*1024*1024));
                            Files.write(n.f.raw.resolve("joining-intent-result.json"),canonical(Map.of("status","PASS","oldVoters",List.of("node-1","node-2"),
                                    "nativeHistory",true,"typedLearner",true,"newSideEndForced",retainPending,"publishedJoint",publishJoint,"nativeJoined",installJoined,
                                    "joinedFloorReconciled",maintainJoined,"publicReady",false),4096));
                        }
                    }
                }
            }
            assertEquals(0,pool.usage().leases());
        }
    }
    private static void probeOldLocks(V53NativeDispatchTest.Network n)throws Exception {
        new V53MembershipOwnershipTest().probe(n.f.request.targets().stream()
                .map(t->t.replicaDirectory().resolve("replica.lock")).toArray(Path[]::new));
    }
    /** One original history: the new voter uses its existing permanent endpoint
     * and retaining cold owner. The native round chooses FINAL and the barrier. */
    private void continueJoint(V53NativeDispatchTest.Network n,MembershipLearnerPlan plan,MembershipResources resources,
            MembershipReplicaConfig<Integer,Doc> config,long budget,boolean joiningService)throws Exception {
        long stableIndex=number(n.owners.getFirst().activationContext().cut.get("index"))+2;
        var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var events=new ArrayList<Object>();var failures=Collections.synchronizedList(new ArrayList<Object>());
        var result=new TreeMap<String,Object>();result.put("status","FAIL");result.put("publicReady",false);
        try(var owner=MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{})) {
            var link=new java.util.concurrent.atomic.AtomicReference<MembershipTransport>();
            MembershipSourcePull.Link outgoing=(peer,request,kind,deadline)->{
                var transport=link.get();return transport==null?java.util.concurrent.CompletableFuture.failedFuture(new java.io.IOException("joining listener starting")):
                        transport.exchange(peer,request,kind,deadline);
            };
            try(var joined=joiningService?MembershipJoiningEndpoint.resume(owner,resources,n.bounds,outgoing,temp.resolve("joining-native-incoming"),
                        System::nanoTime,budget,builder().configuration(),config.materialization()):null;
                var endpoint=joiningService?null:new MembershipActivationEndpoint(owner,resources,n.bounds,outgoing,List.of(),List.of(),
                        temp.resolve("joining-native-incoming"),System::nanoTime,budget,builder().configuration(),config.materialization());
                var transport=new MembershipTransport(owner,n.bounds,resources,(peer,request)->{
                    try{return joiningService?joined.handle(peer,request):endpoint.handle(peer,request);}catch(java.io.IOException|RuntimeException error){
                        n.diagnostic(owner.activationIdentity().nodeId().value(),"HANDLER_FAILED",request,error);
                        failures.add(Map.of("kind",request.kind(),"request",request.digest(),"failure",error.toString()));throw error;
                    }
                },(event,request,response)->{
                    n.diagnostic(owner.activationIdentity().nodeId().value(),event,request,null);
                    if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(request,response));
                })) {
                link.set(transport);if(joiningService){assertEquals(MembershipEndpointHandoff.State.ACTIVE,joined.state());assertNotNull(joined.votingEndpoint());}
                assertTrue(n.transports.get(2).usage().closed());probeOldLocks(n);
                new V53MembershipOwnershipTest().probe(config.replicaDirectory().resolve("replica.lock"));
                MembershipRoundDriver.Events roundEvents=(event,record)->{
                    events.add(Map.of("event",event,"bytes",Base64.getEncoder().encodeToString(record.bytes()),"sha256",record.digest()));
                    if(event.equals("INSTALLED")) {
                        assertEquals(Set.of("node-1","node-2","node-4"),list(record.value().get("sources")).stream()
                                .map(v->(String)object(v).get("voter")).collect(java.util.stream.Collectors.toSet()));
                        long index=number(object(record.value().get("cut")).get("index"));
                        for(int i=0;i<2;i++) {
                            assertArrayEquals(record.bytes(),n.owners.get(i).originalSelection().orElseThrow().bytes());
                            Files.write(n.f.raw.resolve("continuation-grants-"+index+"-node-"+(i+1)+".gsr"),
                                    AdmissionPaths.read(n.f.request.targets().get(i).replicaDirectory().resolve("grants.gsr"),MembershipGrantJournal.MAXIMUM));
                        }
                        assertArrayEquals(record.bytes(),owner.originalSelection().orElseThrow().bytes());
                        Files.write(n.f.raw.resolve("continuation-grants-"+index+"-node-4.gsr"),
                                AdmissionPaths.read(config.replicaDirectory().resolve("grants.gsr"),MembershipGrantJournal.MAXIMUM));
                        System.out.println("v53JoiningContinuation=installed cut="+object(record.value().get("cut")).get("index"));
                    }
                };
                MembershipSlotDriver.Events slotEvents=(event,record,voters)->{
                    if(event.equals("PUBLISHED"))System.out.println("v53JoiningContinuation=published index="+record.value().get("index"));
                };
                try(var coordinated=joiningService?new MembershipJointContinuation<>(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                        n.transports.getFirst(),temp.resolve("joining-coordinated-round"),System::nanoTime,budget,2,
                        builder().configuration(),n.f.request.targets().getFirst().materialization(),roundEvents,slotEvents):null;
                    var continuation=joiningService?null:new MembershipRoundDriver<>(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                        n.transports.getFirst(),temp.resolve("joining-native-round"),System::nanoTime,budget,2,
                        builder().configuration(),n.f.request.targets().getFirst().materialization(),roundEvents,slotEvents)) {
                    var barrier=joiningService?coordinated.start():continuation.start();
                    if(joiningService){assertEquals(MembershipJointContinuation.State.READY,coordinated.state());assertArrayEquals(barrier.bytes(),coordinated.readiness().bytes());}
                    else {assertEquals(MembershipRoundDriver.State.READY,continuation.state());assertArrayEquals(barrier.bytes(),continuation.readiness().bytes());}
                    var context=n.owners.getFirst().activationContext();assertEquals(stableIndex,number(context.cut.get("index")));
                    assertNull(context.view.get("operation"));assertEquals(context.view.get("old"),context.view.get("new"));
                    assertEquals(Set.of("node-1","node-2","node-3","node-4"),context.voters());
                    assertEquals(context.cut,n.owners.get(1).activationContext().cut);assertEquals(context.cut,owner.activationContext().cut);
                    assertEquals(0L,number(n.owners.get(2).activationContext().cut.get("index")));assertTrue(n.transports.get(2).usage().closed());
                    assertEquals("COMPLETED",object(list(context.catalog.get("results")).getFirst()).get("phase"));
                    owner.peerRetentionState();owner.learnerRetentionState();owner.futureRetentionState();
                    result.put("status","CONTINUED");result.put("cut",context.cut);result.put("catalog",n.owners.getFirst().activationCapsule().terminal().catalog());
                    result.put("barrier",Base64.getEncoder().encodeToString(barrier.bytes()));result.put("actualNewVoter","node-4");
                    result.put("offlineOldVoter","node-3");result.put("automaticFinalAndBarrier",true);result.put("coordinatedPreparationAndCompletion",joiningService);
                    probeOldLocks(n);new V53MembershipOwnershipTest().probe(config.replicaDirectory().resolve("replica.lock"));
                }
            }
        }catch(Exception|Error error){result.put("status","FAIL");result.put("failure",error.toString());throw error;}
        finally {
            joinedSnapshot(plan,config.materialization().directory(),n.f.raw.resolve("joining-originals-continuation"));
            Files.write(n.f.raw.resolve("joining-continuation-wire.json"),canonical(wire,16*1024*1024));
            Files.write(n.f.raw.resolve("joining-continuation-events.json"),canonical(events,1024*1024));
            Files.write(n.f.raw.resolve("joining-continuation-failures.json"),canonical(failures,1024*1024));
            Files.write(n.f.raw.resolve("joining-continuation-result.json"),canonical(result,65536));
        }
        assertEquals(0,resources.usage().leases());
        try(var owner=MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{})) {
            assertEquals(stableIndex,number(owner.activationContext().cut.get("index")));owner.peerRetentionState();owner.learnerRetentionState();owner.futureRetentionState();
        }catch(Exception|Error error){result.put("status","FAIL");result.put("failure",error.toString());
            Files.write(n.f.raw.resolve("joining-continuation-result.json"),canonical(result,65536));throw error;
        }
        assertEquals(0,resources.usage().leases());result.put("status","PASS");result.put("stableColdReopened",true);
        Files.write(n.f.raw.resolve("joining-continuation-result.json"),canonical(result,65536));
        System.out.println("v53JoiningContinuation=stable-cold-reopened");
    }
    private static byte[] seedFrom(Path raw)throws Exception {return Files.readAllBytes(raw.resolve("joining-retention-seed.json"));}
    private static void assertJoinedRetention(MembershipGrantJournal journal,byte[] raw,MembershipIdentity identity)throws Exception {
        var copy=journal.floorCopyCurrent();var seed=MembershipJoiningRetentionSeed.read(raw,copy.capsule,copy.fileBytes("ancestry.gsr"),identity);
        var peers=journal.peerRetentionState();var learner=journal.learnerRetentionState();var future=journal.futureRetentionState();
        assertEquals(0,peers.revision());assertEquals(0,learner.revision());assertEquals(0,future.revision);assertFalse(future.pending());
        assertArrayEquals(seed.peers.bytes(),peers.plan().bytes());assertArrayEquals(seed.learner.bytes(),learner.plan().bytes());
    }
    private static void initializeRetention(MembershipLearnerPlan plan,MembershipResources resources,
            MembershipReplicaConfig<Integer,Doc> config,List<MembershipSelection.Source> originals,
            MembershipJoiningRetentionSeed seed,Path raw)throws Exception {
        var cuts=List.of("JOINING_RETENTION_SEED_PREFIX_WRITTEN","JOINING_RETENTION_PEERS_PREFIX_WRITTEN",
                "JOINING_RETENTION_FUTURE_PREFIX_WRITTEN","JOINING_RETENTION_LEARNER_PREFIX_WRITTEN",
                "JOINING_RETENTION_DONE_PREFIX_WRITTEN","JOINING_RETENTION_DONE_RENAMED");
        var observations=new ArrayList<Object>();Path directory=plan.request().replicaDirectory();
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{}));
        for(int i=0;i<cuts.size();i++) {
            String point=cuts.get(i);var hit=new java.util.concurrent.atomic.AtomicBoolean();boolean resumed=i>0;
            var failure=assertThrows(java.io.IOException.class,()->{
                MembershipBallotAllocator.Cut injection=event->{
                    if(event.equals(point)){hit.set(true);throw new java.io.IOException("test interruption: "+point);}
                };
                try(var journal=resumed?MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,injection):
                        MembershipGrantJournal.reopenJoined(plan,resources,builder().configuration(),config,injection)) {journal.initializeJoinedRetention(originals);}
            });
            assertTrue(hit.get(),failure.toString());assertEquals("test interruption: "+point,failure.getMessage());
            assertEquals(0,resources.usage().leases());
            var files=new TreeMap<String,Object>();
            try(var paths=Files.list(directory)) {for(Path path:paths.toList())if(path.getFileName().toString().contains("retention")) {
                byte[] bytes=Files.readAllBytes(path);files.put(path.getFileName().toString(),Map.of("size",(long)bytes.length,"sha256",hash(bytes),
                        "key",MembershipBasisSources.key(path).toString()));
            }}
            observations.add(Map.of("cut",point,"files",files.entrySet().stream().map(row->{
                var value=new TreeMap<>(object(row.getValue()));value.put("name",row.getKey());return value;
            }).toList()));
            if(i==0) {
                try(var journal=MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{})) {
                    assertFalse(Files.exists(directory.resolve(MembershipJoiningRetentionFiles.FILE)));
                    assertThrows(IllegalArgumentException.class,()->journal.initializeJoinedRetention(List.of(originals.getFirst())));
                    assertThrows(IllegalArgumentException.class,journal::reserveCounter);
                }
                assertEquals(files.get(MembershipJoiningRetentionFiles.NEXT),Map.of("size",Files.size(directory.resolve(MembershipJoiningRetentionFiles.NEXT)),
                        "sha256",hash(Files.readAllBytes(directory.resolve(MembershipJoiningRetentionFiles.NEXT))),
                        "key",MembershipBasisSources.key(directory.resolve(MembershipJoiningRetentionFiles.NEXT)).toString()));
            }
            System.out.println("v53JoiningRetentionRecoveredCut="+point);
        }
        try(var journal=MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{})) {
            assertJoinedRetention(journal,seed.bytes(),config.localIdentity());
            assertThrows(IllegalArgumentException.class,()->journal.initializeJoinedRetention(originals));
            new V53MembershipOwnershipTest().probe(directory.resolve("replica.lock"));
        }
        // Completion forbids reconstructing a lost ledger, even before the
        // first counter. Move and restore the original inode only while closed.
        var required=List.of(MembershipPeerRetentionFiles.FILE,MembershipFutureRetentionFiles.FILE,MembershipLearnerRetentionFiles.FILE);
        for(String name:required) {
            Path active=directory.resolve(name),held=raw.resolve("held-original-"+name);
            Files.move(active,held);try {
                var failure=assertThrows(ReplicationException.class,()->MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{}));
                assertEquals(ReplicationException.Reason.STORAGE_FAILURE,failure.reason());
                assertFalse(Files.exists(active));assertEquals(0,resources.usage().leases());
            }finally{Files.move(held,active);}
        }
        var all=new ArrayList<>(required);all.add(MembershipJoiningRetentionFiles.FILE);all.add(MembershipJoiningRetentionFiles.DONE);
        for(String name:all)Files.move(directory.resolve(name),raw.resolve("held-original-"+name));
        try {
            var failure=assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.reopenJoinedRetaining(plan,resources,builder().configuration(),config,e->{}));
            assertEquals("joining retention original decision missing",failure.getMessage());assertEquals(0,resources.usage().leases());
            for(String name:all)assertFalse(Files.exists(directory.resolve(name)));
        }finally{for(String name:all)Files.move(raw.resolve("held-original-"+name),directory.resolve(name));}
        Files.write(raw.resolve("joining-retention-initialization-cuts.json"),canonical(observations,1024*1024));
    }
    /** Retain actual predecessor/native files for later independent replay.
     * Shared read descriptors preserve live POSIX ownership during capture. */
    private static void joinedSnapshot(MembershipLearnerPlan plan,Path materialization,Path output)throws Exception {
        Files.createDirectory(output);var roots=new TreeMap<>(MembershipLearnerPlacement.originalRoots(plan));
        roots.put("custody",MembershipLearnerCustody.directory(plan));roots.put("placement",MembershipLearnerPlacement.directory(plan));
        roots.put("retirement",MembershipLearnerJoinedRetirement.directory(plan));roots.put("nativeOwner",MembershipJoinedOwner.directory(plan));roots.put("materialization",materialization);
        var inventory=MembershipLearnerCustody.capture(roots,null);
        for(var row:roots.entrySet())if(Files.exists(row.getValue())) {
            Path destination=Files.createDirectory(output.resolve(row.getKey()));
            try(var paths=Files.walk(row.getValue())) {
                for(Path source:paths.toList()) {
                    Path to=destination.resolve(row.getValue().relativize(source));
                    if(Files.isDirectory(source)){if(!Files.exists(to))Files.createDirectory(to);}
                    else try(var input=MembershipFileAccess.open(source,StandardOpenOption.READ);
                            var target=java.nio.channels.FileChannel.open(to,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                        var buffer=java.nio.ByteBuffer.allocate(65536);
                        while(input.read(buffer)>0){buffer.flip();while(buffer.hasRemaining())target.write(buffer);buffer.clear();}
                    }
                }
            }
        }
        assertEquals(inventory,MembershipLearnerCustody.capture(roots,null));
        Files.write(output.resolve("inventory.json"),canonical(inventory,1024*1024));
    }
    private void guardChecks(V53NativeDispatchTest.Network n,MembershipLearnerRequest request,Decoded first)throws Exception {
        var owner=n.owners.getFirst();var resources=n.resources.getFirst();var joining=request.identity();
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        while(n.transports.stream().anyMatch(t->{var u=t.usage();return u.outgoing()!=0 || u.incoming()!=0 || u.sockets()!=0;})) {
            assertTrue(System.nanoTime()<end,"native transfer drain before exact accounting");Thread.sleep(10);
        }
        var before=resources.usage();var wrong=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,wrong,System::nanoTime,0,BUDGET));
        assertEquals(0,wrong.usage().leases());
        assertThrows(IllegalArgumentException.class,()->owner.joiningIntent(n.owners.get(1).activationIdentity()));
        var changed=new TreeMap<>(first.value());changed.put("ballot",n.ballot);
        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,decode(encode("wire","CHUNK",changed),"wire","CHUNK"),
                resources,System::nanoTime,System.nanoTime(),BUDGET));
        var expired=new AtomicLong(0);
        try(var export=new MembershipJoiningIntentExport(owner,joining,first,resources,expired::get,0,10)) {
            expired.set(10);assertThrows(IllegalArgumentException.class,export::references);
        }
        var exports=new ArrayList<MembershipJoiningIntentExport>();
        try {
            // The real maintenance service may still own current-generation
            // borrows. Fill the remaining shared capacity, not six new slots.
            for(int i=0;i<6;i++) {
                var at=resources.usage();
                try {exports.add(new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET));}
                catch(IllegalArgumentException full) {
                    assertEquals("prefix export owner capacity",full.getMessage());assertEquals(at,resources.usage());break;
                }
            }
            assertFalse(exports.isEmpty());
            var full=resources.usage();
            assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET));
            assertEquals(full,resources.usage());
        }finally{for(var export:exports)export.close();}
        assertEquals(before,resources.usage());
        try(var export=new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET)) {
            var content=export.references().values().iterator().next();
            assertThrows(IllegalArgumentException.class,()->export.read("0".repeat(64),0,1));
            assertThrows(IllegalArgumentException.class,()->export.read(content.digest(),content.bytes(),1));
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);
            assertThrows(IllegalArgumentException.class,export::references);
            assertThrows(IllegalArgumentException.class,()->export.read(content.digest(),0,1));
        }
    }
}
