package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Objects;
import java.util.concurrent.CancellationException;

/** A positively identified reason to abandon this round. It never authorizes
 * replay of a client command, bypasses recovery, or renews an original deadline. */
final class MembershipCampaignLost extends IOException {
    private static final long serialVersionUID=1L;
    enum Reason { HIGHER_BALLOT, VIEW_CHANGED, CONTACT_UNAVAILABLE }
    final Reason reason;
    MembershipCampaignLost(Reason reason,String message){super(message);this.reason=Objects.requireNonNull(reason);}
    /** CompletableFuture still reports isCancelled(), so the transport stops
     * its socket work, while the exact positively identified loss survives. */
    static final class Cancelled extends CancellationException {
        private static final long serialVersionUID=1L;
        final MembershipCampaignLost loss;
        Cancelled(MembershipCampaignLost loss){super("original campaign revoked");this.loss=Objects.requireNonNull(loss);}
    }
}
