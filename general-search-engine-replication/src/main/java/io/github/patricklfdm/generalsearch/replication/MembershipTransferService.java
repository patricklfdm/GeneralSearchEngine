package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read-only transfer dispatch for one runtime authority/ballot lifetime. No service READY
 * or voting authority. The owner loop must poll expiry and close on campaign replacement.
 * A failed trace remains a bounded tombstone until this whole scope closes. */
final class MembershipTransferService implements MembershipTransport.Handler,AutoCloseable {
    private record Key(MembershipIdentity reader,UUID trace) {}
    record Usage(int traces,int live,int calls,boolean closed) {}
    private final MembershipGrantJournal owner;
    private final MembershipContext context;
    private final MembershipIdentity identity;
    private final Map<String,Object> ballot;
    private final boolean prefix;
    private final MembershipGrantJournal.Publication publication;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Guard guard;
    private final MembershipTransport.Events events;
    private final LongSupplier clock;
    private final long started,budget;
    private final int frameLimit,chunkLimit;
    private final MembershipResources.Lease metadata;
    private final Map<Key,Entry> traces=new HashMap<>();
    private final Map<MembershipIdentity,Integer> calls=new HashMap<>();
    private volatile boolean closed;

    MembershipTransferService(MembershipGrantJournal owner,Map<String,Object> ballot,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        this(owner,ballot,resources,bounds,guard,clock,started,budget,MembershipTransport.Events.NONE);
    }
    MembershipTransferService(MembershipGrantJournal owner,Map<String,Object> ballot,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,MembershipTransport.Events events)throws IOException {
        this(owner,ballot,resources,bounds,guard,clock,started,budget,events,false,null);
    }
    static MembershipTransferService prefix(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        return new MembershipTransferService(owner,Map.of(),resources,bounds,guard,clock,started,budget,MembershipTransport.Events.NONE,true,null);
    }
    static MembershipTransferService publication(MembershipGrantJournal owner,MembershipGrantJournal.Publication publication,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        return new MembershipTransferService(owner,publication.ballot,resources,bounds,guard,clock,started,budget,MembershipTransport.Events.NONE,false,publication);
    }
    private MembershipTransferService(MembershipGrantJournal owner,Map<String,Object> ballot,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,MembershipTransport.Events events,boolean prefix,MembershipGrantJournal.Publication publication)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"transfer service time budget");this.prefix=prefix;this.publication=publication;
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        this.events=Objects.requireNonNull(events);
        context=publication==null?owner.activationContext():publication.before.context;identity=owner.activationIdentity();if(!prefix)context.ballot(ballot,true);this.ballot=Map.copyOf(ballot);
        frameLimit=Math.min(FRAME,bounds.maxFrameBytes());chunkLimit=Math.min(4*1024*1024,bounds.snapshotChunkBytes());
        require(frameLimit>=4096,"transfer service frame limit");guard.check();time();
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"transfer-service-"+UUID.randomUUID(),32768);
        try{time();}catch(RuntimeException|Error error){metadata.close();throw error;}
    }
    private boolean expired(){long elapsed=clock.getAsLong()-started;return elapsed<0 || elapsed>=budget;}
    private void time(){require(!closed && !expired(),"original transfer service deadline/closed");}
    /** Called by the runtime's existing periodic loop; this service creates no background thread. */
    boolean poll(){if(expired())close();return !closed;}
    private void live()throws IOException {
        try{time();guard.check();if(prefix)require(owner.activationContext().cut.equals(context.cut),"prefix service cut changed");time();}
        catch(IOException|RuntimeException error){close();throw error;}
    }
    private final class Entry {
        final Key key;
        final MembershipResources.Lease marker;
        volatile MembershipSourceSession session;
        String completedRequest;
        Decoded completedReply;
        volatile boolean dead,released;
        Entry(Key key) {this.key=key;marker=resources.reserve(MembershipResources.Unit.CONTROL,"transfer-trace-"+UUID.randomUUID(),1024);}
        synchronized Decoded handle(Decoded request)throws IOException {
            require(!dead && !released,"transfer trace already ended");
            try {
                time();
                if(completedReply!=null) {
                    require(request.digest().equals(completedRequest),"completed transfer exact retry only");
                    return completedReply;
                }
                if(session==null) {
                    var payload=object(request.value().get("payload"));
                    // A competing next request cannot initialize an unconstructed trace.
                    initial(request);
                    var export=prefix && MembershipLearnerDiscovery.rootReference(context,key.reader,(String)payload.get("digest"))?
                            new MembershipLearnerRootExport(owner,key.reader,request,resources,clock,started,budget):
                            prefix && MembershipLearnerPrefixExport.scope(context,key.reader,(String)payload.get("digest"))!=null?
                            new MembershipLearnerPrefixExport(owner,key.reader,request,resources,clock,started,budget):
                            prefix && MembershipLearnerProgressAccess.scope(context,key.reader,(String)payload.get("digest"))!=null?
                            new MembershipLearnerPrefixExport(owner,key.reader,request,resources,clock,started,budget,true):
                            prefix?owner.exportPrefix((String)payload.get("digest"),object(request.value().get("ballot")),
                            (String)request.value().get("view"),resources,clock,started,budget):
                            publication!=null && publication.published()?owner.exportPublishedCheckpoint(publication,(String)payload.get("digest"),clock,started,budget):
                            owner.exportTransfer((String)payload.get("digest"),context.authority(),ballot,clock,started,budget);
                    try {
                        require(export.identity().equals(identity) && export.context().root.equals(context.root)
                                && export.context().authority().equals(context.authority())
                                && (prefix?export.context().cut.equals(context.cut):export.ballot().equals(ballot)),"transfer export scope changed");
                        session=new MembershipSourceSession(export,key.reader,key.trace,resources,chunkLimit,frameLimit,clock,started,budget);
                    }catch(IOException|RuntimeException|Error error){export.close();throw error;}
                }
                var reply=session.handle(key.reader,request);time();
                if(session.exhausted()) {
                    require(request.kind().equals("TRANSFER_COMMIT"),"completed transfer requires final commit");
                    // Account the retained decoded reply before dropping the
                    // export/session buffers. Keep the trace so a changed retry
                    // cannot resample another source under the same identity.
                    marker.reserveControl(32768L+reply.size());
                    completedRequest=request.digest();completedReply=reply;
                    session.close();session=null;
                }
                return reply;
            }catch(IOException|RuntimeException|Error error){abort();throw error;}
        }
        boolean liveSession(){return session!=null && !dead && !released;}
        synchronized void abort(){dead=true;completedRequest=null;completedReply=null;if(session!=null){session.close();session=null;}}
        synchronized void close(){abort();if(!released){released=true;marker.close();}}
    }
    private static void initial(Decoded request) {
        var payload=object(request.value().get("payload"));
        require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                && payload.get("action").equals("REQUEST") && number(payload.get("offset"))==0 && payload.get("bytes").equals(""),"transfer initial request");
    }
    @Override public Decoded handle(MembershipIdentity reader,Decoded request)throws IOException {
        live();require(request.size()<=frameLimit,"transfer service frame capacity");
        require(request.kind().equals("CHUNK") || request.kind().equals("TRANSFER_COMMIT"),"transfer service request kind");
        UUID trace=UUID.fromString((String)request.value().get("trace"));
        if(prefix)MembershipPrefixExport.envelope(context,identity,reader,request);
        else context.wire(request,reader,identity,ballot,trace,number(request.value().get("sequence")));
        require(!reader.equals(identity),"transfer self request");var key=new Key(reader,trace);Entry entry;
        synchronized(this) {
            time();int active=calls.getOrDefault(reader,0);
            if(active>=bounds.maxInFlightPerPeer())throw new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"transfer peer in-flight capacity",null);
            entry=traces.get(key);
            if(entry==null) {
                initial(request);require(traces.size()<MembershipResources.Unit.CONTROL.count,"transfer trace capacity");
                entry=new Entry(key);traces.put(key,entry);
            }
            calls.put(reader,active+1);
        }
        try {
            events.at("TRANSFER_ADMITTED",request,null);live();var response=entry.handle(request);live();
            events.at("TRANSFER_BEFORE_REPLY",request,response);live();return response;
        }
        catch(IOException|RuntimeException|Error error){entry.abort();if(expired())close();throw error;}
        finally {synchronized(this){int count=calls.get(reader);if(count==1)calls.remove(reader);else calls.put(reader,count-1);}}
    }
    boolean sameCut(Map<String,Object> cut){return context.cut.equals(cut);}
    synchronized boolean contains(MembershipIdentity reader,Decoded request) {
        return traces.containsKey(new Key(reader,UUID.fromString((String)request.value().get("trace"))));
    }
    Usage usage() {
        List<Entry> entries;int active;boolean stopped;
        synchronized(this){entries=List.copyOf(traces.values());active=calls.values().stream().mapToInt(Integer::intValue).sum();stopped=closed;}
        // Never acquire an entry monitor while holding the registry monitor.
        return new Usage(entries.size(),(int)entries.stream().filter(Entry::liveSession).count(),active,stopped);
    }
    @Override public void close() {
        List<Entry> entries;
        synchronized(this){if(closed)return;closed=true;entries=List.copyOf(traces.values());traces.clear();}
        // The protocol must call close outside the journal monitor; reads serialize on that owner.
        try{for(var entry:entries)entry.close();}finally{metadata.close();}
    }
}
