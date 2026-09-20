package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import java.util.Optional;

/** Classified automatic-mode failure; outcome, not reason/hint alone, governs mutation retry. */
public final class AutomaticReplicationException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public enum Reason {
        NOT_LEADER, NOT_READY, QUORUM_UNAVAILABLE, STALE_EPOCH,
        CONFLICTING_HISTORY, CAPACITY_EXCEEDED, PROTOCOL_MISMATCH,
        INTEGRITY_FAILURE, STORAGE_FAILURE, DEADLINE_EXCEEDED, REENTRANT_CALL, CLOSED
    }
    public enum Outcome { NOT_APPLICABLE, NOT_SUBMITTED, INDETERMINATE }
    private final Reason reason;
    private final Outcome outcome;
    private final Optional<ReplicationNodeId> observedLeader;

    public AutomaticReplicationException(Reason reason, Outcome outcome,
            Optional<ReplicationNodeId> observedLeader, String message) {
        this(reason, outcome, observedLeader, message, null);
    }

    public AutomaticReplicationException(Reason reason, Outcome outcome,
            Optional<ReplicationNodeId> observedLeader, String message, Throwable cause) {
        super(Objects.requireNonNull(message, "message"), cause);
        this.reason = Objects.requireNonNull(reason, "reason");
        this.outcome = Objects.requireNonNull(outcome, "outcome");
        this.observedLeader = Objects.requireNonNull(observedLeader, "observedLeader");
    }

    public Reason reason() { return reason; }
    public Outcome outcome() { return outcome; }
    public Optional<ReplicationNodeId> observedLeader() { return observedLeader; }
}
