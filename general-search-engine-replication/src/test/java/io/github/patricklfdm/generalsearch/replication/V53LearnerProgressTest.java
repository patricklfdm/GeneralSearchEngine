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
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Actual source transfer/storage, conditional historical voter observations.
 * These tests do not establish native cancellation, admission or joint votes. */
class V53LearnerProgressTest {
    @TempDir Path temp;
    V53LearnerSourceTest helper(){var h=new V53LearnerSourceTest();h.temp=temp;return h;}
    static V53CapsuleFixture cancelled(int size,String kind,int at) {
        return cancelled(new V53CapsuleFixture(size,kind,at),at);
    }
    static V53CapsuleFixture cancelled(V53CapsuleFixture original,int at) {
        var history=original.source;
        history.state=object(V53ContextFixture.mutable(original.state(at)));
        history.steps.subList(at,history.steps.size()).clear();
        history.commit("CANCEL",Map.of("number",1L),()->{
            history.operation().put("phase","CANCELLED");history.operation().put("terminalIndex",number(object(history.state.get("cut")).get("index")));
            history.state.put("active",null);
        });
        return V53CapsuleFixture.fromHistory(history,at+1);
    }
    MembershipSourcePull pull(V53LearnerSourceTest.Fixture f,MembershipSourcePull.Link link) {
        return MembershipSourcePull.learnerProgress(f.request,f.fixture.fixture.source.root,f.hint,f.client,bounds(),(p,r,k,d)->{
            f.sent.add(r);return link.exchange(p,r,k,d);
        },()->{},f.clock::get,0,BUDGET);
    }
    MembershipSourcePull pull(V53LearnerSourceTest.Fixture f){return pull(f,f::deliver);}
    @Test void allFiveJoiningProfilesReadPreparedJointFinalAndCancelledWithoutChangingTheOwner()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            var histories=new ArrayList<V53CapsuleFixture>();
            for(int cut:List.of(3,4,5,6,7,8))histories.add(new V53CapsuleFixture(size,kind,cut));
            histories.add(cancelled(size,kind,3));histories.add(cancelled(size,kind,4));
            for(var history:histories)try(var f=helper().new Fixture(size,kind,history);var prefix=pull(f);var generation=pull(f)) {
                var before=V53ReplayFilesTest.files(f.path);prefix.fetchPrefix(temp.resolve("progress-"+UUID.randomUUID()));
                var copy=generation.fetchGeneration(prefix);var original=f.owner.floorCopyCurrent();
                assertArrayEquals(original.generation.bytes(),copy.generation.bytes());assertEquals(original.fileNames(),copy.fileNames());
                for(String name:original.fileNames())assertArrayEquals(original.fileBytes(name),copy.fileBytes(name),name);
                assertEquals(before,V53ReplayFilesTest.files(f.path));assertFalse(Files.exists(f.request.replicaDirectory()));assertFalse(Files.exists(f.request.operationDirectory()));
                var usage=f.client.usage();assertEquals(1,usage.counts().get(MembershipResources.Unit.LEARNER));
                assertFalse(usage.counts().containsKey(MembershipResources.Unit.GENERATION));
                assertThrows(IllegalArgumentException.class,()->prefix.completeLearnerSource(copy,e->{throw new AssertionError("read-only progress forced admission");}));
                assertEquals(usage,f.client.usage());assertThrows(IllegalArgumentException.class,prefix::verifiedOriginalSource);
            }
        }
    }
    @Test void ordinaryEnrollmentRemainsUnavailableAfterIntentOrCancellation()throws Exception {
        for(var history:List.of(new V53CapsuleFixture(3,"ADD",6),new V53CapsuleFixture(3,"ADD",7),cancelled(3,"ADD",3)))
            try(var f=helper().new Fixture(3,"ADD",history);var prefix=f.pull()) {
                assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("old-route-"+UUID.randomUUID())));
                assertEquals(1,f.sent.size());assertFalse(Files.exists(f.request.replicaDirectory()));
            }
    }
    @Test void missingRetiredUnpreparedAndChangedRequestsCannotUseTheProgressRoute()throws Exception {
        for(int cut:List.of(0,1,2,9))try(var f=helper().new Fixture(3,"ADD",cut);var prefix=pull(f)) {
            assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("absent-"+cut)));assertEquals(1,f.sent.size());
        }
        try(var f=helper().new Fixture(3,"ADD",6)) {
            for(String variant:List.of("number","expected","identity","cut")) {
                var change=f.request.change();var identity=f.request.identity();
                if(variant.equals("identity"))identity=new MembershipIdentity(identity.nodeId(),UUID.randomUUID(),identity.endpoint());
                var target=new ArrayList<>(change.target());if(variant.equals("identity"))target.set(target.size()-1,identity);
                var changed=new MembershipLearnerRequest(f.request.root(),identity,new MembershipChangeRequest(
                        new MembershipOperationId(f.request.root(),variant.equals("number")?2:1),variant.equals("expected")?"ab".repeat(32):change.expectedConfigurationDigest(),
                        change.kind(),target),f.request.replicaDirectory(),f.request.operationDirectory());
                var cut=new TreeMap<>(f.hint.cut());if(variant.equals("cut"))cut.put("index",number(cut.get("index"))+1);
                try(var prefix=MembershipSourcePull.learnerProgress(changed,f.fixture.fixture.source.root,new MembershipDiscovery.Hint(f.hint.peer(),cut,false),
                        f.client,bounds(),f::deliver,()->{},f.clock::get,0,BUDGET)) {
                    assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("wrong-"+variant)),variant);
                }
            }
        }
    }
    @Test void lostRepliesRetryTheSameFrameAndPermanentErrorsDoNotRetry()throws Exception {
        for(String mode:List.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT","exhausted","permanent"))
            try(var f=helper().new Fixture(3,"ADD",cancelled(3,"ADD",4))) {
                var lost=new AtomicBoolean();
                try(var prefix=pull(f,(p,r,k,d)->{
                    if(mode.equals("exhausted") || mode.equals("permanent"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(
                            mode.equals("permanent")?MembershipTransport.Reason.PROTOCOL:MembershipTransport.Reason.IO,"injected",null));
                    return f.deliver(p,r,k,d).thenCompose(reply->mode.equals(k) && lost.compareAndSet(false,true)?
                            CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null)):CompletableFuture.completedFuture(reply));
                })) {
                    Path path=temp.resolve("loss-"+mode);
                    if(mode.equals("exhausted") || mode.equals("permanent")) {
                        assertThrows(IOException.class,()->prefix.fetchPrefix(path));assertEquals(mode.equals("permanent")?1:3,f.sent.size());
                        assertEquals(1,f.sent.stream().map(Decoded::digest).distinct().count());
                    }else {prefix.fetchPrefix(path);prefix.verifiedPrefix();assertTrue(lost.get());assertEquals(1,f.sent.size()-f.sent.stream().map(Decoded::digest).distinct().count());}
                }
            }
    }
    @Test void originalDeadlineAndCallerCloseRevokeIncompleteProgress()throws Exception {
        try(var f=helper().new Fixture(3,"ADD",6);var prefix=pull(f)) {
            f.clock.set(BUDGET);assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("expired")));assertTrue(f.sent.isEmpty());
        }
        try(var f=helper().new Fixture(3,"ADD",6)) {
            var holder=new AtomicReference<MembershipSourcePull>();var pending=new CompletableFuture<Decoded>();
            try(var prefix=pull(f,(p,r,k,d)->{try{holder.get().close();}catch(IOException e){throw new UncheckedIOException(e);}return pending;})) {
                holder.set(prefix);assertThrows(IOException.class,()->prefix.fetchPrefix(temp.resolve("closed")));assertTrue(pending.isCancelled());
            }
        }
    }
    @Test void progressAndEnrollmentCannotMixPrefixOwnership()throws Exception {
        try(var f=helper().new Fixture(3,"ADD",3);var prefix=pull(f);var other=f.pull()) {
            prefix.fetchPrefix(temp.resolve("progress"));assertThrows(IllegalArgumentException.class,()->other.fetchGeneration(prefix));
        }
        try(var f=helper().new Fixture(3,"ADD",3);var prefix=f.pull();var other=pull(f)) {
            prefix.fetchPrefix(temp.resolve("admission"));assertThrows(IllegalArgumentException.class,()->other.fetchGeneration(prefix));
        }
    }
}
