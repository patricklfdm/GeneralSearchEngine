package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retrieves the original ROOT without inventing a local generation or voter.
 * The result authenticates only ROOT bytes. Complete live reservation/capsule
 * acquisition and forced admission remain required before materialization. */
final class MembershipLearnerDiscovery implements AutoCloseable {
    static final int ROOT_MAXIMUM=16384;
    private final MembershipLearnerRequest learner;
    private final MembershipIdentity peer;
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

    MembershipLearnerDiscovery(MembershipLearnerRequest learner,MembershipIdentity peer,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner discovery original budget");
        this.learner=Objects.requireNonNull(learner);this.peer=Objects.requireNonNull(peer);
        // Operator-supplied routes are contact addresses, not verified voter identities.
        require(!peer.equals(learner.identity()) && learner.change().target().contains(peer),"learner discovery contact route");
        this.resources=Objects.requireNonNull(resources);this.link=Objects.requireNonNull(link);
        this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        maximumAttempts=Math.min(3,bounds.maxRetryAttempts());maximumFrame=Math.min(FRAME,bounds.maxFrameBytes());
        require(maximumFrame>=4096,"learner discovery frame bound");
    }
    static Map<String,Object> request(MembershipChangeRequest change) {
        return Map.of("root",change.id().root().manifestDigest(),"number",change.id().number(),
                "expected",change.expectedConfigurationDigest(),"kind",change.kind().name(),
                "target",change.target().stream().map(MembershipBootstrapSeed::identity).toList());
    }
    /** Lookup alias, never a ROOT frame digest, vote, receipt or admission token. */
    static String reference(String root,MembershipIdentity learner,Map<String,Object> request) {
        return hash(canonical(Map.of("schema","gse-v53-learner-root-reference/1.3","root",root,
                "learner",MembershipBootstrapSeed.identity(learner),"request",request),16384));
    }
    static String reference(MembershipLearnerRequest learner) {
        return reference(learner.root().manifestDigest(),learner.identity(),request(learner.change()));
    }
    static boolean rootReference(MembershipContext context,MembershipIdentity learner,String digest) {
        var operation=list(context.catalog.get("results")).stream().map(MembershipFormat::object)
                .filter(row->object(row.get("request")).get("number").equals(context.catalog.get("active"))).findFirst().orElse(null);
        return operation!=null && context.view.get("operation")==null
                && !context.voters().contains(learner.nodeId().value())
                && learner.equals(context.identities.get(learner.nodeId().value()))
                && digest.equals(reference(context.root,learner,object(operation.get("request"))));
    }
    /** Receiver-side predicate on its verified current catalog, never caller arguments.
     * Known removed/initial identities and completed/cancelled operations cannot enroll. */
    static Map<String,Object> reservation(MembershipContext context,MembershipIdentity learner) {
        var operation=list(context.catalog.get("results")).stream().map(MembershipFormat::object)
                .filter(row->object(row.get("request")).get("number").equals(context.catalog.get("active"))).findFirst().orElse(null);
        require(operation!=null && context.view.get("operation")==null
                && Set.of("RESERVED","PREPARING","READY","SEALED").contains(operation.get("phase")),
                "learner discovery active pre-joint reservation");
        var original=object(operation.get("request"));
        require(!original.get("kind").equals("REMOVE") && !context.voters().contains(learner.nodeId().value())
                && learner.equals(context.identities.get(learner.nodeId().value()))
                && list(original.get("target")).stream().map(MembershipFormat::object).map(MembershipContext::identity).anyMatch(learner::equals),
                "learner discovery exact joining identity");
        return original;
    }
    static void reservation(MembershipContext context,MembershipIdentity learner,Decoded frame) {
        var original=reservation(context,learner);
        require(frame.kind().equals("CHUNK") && frame.value().get("root").equals(context.root)
                && frame.value().get("sender").equals(MembershipBootstrapSeed.identity(learner))
                && frame.value().get("view").equals(original.get("expected"))
                && frame.value().get("ballot").equals(correlation(learner)),"learner discovery original correlation");
        var payload=object(frame.value().get("payload"));
        require(number(frame.value().get("sequence"))==1 && payload.get("action").equals("REQUEST")
                && number(payload.get("offset"))==0 && payload.get("bytes").equals("")
                && payload.get("digest").equals(reference(context.root,learner,original)),
                "learner discovery reservation-scoped root reference");
    }
    static Map<String,Object> correlation(MembershipIdentity learner) {
        // Correlation only. This path must never call observe/allocate/prepare.
        return Map.of("counter",1L,"proposer",learner.nodeId().value(),"incarnation",learner.storageId().toString());
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner discovery closed/original deadline");
        guard.check();elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner discovery closed/original deadline");
    }
    private Decoded frame(String kind,Map<String,Object> payload)throws IOException {
        check();require(sequence<MembershipValidation.MAX,"learner discovery sequence exhausted");
        return decode(encode("wire",kind,Map.of("root",learner.root().manifestDigest(),"view",learner.change().expectedConfigurationDigest(),
                "ballot",correlation(learner.identity()),"sender",MembershipBootstrapSeed.identity(learner.identity()),
                "recipient",MembershipBootstrapSeed.identity(peer),"trace",trace.toString(),"sequence",++sequence,"payload",payload)),"wire",kind);
    }
    private Decoded exchange(Decoded request,String kind)throws IOException {
        require(request.size()<=maximumFrame,"learner discovery request frame bound");
        var retry=new MembershipExchange(request.digest(),started,budget);
        try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"learner-root-request-"+UUID.randomUUID(),request.size())) {
            for(;;) {
                check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                synchronized(this){check();future=Objects.requireNonNull(link.exchange(peer,request,kind,started+budget));pending=future;if(closed)future.cancel(true);}
                try {
                    long left=budget-(clock.getAsLong()-started);if(left<=0){future.cancel(true);throw new IOException("learner discovery original deadline");}
                    var reply=future.get(left,TimeUnit.NANOSECONDS);check();require(reply.size()<=maximumFrame,"learner discovery response frame bound");
                    MembershipWire.envelope(reply,learner.root().manifestDigest(),peer,learner.identity());MembershipWire.correlated(request,reply,kind);
                    if(reply.kind().equals("REJECT"))throw new MembershipSourcePull.Rejected(reply);
                    retry.complete(request.digest(),clock.getAsLong());return reply;
                }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("learner discovery interrupted",error);}
                catch(CancellationException error){throw new IOException("learner discovery cancelled",error);}
                catch(TimeoutException error){future.cancel(true);throw new IOException("learner discovery original deadline",error);}
                catch(ExecutionException error) {
                    var cause=error.getCause();
                    if(cause instanceof MembershipTransport.Failure failure &&
                            (failure.reason==MembershipTransport.Reason.IO || failure.reason==MembershipTransport.Reason.DEADLINE)) {
                        check();if(retry.attempts()>=maximumAttempts)throw failure;
                    }else {
                        if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;
                        throw new IOException("learner discovery exchange failed",cause);
                    }
                }finally{synchronized(this){if(pending==future)pending=null;}}
            }
        }
    }
    Decoded fetch()throws IOException {
        synchronized(this){require(!used && !closed,"learner discovery single use");used=true;}
        try {
            var offer=object(exchange(frame("CHUNK",Map.of("action","REQUEST","id",transfer.toString(),"offset",0L,
                    "digest",reference(learner),"bytes","")),"SOURCE_OFFER").value().get("payload"));
            long bytes=number(offer.get("bytes"));String digest=(String)offer.get("digest");
            require(offer.get("id").equals(transfer.toString()) && offer.get("kind").equals("RECORD")
                    && bytes>HEADER && bytes<=ROOT_MAXIMUM,"learner discovery bounded original ROOT offer");
            try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"learner-root-bytes-"+UUID.randomUUID(),bytes*3)) {
                byte[] content=new byte[(int)bytes];int offset=0;
                while(offset<content.length) {
                    var payload=object(exchange(frame("CHUNK",Map.of("action","REQUEST","id",transfer.toString(),"offset",(long)offset,
                            "digest",digest,"bytes","")),"CHUNK").value().get("payload"));
                    String encoded=(String)payload.get("bytes");
                    require(encoded.length()<=((content.length-offset+2)/3)*4,"learner discovery chunk allocation bound");
                    byte[] part=Base64.getDecoder().decode(encoded);
                    require(payload.get("action").equals("DATA") && payload.get("id").equals(transfer.toString())
                            && number(payload.get("offset"))==offset && part.length>0 && part.length<=content.length-offset
                            && hash(part).equals(payload.get("digest")),"learner discovery exact ROOT chunk");
                    System.arraycopy(part,0,content,offset,part.length);offset+=part.length;
                }
                require(hash(content).equals(digest),"learner discovery original ROOT digest");
                var root=decode(content,"records","ROOT");
                require(root.rootDigest().equals(learner.root().manifestDigest())
                        && root.value().get("groupId").equals(learner.root().groupId().value().toString())
                        && root.value().get("historyId").equals(learner.root().historyId().toString())
                        && root.value().get("limits").equals(hash(canonical(CATALOG.get("resources"),16384))),"learner discovery authentic ROOT identity");
                var commit=Map.<String,Object>of("id",transfer.toString(),"digest",digest);
                require(object(exchange(frame("TRANSFER_COMMIT",commit),"TRANSFER_COMMIT").value().get("payload")).equals(commit),
                        "learner discovery exact ROOT completion");check();return root;
            }
        }finally{close();}
    }
    /** An untrusted location hint only, never a reservation proof or readiness. */
    MembershipDiscovery.Hint hint()throws IOException {
        synchronized(this){require(!used && !closed,"learner discovery single use");used=true;}
        try {
            String nonce=UUID.randomUUID().toString();
            var reply=exchange(frame("STATUS_PROBE",Map.of("nonce",nonce)),"STATUS");
            var payload=object(reply.value().get("payload"));
            require(nonce.equals(payload.get("nonce")) && Boolean.FALSE.equals(payload.get("ready")),"learner discovery hint correlation");
            var cut=object(payload.get("cut"));checkView(object(cut.get("view")));MembershipValidation.position(number(cut.get("index")));
            check();return new MembershipDiscovery.Hint(peer,cut,false);
        }finally{close();}
    }
    @Override public synchronized void close(){closed=true;if(pending!=null)pending.cancel(true);}
}
