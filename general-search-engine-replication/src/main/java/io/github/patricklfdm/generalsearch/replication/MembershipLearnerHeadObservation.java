package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A process-local observation of an actual forced typed head. No constructor
 * accepts decoded metadata or a receipt. This capability cannot be serialized
 * into a remote acknowledgement; that requires its own authenticated protocol. */
final class MembershipLearnerHeadObservation implements AutoCloseable {
    static final int BYTES=32*1024;
    final Map<String,Object> request;
    final MembershipIdentity learner;
    final MembershipCapsule.Anchor endpoint;
    private final MembershipLearnerHead head;
    private final MembershipResources resources;
    private final MembershipResources.Lease lease;
    private boolean closed;

    private MembershipLearnerHeadObservation(MembershipLearnerHead head,MembershipResources resources,
            MembershipResources.Lease lease)throws IOException {
        this.head=head;this.resources=resources;this.lease=lease;
        var original=head.request();learner=original.identity();
        request=object(parse(canonical(MembershipLearnerDiscovery.request(original.change()),8192),8192));
        var source=head.source();var terminal=source.terminal();
        endpoint=new MembershipCapsule.Anchor(object(parse(canonical(terminal.cut(),8192),8192)),terminal.catalog(),terminal.application());
        require(source.context.root.equals(original.root().manifestDigest())
                && !source.context.voters().contains(learner.nodeId().value()),"learner observation nonvoting original");
        check();
    }
    static MembershipLearnerHeadObservation capture(MembershipLearnerHead head)throws IOException {
        Objects.requireNonNull(head);head.check();MembershipLearnerCancellation.requireActive(head);
        var resources=head.resources();var lease=resources.reserve(MembershipResources.Unit.CONTROL,"learner-head-"+UUID.randomUUID(),BYTES);
        try{return new MembershipLearnerHeadObservation(head,resources,lease);}
        catch(IOException|RuntimeException|Error error){lease.close();throw error;}
    }
    void check()throws IOException {
        require(!closed,"learner head observation closed");head.check();MembershipLearnerCancellation.requireActive(head);
        var original=head.request();
        require(head.resources()==resources && original.identity().equals(learner)
                && MembershipLearnerDiscovery.request(original.change()).equals(request)
                && head.source().terminal().equals(endpoint),"learner head observation changed original");
    }
    @Override public void close(){if(!closed){closed=true;lease.close();}}
}
