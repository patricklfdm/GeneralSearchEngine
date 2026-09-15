package io.github.patricklfdm.generalsearch.replication;

/** Observable local lifecycle state, distinct from configured membership role. */
public enum ReplicaState {
    STARTING,
    ACTIVATING,
    CATCHING_UP,
    READY,
    UNAVAILABLE,
    FAILED,
    CLOSED
}
