package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual production endpoint decorators must retain socket observations while
 * preserving the post-hook custody check. Historical authority is a fixture. */
class V53LearnerEndpointConnectionTest {
    @TempDir Path temp;
    record Seen(String event,Decoded request,MembershipTransport.Connection connection) {}
    @FunctionalInterface interface Hook {void run(String event)throws IOException;}
    static final class Observer implements MembershipTransport.Events {
        final List<Seen> seen=new CopyOnWriteArrayList<>();
        final CompletableFuture<MembershipTransport.Reason> terminal=new CompletableFuture<>();
        final Hook hook;
        Observer(){this(event->{});}
        Observer(Hook hook){this.hook=hook;}
        @Override public void at(String event,Decoded request,Decoded response)throws IOException {at(event,request,response,null);}
        @Override public void at(String event,Decoded request,Decoded response,MembershipTransport.Connection connection)throws IOException {
            seen.add(new Seen(event,request,connection));hook.run(event);
        }
        @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason) {failed(outbound,request,reason,null);}
        @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason,MembershipTransport.Connection connection) {
            seen.add(new Seen(outbound?"OUTBOUND_FAILURE":"INBOUND_FAILURE",request,connection));terminal.complete(reason);
        }
        MembershipTransport.Connection invocation(Decoded request,String... events) {
            var rows=seen.stream().filter(v->v.request()!=null && v.request().digest().equals(request.digest())).toList();
            assertEquals(List.of(events),rows.stream().map(Seen::event).toList());
            var original=rows.getFirst().connection();assertNotNull(original,"endpoint dropped original connection");
            rows.forEach(row->assertSame(original,row.connection(),"endpoint replaced original connection"));return original;
        }
    }
    static Decoded exchange(MembershipTransport client,MembershipIdentity peer,Decoded request,String response)throws Exception {
        return client.exchange(peer,request,response,System.nanoTime()+TimeUnit.SECONDS.toNanos(10)).get(15,TimeUnit.SECONDS);
    }
    static void rejected(MembershipTransport client,MembershipIdentity peer,Decoded request,String response,Observer server,MembershipTransport.Reason reason)throws Exception {
        var failure=assertThrows(ExecutionException.class,()->exchange(client,peer,request,response));
        assertEquals(MembershipTransport.Reason.IO,((MembershipTransport.Failure)failure.getCause()).reason);
        assertEquals(reason,server.terminal.get(5,TimeUnit.SECONDS));
    }
    static void sockets(Observer server,Observer client,Decoded request) {
        var receiver=server.invocation(request,"AFTER_REQUEST_READ","BEFORE_RESPONSE_WRITE");
        var sender=client.invocation(request,"BEFORE_REQUEST_WRITE","AFTER_RESPONSE_READ");
        assertNotEquals(receiver.id(),sender.id());assertEquals(receiver.local(),sender.remote());assertEquals(receiver.remote(),sender.local());
    }
    @Test void checkpointRepliesAndProtocolFailuresKeepTheOriginalConnection()throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var server=new Observer();var client=new Observer();
            try(var endpoint=f.listen(server);var contact=new MembershipTransport(f.source,f.reader,f.fixture.f.local.config.bounds(),f.fixture.f.peer.server,
                    (p,q)->{throw new IOException("read-only test contact");},client)) {
                var requests=new ArrayList<Decoded>();
                f.fetch((p,q,k,d)->{requests.add(q);return contact.exchange(p,q,k,d);});
                assertEquals(List.of("CHUNK","CHUNK","TRANSFER_COMMIT"),requests.stream().map(Decoded::kind).toList());
                for(var request:requests)sockets(server,client,request);
                assertEquals(3,requests.stream().map(q->server.invocation(q,"AFTER_REQUEST_READ","BEFORE_RESPONSE_WRITE").id()).distinct().count());
                var wrong=V53LearnerHeadProtocolTest.changed(f.first(),v->object(v.get("payload")).put("offset",1L));
                rejected(contact,f.local,wrong,"SOURCE_OFFER",server,MembershipTransport.Reason.PROTOCOL);
                server.invocation(wrong,"AFTER_REQUEST_READ","INBOUND_FAILURE");
            }
        }
    }
    @Test void checkpointConnectionHookStillRevokesReplyAfterOwnerClose()throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var server=new Observer(event->{if(event.equals("BEFORE_RESPONSE_WRITE"))f.pending.close();});
            try(var endpoint=f.listen(server);var contact=f.contact()) {
                var request=f.first();rejected(contact,f.local,request,"SOURCE_OFFER",server,MembershipTransport.Reason.CLOSED);
                server.invocation(request,"AFTER_REQUEST_READ","BEFORE_RESPONSE_WRITE","INBOUND_FAILURE");
                f.pending.close();
                assertTrue(endpoint.closed());
            }
        }
    }
    @Test void headRepliesAndProtocolFailuresKeepTheOriginalConnection()throws Exception {
        head(false);
    }
    @Test void headConnectionHookStillRevokesReplyAfterOwnerClose()throws Exception {
        head(true);
    }
    private void head(boolean close)throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(event->{})) {
            var head=typed.retainGeneration();var voter=f.source.owner.activationIdentity();var client=new Observer();
            var server=new Observer(event->{if(close && event.equals("BEFORE_RESPONSE_WRITE"))typed.close();});
            try(var endpoint=new MembershipLearnerHeadEndpoint(head,V53SourceExchangeTest.bounds(),server);
                var contact=new MembershipTransport(head.source(),voter,V53SourceExchangeTest.bounds(),f.source.server,
                        (p,q)->{throw new IOException("read-only test contact");},client)) {
                var request=V53LearnerHeadProtocolTest.query(head,voter);
                if(close) {
                    rejected(contact,head.request().identity(),request,"LEARNER_HEAD_ACK",server,MembershipTransport.Reason.PROTOCOL);
                    server.invocation(request,"AFTER_REQUEST_READ","BEFORE_RESPONSE_WRITE","INBOUND_FAILURE");
                }else {
                    assertEquals("LEARNER_HEAD_ACK",exchange(contact,head.request().identity(),request,"LEARNER_HEAD_ACK").kind());
                    sockets(server,client,request);
                    var wrong=V53LearnerHeadProtocolTest.changed(request,v->v.put("sequence",2L));
                    rejected(contact,head.request().identity(),wrong,"LEARNER_HEAD_ACK",server,MembershipTransport.Reason.PROTOCOL);
                    server.invocation(wrong,"AFTER_REQUEST_READ","INBOUND_FAILURE");
                }
            }
        }
    }
}
