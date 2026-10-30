package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Deliberately conditional alternative old-quorum histories; real original
 * pending owners and complete TCP receives. These are not native elections. */
class V53PendingPublishedValueTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final V53LearnerPendingIntentTest.Fixture f;
        final MembershipLearnerPendingIntent pending;
        final MembershipLearnerDisposition.RetainedSource retained;
        final V53LearnerProgressNetworkTest.Peer peer;
        final MembershipTransport server;
        final boolean recertified;
        Fixture(boolean recertified)throws Exception {
            this.recertified=recertified;var helper=new V53LearnerPendingIntentTest();helper.temp=temp;f=helper.new Fixture();
            pending=f.retain(e->{});pending.endorse();retained=pending.retainSource();f.server.close();
            var history=f.f.local.source.fixture.fixture.source;
            var before=decode(history.inventory.get((String)history.steps.get(5).get("catalogBefore")),"records","CATALOG");
            var context=new MembershipContext(history.root,before,object(before.value().get("cut")),history.inventory,history.images);
            if(recertified) {
                var step=history.steps.get(5);var fields=new TreeMap<>(decode(history.inventory.get((String)step.get("accept")),"records","ACCEPT").value());
                fields.put("ballot",history.ballot(2));String parent=MembershipContext.cutDigest(object(before.value().get("cut")));
                var accept=history.record("ACCEPT",fields);fields.put("accepts",history.witnesses(context,"ACCEPT",accept.digest(),parent));
                var proof=history.record("PROOF",fields);fields.put("proofs",history.witnesses(context,"PROOF",proof.digest(),parent));
                var certificate=history.record("CERTIFICATE",fields);
                new MembershipContext(history.root,before,object(before.value().get("cut")),history.inventory,history.images).certificate(certificate,history.owned);
                step.put("accept",accept.digest());step.put("proof",proof.digest());step.put("certificate",certificate.digest());
            }else {
                // Another internally valid conditional history has a barrier
                // before INTENT. Same typed receipt is insufficient: its ENTRY
                // and checkpoint are not the ones the pending owner ACKed.
                history.state=object(mutable(before.value()));history.steps.subList(5,history.steps.size()).clear();
                history.commit("BARRIER",null,()->{});var row=history.operation();
                var descriptor=map("request",row.get("request"),"prepared",row.get("prepared"),"receipt",row.get("receipt"));
                history.commit("INTENT",map("sealed",descriptor),()->{
                    history.operation().put("phase","JOINT");var view=object(object(history.state.get("cut")).get("view"));
                    view.put("new",names(history.target));view.put("operation",history.operation().get("binding"));
                });
            }
            var network=new V53LearnerProgressNetworkTest();network.temp=temp;
            var complete=V53CapsuleFixture.fromHistory(history,recertified?6:7);complete.verify();
            peer=recertified?network.new Peer(complete,true):network.new Peer(complete,List.of(
                    V53LearnerProgressNetworkTest.bridge(complete,3,6),V53LearnerProgressNetworkTest.bridge(complete,5,6)));
            server=new MembershipTransport(peer.owner,f.f.local.config.bounds(),peer.server,(sender,request)->request.kind().equals("STATUS_PROBE")?
                    MembershipDiscovery.answer(peer.owner.activationContext(),peer.owner.activationIdentity(),sender,request):peer.service.handle(sender,request),MembershipTransport.Events.NONE);
        }
        MembershipLearnerProgress progress()throws Exception{return new MembershipLearnerProgress(retained,peer.owner.activationIdentity(),f.f.local.config.bounds(),
                MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),TimeUnit.MINUTES.toNanos(2));}
        @Override public void close()throws Exception{server.close();peer.close();pending.close();f.close();}
    }
    @Test void laterValidCertificateForTheSameOriginalEntryAndCheckpointIsAccepted()throws Exception {
        try(var f=new Fixture(true);var progress=f.progress()) {
            var old=f.pending.originals();var copy=progress.fetch(f.f.f.local.base.resolve("recertified"));
            var item=list(copy.capsule.packet.capsule().value().get("items")).stream().map(MembershipFormat::object).filter(v->v.get("kind").equals("MEMBERSHIP")).findFirst().orElseThrow();
            var certificate=copy.capsule.context.record((String)item.get("certificate"),"CERTIFICATE");
            assertNotEquals(old.record("CERTIFICATE").digest(),certificate.digest());assertEquals(2L,object(certificate.value().get("ballot")).get("counter"));
            assertEquals(old.record("ENTRY").digest(),certificate.value().get("entry"));assertEquals(old.record("CHECKPOINT").digest(),item.get("statement"));
        }
    }
    @Test void validDifferentIntentCannotConsumeTheOriginalPendingEnd()throws Exception {
        try(var f=new Fixture(false);var progress=f.progress()) {
            var original=V53ReplayFilesTest.files(f.f.directory());var usage=f.f.f.local.source.client.usage();Path scratch=f.f.f.local.base.resolve("different");
            var error=assertThrows(IllegalArgumentException.class,()->progress.fetch(scratch));
            assertEquals("missing packet object",error.getMessage());assertFalse(Files.exists(scratch));
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertEquals(usage,f.f.f.local.source.client.usage());f.retained.check();
        }
    }
}
