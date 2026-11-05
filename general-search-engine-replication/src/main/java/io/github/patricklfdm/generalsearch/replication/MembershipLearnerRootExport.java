package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One small original ROOT borrow under an actual live reservation. This is
 * control metadata, not a generation/source copy, receipt, installation or vote. */
final class MembershipLearnerRootExport implements MembershipTransferExport {
    private final MembershipGrantJournal owner;
    private final MembershipCapsule original;
    private final MembershipIdentity reader,local;
    private final Decoded request;
    private final MembershipResources resources;
    private final MembershipResources.Lease lease;
    private final MembershipPrefixExport originalBorrow;
    private final LongSupplier clock;
    private final long started,budget;
    private final byte[] root;
    private final String digest;
    private final Map<String,MembershipSourceExport.Content> references;
    private boolean closed;
    MembershipLearnerRootExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner ROOT export budget");
        this.owner=Objects.requireNonNull(owner);this.reader=Objects.requireNonNull(reader);this.request=request;
        this.resources=resources;this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        synchronized(owner) {
            original=owner.activationCapsule();local=owner.activationIdentity();
            require(owner.discoveryState(resources).context()==original.context,"learner ROOT export shared owner");
            MembershipWire.envelope(request,original.context.root,reader,local);
            MembershipLearnerDiscovery.reservation(original.context,reader,request);
            int size=original.packet.objectSize(original.context.recordRootDigest());
            require(size>HEADER && size<=MembershipLearnerDiscovery.ROOT_MAXIMUM,"learner original ROOT capacity");
            lease=resources.reserve(MembershipResources.Unit.CONTROL,
                    MembershipSourceResources.export("learner-root-export",original.context.recordRootDigest()),size*2L+4096);
            MembershipPrefixExport acquired=null;
            try {
                // Share the native owner's six-export registry. A small ROOT read
                // must not create an untracked alternate export lifetime.
                acquired=owner.exportPrefix(cutDigest(original.context.cut),object(request.value().get("ballot")),
                        (String)request.value().get("view"),resources,clock,started,budget);
                originalBorrow=acquired;
                root=original.packet.objectBytes(original.context.recordRootDigest());digest=hash(root);
                var record=decode(root,"records","ROOT");
                require(record.rootDigest().equals(original.context.root) && record.digest().equals(original.context.recordRootDigest()),
                        "learner original ROOT identity");
                var content=new MembershipSourceExport.Content(digest,root.length,MembershipTransfer.Kind.RECORD);
                references=Map.of(digest,content,(String)object(request.value().get("payload")).get("digest"),content);check();
            }catch(IOException|RuntimeException|Error error){if(acquired!=null)acquired.close();lease.close();throw error;}
        }
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner ROOT export closed/original deadline");
        require(owner.activationCapsule()==original && owner.discoveryState(resources).context()==original.context,
                "learner ROOT export original reservation replaced");
        originalBorrow.references();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner ROOT export closed/original deadline");
    }
    @Override public List<MembershipResources.Lease> closeReservations(){return MembershipTransferExport.ownedWithBorrow(lease,originalBorrow);}
    @Override public MembershipContext context(){return original.context;}
    @Override public MembershipIdentity identity(){return local;}
    @Override public Map<String,Object> ballot(){return object(request.value().get("ballot"));}
    @Override public void request(MembershipIdentity reader,Decoded incoming,UUID trace) {
        require(this.reader.equals(reader) && Set.of("CHUNK","TRANSFER_COMMIT").contains(incoming.kind()),"learner ROOT export reader/kind");
        MembershipWire.envelope(incoming,context().root,reader,local);
        require(request.value().get("view").equals(incoming.value().get("view")) && ballot().equals(incoming.value().get("ballot"))
                && request.value().get("trace").equals(trace.toString()) && incoming.value().get("trace").equals(trace.toString()),
                "learner ROOT export exact correlation");
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){check();return references;}
    }
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner) {
            check();require(this.digest.equals(digest) && offset>=0 && offset<root.length && maximum>0,
                    "learner ROOT export exact extent");
            int start=Math.toIntExact(offset);byte[] bytes=Arrays.copyOfRange(root,start,start+Math.min(maximum,root.length-start));check();return bytes;
        }
    }
    @Override public void close(){synchronized(owner){if(!closed){closed=true;try{originalBorrow.close();}finally{lease.close();}}}}
}
