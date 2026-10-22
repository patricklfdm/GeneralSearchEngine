package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Three attempts of one immutable exchange under one deadline; never a client-operation retry. */
final class MembershipExchange {
    private final String requestDigest;
    private final long started, budget;
    private int attempts;
    private boolean completed;
    MembershipExchange(String requestDigest,long started,long budget) {
        digest(requestDigest);require(budget>0 && budget<Long.MAX_VALUE/2,"exchange time budget");
        this.requestDigest=requestDigest;this.started=started;this.budget=budget;
    }
    void attempt(String sameRequest,long now) {
        require(requestDigest.equals(sameRequest),"exchange changed request");
        long elapsed=now-started;
        require(elapsed>=0 && elapsed<budget,"original exchange deadline");
        require(!completed && attempts<3,"exchange attempt bound/state");attempts++;
    }
    void complete(String sameRequest,long now) {
        require(requestDigest.equals(sameRequest) && attempts>0,"unknown exchange completion");
        long elapsed=now-started;require(elapsed>=0 && elapsed<budget,"late exchange completion");completed=true;
    }
    int attempts() { return attempts; }
}
