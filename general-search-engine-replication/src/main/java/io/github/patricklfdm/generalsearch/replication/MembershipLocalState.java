package io.github.patricklfdm.generalsearch.replication;

/** Local role observation, not quorum authority. */
public enum MembershipLocalState { VOTER, LEARNER, REMOVED, DRAINING }
