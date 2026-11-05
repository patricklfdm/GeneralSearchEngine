package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A real pending learner serves only its own forced checkpoint ACK. No vote,
 * selector, source/image transfer or public service is installed. Identity uses
 * the existing trusted-private-network boundary, not a new TLS credential. */
final class MembershipLearnerCheckpointEndpoint implements AutoCloseable {
    private record Key(MembershipIdentity reader,UUID trace) {}
    record Usage(int traces,int exports,boolean closed) {}
    private final MembershipLearnerDisposition.PendingCheckpoint original;
    private final MembershipResources resources;
    private final MembershipResources.Lease metadata;
    private final MembershipTransport transport;
    private final LongSupplier clock;
    private final long started,budget;
    private final int frameLimit,chunkLimit;
    private final Object guard=new Object();
    private final Map<Key,Entry> traces=new HashMap<>();
    private volatile boolean closed,released;
    private int exports;

    MembershipLearnerCheckpointEndpoint(MembershipLearnerDisposition.PendingCheckpoint original,ReplicationBounds bounds,
            MembershipTransport.Events events,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining checkpoint original budget");
        this.original=Objects.requireNonNull(original);this.resources=original.resources;
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        Objects.requireNonNull(events);Objects.requireNonNull(bounds);original.check();time();
        frameLimit=Math.min(FRAME,bounds.maxFrameBytes());chunkLimit=Math.min(4*1024*1024,bounds.snapshotChunkBytes());
        require(frameLimit>=4096 && chunkLimit>0,"joining checkpoint frame limits");
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-checkpoint-service-"+UUID.randomUUID(),32768);
        try {
            transport=new MembershipTransport(original.source,original.identity,bounds,resources,this::answer,new MembershipTransport.Events() {
                @Override public void at(String event,Decoded request,Decoded response)throws IOException {
                    events.at(event,request,response);afterObservation(event);
                }
                @Override public void at(String event,Decoded request,Decoded response,MembershipTransport.Connection connection)throws IOException {
                    events.at(event,request,response,connection);afterObservation(event);
                }
                private void afterObservation(String event)throws IOException {
                    // Preserve custody checking after the external hook in both overloads.
                    if(event.equals("BEFORE_RESPONSE_WRITE"))synchronized(guard){check();}
                }
                @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason)throws IOException {
                    events.failed(outbound,request,reason);
                }
                @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason,MembershipTransport.Connection connection)throws IOException {
                    events.failed(outbound,request,reason,connection);
                }
            });
        }catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
    }
    private boolean expired(){long elapsed=clock.getAsLong()-started;return elapsed<0 || elapsed>=budget;}
    private void time(){require(!closed && !expired(),"joining checkpoint original deadline/closed");}
    private void check()throws IOException {time();original.check();time();}
    private void envelope(MembershipIdentity reader,Decoded request) {
        var context=original.source.context;
        require(Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()) && request.size()<=frameLimit
                && context.voters().contains(reader.nodeId().value()),"joining checkpoint reader/kind");
        // Reading this already forced immutable end is not a new vote. A
        // legitimate later old-view campaign may read it too; each transfer
        // still freezes its own valid ballot and exact request correlation.
        context.wire(request,reader,original.identity,object(request.value().get("ballot")),UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
    }
    private void initial(Decoded request) {
        var payload=object(request.value().get("payload"));
        require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                && payload.get("action").equals("REQUEST") && number(payload.get("offset"))==0 && payload.get("bytes").equals("")
                && payload.get("digest").equals(original.acknowledgement.digest()),"joining checkpoint exact ACK reference");
    }
    private final class Export implements MembershipTransferExport {
        final MembershipResources.Lease lease;
        final byte[] bytes;
        final Map<String,MembershipSourceExport.Content> contents;
        final Map<String,Object> ballot;
        boolean stopped;
        Export(Map<String,Object> ballot)throws IOException {
            this.ballot=Map.copyOf(ballot);
            check();require(exports<MembershipResources.Unit.SOURCE.count,"joining checkpoint export capacity");
            lease=resources.reserve(MembershipResources.Unit.CONTROL,"joining-checkpoint-export-"+UUID.randomUUID(),original.acknowledgement.size());
            try {
                bytes=original.acknowledgement.bytes();contents=Map.of(original.acknowledgement.digest(),
                        new MembershipSourceExport.Content(original.acknowledgement.digest(),bytes.length,MembershipTransfer.Kind.RECORD));exports++;
            }catch(RuntimeException|Error error){lease.close();throw error;}
        }
        @Override public MembershipContext context(){return original.source.context;}
        @Override public MembershipIdentity identity(){return original.identity;}
        @Override public Map<String,Object> ballot(){return ballot;}
        @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
            synchronized(guard){require(!stopped,"joining checkpoint export closed");check();return contents;}
        }
        @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
            synchronized(guard) {
                references();require(contents.containsKey(digest) && offset>=0 && offset<bytes.length && maximum>0 && maximum<=4*1024*1024,
                        "joining checkpoint exact extent");
                int start=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,start,start+(int)Math.min(maximum,bytes.length-offset));check();return result;
            }
        }
        @Override public void close(){synchronized(guard){if(!stopped){stopped=true;exports--;lease.close();}}}
    }
    private final class Entry {
        final Key key;
        final MembershipResources.Lease marker;
        MembershipSourceSession session;
        Decoded completed;
        String requestDigest;
        boolean dead;
        Entry(Key key){this.key=key;marker=resources.reserve(MembershipResources.Unit.CONTROL,
                MembershipSourceResources.session("joining-checkpoint-trace",original.source.context.root,original.identity,key.reader,key.trace),1024);}
        Decoded answer(Decoded request)throws IOException {
            require(!dead,"joining checkpoint trace ended");
            try {
                if(completed!=null){require(request.digest().equals(requestDigest),"joining checkpoint exact completion retry");return completed;}
                if(session==null) {
                    initial(request);var export=new Export(object(request.value().get("ballot")));
                    try{session=new MembershipSourceSession(export,key.reader,key.trace,resources,chunkLimit,frameLimit,clock,started,budget);}
                    catch(IOException|RuntimeException|Error error){export.close();throw error;}
                }
                var reply=session.handle(key.reader,request);
                if(session.exhausted()) {
                    require(request.kind().equals("TRANSFER_COMMIT"),"joining checkpoint final commit");
                    marker.reserveControl(32768L+reply.size());requestDigest=request.digest();completed=reply;session.close();session=null;
                }
                return reply;
            }catch(IOException|RuntimeException|Error error){abort();throw error;}
        }
        void abort(){dead=true;completed=null;requestDigest=null;if(session!=null){session.close();session=null;}}
        void close(){abort();marker.close();}
    }
    Decoded answer(MembershipIdentity reader,Decoded request)throws IOException {
        try {
            synchronized(guard) {
                check();envelope(reader,request);var key=new Key(reader,UUID.fromString((String)request.value().get("trace")));
                var entry=traces.get(key);
                if(entry==null) {
                    initial(request);require(traces.size()<MembershipResources.Unit.CONTROL.count,"joining checkpoint trace capacity");
                    entry=new Entry(key);traces.put(key,entry);
                }
                var result=entry.answer(request);check();return result;
            }
        }catch(IOException|RuntimeException|Error error) {
            if(expired())try{close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    boolean poll(){if(expired())close();return !closed;}
    Usage usage(){synchronized(guard){return new Usage(traces.size(),exports,closed);}}
    /** A closing listener cannot be replaced until its workers and leases drain. */
    boolean closed(){return released;}
    @Override public void close() {
        synchronized(guard){closed=true;}
        transport.close();
        synchronized(guard) {
            if(released)return;
            for(var entry:traces.values())entry.close();traces.clear();metadata.close();released=true;
        }
    }
}
