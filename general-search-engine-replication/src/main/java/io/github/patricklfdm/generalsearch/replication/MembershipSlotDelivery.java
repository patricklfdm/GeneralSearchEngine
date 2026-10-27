package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded identical delivery of this proposer's actual native vote/application.
 * A correlated ACK is not an original-owner observation or a publication proof. */
final class MembershipSlotDelivery {
    private MembershipSlotDelivery() {}
    static Decoded deliver(MembershipGrantJournal owner,MembershipIdentity peer,Decoded request,MembershipResources resources,
            MembershipTransport transport,LongSupplier clock,long started,long budget)throws IOException {
        return deliver(owner,peer,request,resources,transport,clock,started,budget,()->{});
    }
    static Decoded deliver(MembershipGrantJournal owner,MembershipIdentity peer,Decoded request,MembershipResources resources,
            MembershipTransport transport,LongSupplier clock,long started,long budget,MembershipSourcePull.Guard parent)throws IOException {
        Objects.requireNonNull(parent);parent.check();
        require(budget>0 && budget<Long.MAX_VALUE/2,"slot delivery budget");
        var original=owner.voting(resources);String kind=request.kind();
        require(Set.of("ACCEPT","PROOF","APPLY").contains(kind),"slot delivery kind");
        var context=original.before.context;var local=owner.activationIdentity();
        require(local.nodeId().value().equals(original.ballot.get("proposer")),"slot delivery proposer");
        context.wire(request,local,peer,original.ballot,UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
        Map<String,Object> expected;
        if(kind.equals("APPLY")) {
            var applied=original.application().orElseThrow(()->new IllegalArgumentException("slot delivery actual application required"));
            var certificate=applied.plan().originalCertificate();String selection=owner.originalSelection().orElseThrow().digest();
            require(object(request.value().get("payload")).equals(Map.of("certificate",certificate.digest(),"selection",selection)),"slot delivery original application request");
            var ack=new TreeMap<>(applied.endorsement().acknowledgement().value());ack.put("voter",peer.nodeId().value());ack.put("incarnation",peer.storageId().toString());
            expected=Map.of("certificate",certificate.digest(),"selection",selection,"statement",applied.plan().statement.digest(),
                    "acknowledgement",hash(encode("records","CHECKPOINT_ACK",ack)));
        }else {
            var record=original.record(kind).orElseThrow(()->new IllegalArgumentException("slot delivery original vote required"));
            require(object(request.value().get("payload")).equals(Map.of(kind.equals("ACCEPT")?"acceptance":"proof",record.digest())),"slot delivery original vote request");
            expected=Map.of("entry",record.value().get("entry"),"receipt",hash(MembershipVoteReceipt.bytes(context,peer,record)));
        }
        MembershipSourcePull.Guard guard=()->{parent.check();long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"slot delivery original deadline");original.check();parent.check();};
        var retry=new MembershipExchange(request.digest(),started,budget);
        try(var lease=resources.reserve(MembershipResources.Unit.CONTROL,"slot-delivery-"+UUID.randomUUID(),request.size())) {
            for(;;) {
                guard.check();retry.attempt(request.digest(),clock.getAsLong());
                var response=transport.exchange(peer,request,kind+"_ACK",started+budget,guard);
                try {
                    long left=budget-(clock.getAsLong()-started);require(left>0,"slot delivery original deadline");
                    var value=response.get(left,TimeUnit.NANOSECONDS);guard.check();MembershipWire.correlated(request,value,kind+"_ACK");
                    if(value.kind().equals("REJECT")) {
                        var promised=object(object(value.value().get("payload")).get("promised"));context.ballot(promised,true);
                        if(MembershipContext.compareBallot(promised,original.ballot)>0)owner.observeCurrent(promised);
                        throw new MembershipSourcePull.Rejected(value);
                    }
                    require(value.value().get("payload").equals(expected),"slot delivery exact acknowledgement");retry.complete(request.digest(),clock.getAsLong());return value;
                }catch(InterruptedException error){response.cancel(true);Thread.currentThread().interrupt();throw new IOException("slot delivery interrupted",error);}
                catch(TimeoutException|CancellationException error){response.cancel(true);throw new IOException("slot delivery original deadline/closed",error);}
                catch(ExecutionException error) {
                    var cause=error.getCause();guard.check();
                    if(cause instanceof MembershipTransport.Failure failure && (failure.reason==MembershipTransport.Reason.IO || failure.reason==MembershipTransport.Reason.DEADLINE) && retry.attempts()<3)continue;
                    if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;if(cause instanceof Error fatal)throw fatal;
                    throw new IOException("slot delivery failed",cause);
                }
            }
        }
    }
}
