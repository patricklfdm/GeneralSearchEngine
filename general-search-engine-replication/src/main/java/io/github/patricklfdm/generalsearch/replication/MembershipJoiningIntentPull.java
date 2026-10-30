package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded read-only pending metadata exchange. Structural metadata remains
 * distinct from a durable joining witness; this class cannot issue one. */
final class MembershipJoiningIntentPull implements AutoCloseable {
    private final MembershipLearnerRequest request;
    private final MembershipIdentity peer;
    private final MembershipCapsule before;
    private final Decoded receipt;
    private final MembershipResources resources;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final int maximumAttempts,maximumFrame;
    private final UUID trace=UUID.randomUUID(),transfer=UUID.randomUUID();
    private volatile boolean closed;
    private boolean used;
    private long sequence;
    private CompletableFuture<Decoded> pending;
    private MembershipResources.Lease held;
    private MembershipJoiningIntentMetadata received;

    MembershipJoiningIntentPull(MembershipLearnerRequest request,MembershipIdentity peer,MembershipCapsule before,Decoded receipt,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining pull original budget");
        this.request=Objects.requireNonNull(request);this.peer=Objects.requireNonNull(peer);this.before=Objects.requireNonNull(before);
        this.receipt=Objects.requireNonNull(receipt);this.resources=Objects.requireNonNull(resources);this.link=Objects.requireNonNull(link);
        this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        maximumAttempts=Math.min(3,bounds.maxRetryAttempts());maximumFrame=Math.min(FRAME,bounds.maxFrameBytes());
        require(maximumFrame>=4096,"joining pull frame bound");
        MembershipLearnerProgressAccess.original(before.context,request,peer);
        var row=MembershipLearnerProgressAccess.operation(before.context,request.identity());
        require(row.get("phase").equals("SEALED") && before.context.view.get("operation")==null
                && receipt.kind().equals("LEARNER") && receipt.value().get("root").equals(before.context.root)
                && receipt.value().get("receipt").equals(row.get("receipt")),"joining pull original typed SEALED source");check();
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining pull closed/original deadline");
        guard.check();elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"joining pull closed/original deadline");
    }
    private Decoded frame(String kind,Map<String,Object> payload)throws IOException {
        check();require(sequence<MembershipValidation.MAX,"joining pull sequence exhausted");
        return decode(encode("wire",kind,Map.of("root",request.root().manifestDigest(),"view",request.change().expectedConfigurationDigest(),
                "ballot",MembershipLearnerDiscovery.correlation(request.identity()),"sender",MembershipBootstrapSeed.identity(request.identity()),
                "recipient",MembershipBootstrapSeed.identity(peer),"trace",trace.toString(),"sequence",++sequence,"payload",payload)),"wire",kind);
    }
    private Decoded exchange(Decoded request,String kind)throws IOException {
        require(request.size()<=maximumFrame,"joining pull request frame bound");
        var retry=new MembershipExchange(request.digest(),started,budget);
        try(var work=resources.reserve(MembershipResources.Unit.CONTROL,"joining-request-"+UUID.randomUUID(),request.size())) {
            for(;;) {
                check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                synchronized(this){check();future=Objects.requireNonNull(link.exchange(peer,request,kind,started+budget));pending=future;if(closed)future.cancel(true);}
                try {
                    long left=budget-(clock.getAsLong()-started);if(left<=0){future.cancel(true);throw new IOException("joining pull original deadline");}
                    var reply=future.get(left,TimeUnit.NANOSECONDS);check();require(reply.size()<=maximumFrame,"joining pull response frame bound");
                    MembershipWire.envelope(reply,this.request.root().manifestDigest(),peer,this.request.identity());MembershipWire.correlated(request,reply,kind);
                    if(reply.kind().equals("REJECT"))throw new MembershipSourcePull.Rejected(reply);
                    retry.complete(request.digest(),clock.getAsLong());return reply;
                }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("joining pull interrupted",error);}
                catch(CancellationException error){throw new IOException("joining pull cancelled",error);}
                catch(TimeoutException error){future.cancel(true);throw new IOException("joining pull original deadline",error);}
                catch(ExecutionException error) {
                    var cause=error.getCause();
                    if(cause instanceof MembershipTransport.Failure failure &&
                            (failure.reason==MembershipTransport.Reason.IO || failure.reason==MembershipTransport.Reason.DEADLINE)) {
                        check();if(retry.attempts()>=maximumAttempts)throw failure;
                    }else {
                        if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;
                        throw new IOException("joining pull exchange failed",cause);
                    }
                }finally{synchronized(this){if(pending==future)pending=null;}}
            }
        }
    }
    MembershipJoiningIntentMetadata fetch()throws IOException {
        synchronized(this){check();require(!used,"joining pull single use");used=true;}
        try {
            var offer=object(exchange(frame("CHUNK",Map.of("action","REQUEST","id",transfer.toString(),"offset",0L,
                    "digest",MembershipJoiningIntentExport.reference(request,before.context.cut),"bytes","")),"SOURCE_OFFER").value().get("payload"));
            long size=number(offer.get("bytes"));String digest=(String)offer.get("digest");
            require(offer.get("id").equals(transfer.toString()) && offer.get("kind").equals("RECORD")
                    && size>0 && size<=MembershipJoiningIntentMetadata.MAXIMUM,"joining pull bounded metadata offer");
            synchronized(this){check();held=resources.reserve(MembershipResources.Unit.CONTROL,"joining-metadata-"+UUID.randomUUID(),size*3);}
            byte[] content=new byte[Math.toIntExact(size)];int offset=0;
            while(offset<content.length) {
                var payload=object(exchange(frame("CHUNK",Map.of("action","REQUEST","id",transfer.toString(),"offset",(long)offset,
                        "digest",digest,"bytes","")),"CHUNK").value().get("payload"));
                String encoded=(String)payload.get("bytes");
                require(encoded.length()<=((content.length-offset+2)/3)*4,"joining pull chunk allocation bound");
                byte[] part=Base64.getDecoder().decode(encoded);
                require(payload.get("action").equals("DATA") && payload.get("id").equals(transfer.toString())
                        && number(payload.get("offset"))==offset && part.length>0 && part.length<=content.length-offset
                        && part.length<=4*1024*1024 && hash(part).equals(payload.get("digest")),"joining pull exact metadata chunk");
                System.arraycopy(part,0,content,offset,part.length);offset+=part.length;
            }
            require(hash(content).equals(digest),"joining pull original metadata digest");
            var parsed=MembershipJoiningIntentMetadata.inspect(request,peer,before,receipt,content);check();
            var commit=Map.<String,Object>of("id",transfer.toString(),"digest",digest);
            require(object(exchange(frame("TRANSFER_COMMIT",commit),"TRANSFER_COMMIT").value().get("payload")).equals(commit),
                    "joining pull exact completion");
            synchronized(this){check();received=parsed;return received;}
        }catch(IOException|RuntimeException|Error error){close();throw error;}
    }
    synchronized MembershipJoiningIntentMetadata metadata()throws IOException {
        check();require(received!=null,"joining pull incomplete");return received;
    }
    @Override public synchronized void close(){closed=true;received=null;if(pending!=null)pending.cancel(true);if(held!=null){held.close();held=null;}}
}
