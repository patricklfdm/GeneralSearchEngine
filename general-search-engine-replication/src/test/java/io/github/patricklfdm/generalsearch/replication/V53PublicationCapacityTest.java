package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Logical history is preconstructed; refusal and completion use actual storage owners. */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class V53PublicationCapacityTest {
    @TempDir static Path temp;
    V53ApplicationReplayTest application;
    V53EnvelopeHistoryFixture history;MembershipCapsule stable,ready,sealed;Path evidence;
    @BeforeAll void prefix()throws Exception {
        evidence=Path.of("target/v53-publication-capacity/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        System.out.println("v53PublicationCapacityEvidence="+evidence.toAbsolutePath());
        application=new V53ApplicationReplayTest();application.temp=temp;
        history=new V53EnvelopeHistoryFixture(application.initial(41),V53ApplicationImageTest.HISTORY,41);
        history.commit("BARRIER",null);for(int n=1;n<=232;n++) {history.change(n,true);if(n%32==0)System.out.println("v53CapacityPrefix="+n);}
        stable=history.verify();history.change(233,"READY");ready=history.verify();
        history.commit("SEAL",Map.of("number",233L));
        var operation=object(list(history.state.get("results")).getFirst());var descriptor=new TreeMap<String,Object>();
        for(String k:List.of("request","prepared","receipt"))descriptor.put(k,operation.get(k));
        history.commit("INTENT",Map.of("sealed",descriptor));history.commit("FINAL",Map.of("binding",operation.get("binding")));history.commit("RETIRE",Map.of("through",233L));
        history.change(234,"SEAL");sealed=history.verify();
    }
    @BeforeEach void progress(TestInfo info){System.out.println("v53CapacityCase="+info.getDisplayName());}
    @Test void reserveRefusesBeforeVotingAndStableWorkStillCompletes()throws Exception {
        var f=new V53EnvelopeOwnerFixture(temp.resolve("stable"),history,stable);f.evidence=evidence.resolve("reserve-refusal");
        var target=new ArrayList<Map<String,Object>>();for(int n=1;n<=4;n++)target.add(V53ContextFixture.member(n));target.add(V53ContextFixture.member(238));
        target.sort(Comparator.comparing(v->(String)v.get("node")));
        byte[] payload=command("RESERVE",Map.of("request",Map.of("root",f.root.manifestDigest(),"expected",stable.context.authority(),"number",233L,"kind","REPLACE","target",target)));
        f.refuse("RESERVE",payload);
        var after=f.publish("BARRIER",new byte[0],application);
        assertEquals(number(stable.context.cut.get("index"))+1,number(after.context.cut.get("index")));
        assertEquals(stable.context.catalog.get("applicationSequence"),after.context.catalog.get("applicationSequence"));
        f.maintain();try(var s=f.open(1)){assertEquals(after.context.cut,s.floorCopyCurrent().capsule.context.cut);}
    }
    @Test void legacySealedPrefixRefusesUnpublishableIntentBeforeVote()throws Exception {
        var f=new V53EnvelopeOwnerFixture(temp.resolve("sealed"),history,sealed);f.evidence=evidence.resolve("intent-refusal");var operation=object(list(sealed.context.catalog.get("results")).getFirst());
        var descriptor=new TreeMap<String,Object>();for(String k:List.of("request","prepared","receipt"))descriptor.put(k,operation.get(k));
        f.refuse("INTENT",command("INTENT",Map.of("sealed",descriptor)));
    }
    @Test void preSealCancellationRemainsAnEscapeWithoutInventingFutureMembership()throws Exception {
        var f=new V53EnvelopeOwnerFixture(temp.resolve("cancel"),history,ready);
        var after=f.publish("CANCEL",command("CANCEL",Map.of("number",233L)),application);
        assertNull(after.context.catalog.get("active"));assertEquals("CANCELLED",object(list(after.context.catalog.get("results")).getFirst()).get("phase"));
        assertEquals(ready.context.view,after.context.view);
    }
    @Test void frozenRecordSumsBoundTheNextActualCompletePacket() {
        var small=new V53EnvelopeHistoryFixture(history.seed.images.values().iterator().next(),V53ApplicationImageTest.HISTORY,41);
        small.commit("BARRIER",null);var before=small.verify();
        var reserved=MembershipPublicationCapacity.publication(before,null,"RESERVE",8192,0);
        small.change(1,true);var after=small.verify();
        assertTrue(reserved.fits());assertTrue(after.packet.envelope().length+HEADER<=reserved.envelope());
        assertTrue(after.packet.bytes().length<=reserved.packet());
        assertFalse(MembershipPublicationCapacity.publication(stable,null,"RESERVE",8192,0).fits());
        assertTrue(MembershipPublicationCapacity.publication(stable,null,"BARRIER",0,1).fits());
    }
    @Test void maximalFieldWidthsStillFitTheFrozenIndividualMembershipEdge() {
        // Encoded size only: repeated placeholder voters are not authority.
        String hash="f".repeat(64),node="n".repeat(64),uuid="ffffffff-ffff-4fff-8fff-ffffffffffff";
        var ballot=Map.of("counter",MembershipValidation.MAX,"proposer",node,"incarnation",uuid);
        var fields=new TreeMap<String,Object>(Map.of("root",hash,"authority",hash,"ballot",ballot,"index",MembershipValidation.MAX,"entry",hash));
        long bytes=encode("records","ACCEPT",fields).length;
        var witness=Map.of("voter",node,"incarnation",uuid,"receipt",hash);
        fields.put("accepts",Collections.nCopies(6,witness));bytes+=encode("records","PROOF",fields).length;
        fields.put("proofs",Collections.nCopies(6,witness));bytes+=encode("records","CERTIFICATE",fields).length;
        bytes+=encode("records","ENTRY",Map.of("root",hash,"authority",hash,"index",MembershipValidation.MAX,"previous",hash,"origin",ballot,"kind","INTENT","payload",hash)).length;
        // Both control and descriptor use their own frozen 8 KiB maximum;
        // statement + six ACKs use their complete frozen 16 KiB allowance.
        bytes+=2*8192+16*1024;
        assertTrue(bytes<=48*1024,"complete maximum-width edge: "+bytes);
    }
    @Test void pendingControlCompletionReservationNeverGrowsFromItsInitialBound() {
        var h=new V53EnvelopeHistoryFixture(history.seed.images.values().iterator().next(),V53ApplicationImageTest.HISTORY,41);
        h.commit("BARRIER",null);var original=MembershipPublicationCapacity.publication(h.verify(),null,"RESERVE",8192,0);
        h.change(1,"READY");var ready=h.verify();
        var preparing=MembershipPublicationCapacity.publication(ready,null,"SEAL",8192,0);
        h.commit("SEAL",Map.of("number",1L));var sealed=h.verify();
        var intent=MembershipPublicationCapacity.publication(sealed,null,"INTENT",8192,0);
        var operation=object(list(h.state.get("results")).getFirst());var descriptor=new TreeMap<String,Object>();
        for(String k:List.of("request","prepared","receipt"))descriptor.put(k,operation.get(k));
        h.commit("INTENT",Map.of("sealed",descriptor));var joint=h.verify();
        var finish=MembershipPublicationCapacity.publication(joint,null,"FINAL",8192,0);
        for(var remaining:List.of(preparing,intent,finish)) {
            assertTrue(remaining.envelope()<=original.envelope());assertTrue(remaining.packet()<=original.packet());
            assertTrue(remaining.generation()<=original.generation());assertTrue(remaining.fits());
        }
    }
    @Test void continuedRoundIncludesItsOriginalFirstProofAndDoesNotHideInvalidReferences() {
        var r=new V53RoundCoverageTest.Round();
        for(int n=0;n<3;n++){r.source.commit("BARRIER",null,()->{});r.next(n);}
        var retained=MembershipPublicationCapacity.publication(r.capsule,r.coverage,"BARRIER",0,2);
        var omitted=MembershipPublicationCapacity.publication(r.capsule,null,"BARRIER",0,2);
        assertTrue(retained.packet()>omitted.packet());assertTrue(retained.envelope()>omitted.envelope());
        byte[] unknown=canonical(Map.of("certificate","0".repeat(64)),4096);
        var error=assertThrows(IllegalArgumentException.class,()->MembershipPublicationCapacity.admits(r.capsule,unknown,"BARRIER",0,2));
        assertEquals("missing packet object",error.getMessage());
        r.source.commit("BARRIER",null,()->{});r.next(3);
        assertTrue(r.capsule.packet.bytes().length<=retained.packet());assertTrue(r.capsule.packet.envelope().length+HEADER<=retained.envelope());
    }
    @Test void ordinaryDataStillPublishesAfterNewMembershipCapacityIsExhausted()throws Exception {
        var f=new V53EnvelopeOwnerFixture(temp.resolve("data"),history,stable);
        assertFalse(MembershipPublicationCapacity.publication(stable,null,"RESERVE",8192,0).fits());
        byte[] payload;
        try(var encoder=application.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(20,"capacity-still-writable"))));
        }
        var after=f.publish("DATA",payload,application);
        assertEquals(number(stable.context.catalog.get("applicationSequence"))+1,number(after.context.catalog.get("applicationSequence")));
        assertEquals(stable.context.view,after.context.view);f.maintain();
        try(var owner=f.open(1)) {
            var original=owner.floorCopyCurrent();
            var loaded=application.read(original.fileBytes(original.capsule.terminal().application()+".image"),"capacity-final-data");
            assertTrue(loaded.documents().contains(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(20,"capacity-still-writable")));
            assertEquals(42,loaded.sequence());
        }
    }
}
