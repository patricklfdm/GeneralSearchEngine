package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Completed control bytes remain owned by every admitted response caller. */
class V53ActivationControlCustodyTest {
    @TempDir Path temp;
    @Test void failedCloseKeepsRetiredReplyBytesUntilItsCancelledCallerUnwinds()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var gate=new V53ActivationCloseDrainTest.Gate();var callers=Executors.newVirtualThreadPerTaskExecutor()) {
            local.endpoint.close();var stopped=new AtomicBoolean();Path scratch=temp.resolve("closing-custody");
            LongSupplier clock=()->{
                if(Thread.currentThread().getName().equals("retired-close-caller") &&
                        StackWalker.getInstance().walk(frames->frames.anyMatch(f->f.getMethodName().equals("completed"))) &&
                        stopped.compareAndSet(false,true))gate.stop();return 0;
            };
            try(var endpoint=V53ActivationCloseDrainTest.endpoint(local,scratch,clock,false)) {
                var request=local.prepare();var call=callers.submit(()->{Thread.currentThread().setName("retired-close-caller");
                    return endpoint.handle(local.proposer(),request);});
                try {
                    gate.reached();var values=new TreeMap<>(request.value());values.put("trace",UUID.randomUUID().toString());
                    var next=decode(encode("wire","PREPARE",values),"wire","PREPARE");var response=endpoint.handle(local.proposer(),next);
                    var failure=assertThrows(IOException.class,endpoint::close);
                    assertTrue(V53SlotCloseDrainTest.contains(failure,"activation caller close timeout"));V53ActivationCloseDrainTest.locked(scratch);
                    long held=local.base.peerResources.usage().queued();gate.close();
                    assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
                    // Both correlated promises retain the same basis and byte
                    // width; only their fixed-width UUID traces differ.
                    assertEquals(held-request.size()-response.size(),local.base.peerResources.usage().queued());
                    assertEquals(0,endpoint.usage().waiters());endpoint.close();V53ActivationCloseDrainTest.unlocked(scratch);
                }finally{gate.close();try{call.get(10,TimeUnit.SECONDS);}catch(ExecutionException expected){/* revoked caller */}}
            }
        }
    }
    @ParameterizedTest @ValueSource(ints={1,2})
    void replacedControlKeepsItsBytesUntilTheLastOriginalReplyReturns(int duplicates)throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var firstGate=new V53ActivationCloseDrainTest.Gate();
                var secondGate=new V53ActivationCloseDrainTest.Gate();var callers=Executors.newVirtualThreadPerTaskExecutor()) {
            local.endpoint.close();var entered=new ConcurrentHashMap<String,Boolean>();
            LongSupplier clock=()->{
                String name=Thread.currentThread().getName();
                if(name.startsWith("held-reply-") && StackWalker.getInstance().walk(frames->frames.anyMatch(
                        f->f.getClassName().endsWith("MembershipActivationEndpoint$Scope") && f.getMethodName().equals("completed"))) &&
                        entered.putIfAbsent(name,true)==null) {
                    if(name.equals("held-reply-0"))firstGate.stop();else secondGate.stop();
                }
                return 0;
            };
            try(var endpoint=V53ActivationCloseDrainTest.endpoint(local,temp.resolve("custody"),clock,false)) {
                var request=local.prepare();var replies=new ArrayList<Future<Decoded>>();
                try {
                    for(int i=0;i<duplicates;i++) {
                        int n=i;replies.add(callers.submit(()->{Thread.currentThread().setName("held-reply-"+n);return endpoint.handle(local.proposer(),request);}));
                        (i==0?firstGate:secondGate).reached();
                    }
                    var before=local.base.peerResources.usage();assertFalse(endpoint.usage().controlRunning());
                    assertEquals(duplicates,endpoint.usage().waiters());
                    var values=new TreeMap<>(request.value());values.put("trace",UUID.randomUUID().toString());
                    var next=decode(encode("wire","PREPARE",values),"wire","PREPARE");var response=endpoint.handle(local.proposer(),next);
                    assertEquals("PROMISE",response.kind());long added=next.size()+(long)response.size();
                    var after=local.base.peerResources.usage();
                    assertEquals(before.counts().get(MembershipResources.Unit.CONTROL)+1,after.counts().get(MembershipResources.Unit.CONTROL),
                            "retiring the cache must not release bytes still held by the old response caller");
                    assertEquals(before.queued()+added,after.queued());
                    firstGate.close();var original=replies.getFirst().get(10,TimeUnit.SECONDS);
                    if(duplicates==2) {
                        assertEquals(after.queued(),local.base.peerResources.usage().queued(),"first duplicate cannot release the second caller's bytes");
                        assertEquals(1,endpoint.usage().waiters());secondGate.close();
                        assertArrayEquals(original.bytes(),replies.get(1).get(10,TimeUnit.SECONDS).bytes());
                    }
                    assertEquals(after.queued()-request.size()-original.size(),local.base.peerResources.usage().queued());
                    assertEquals(before.counts().get(MembershipResources.Unit.CONTROL),local.base.peerResources.usage().counts().get(MembershipResources.Unit.CONTROL));
                    assertEquals(0,endpoint.usage().waiters());assertArrayEquals(response.bytes(),endpoint.handle(local.proposer(),next).bytes());
                }finally {
                    firstGate.close();secondGate.close();for(var reply:replies)reply.get(10,TimeUnit.SECONDS);
                }
            }
        }
    }
}
