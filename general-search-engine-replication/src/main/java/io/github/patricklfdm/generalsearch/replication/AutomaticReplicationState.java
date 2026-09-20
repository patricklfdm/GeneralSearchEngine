package io.github.patricklfdm.generalsearch.replication;

/** Local lifecycle/leadership observations; a role observation is not authority. */
public enum AutomaticReplicationState {
    STOPPED, STARTING, FOLLOWER, CANDIDATE, RECOVERING,
    LEADER_READY, UNAVAILABLE, FAILED, CLOSED
}
