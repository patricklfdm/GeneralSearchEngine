package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import java.util.Optional;

/** Structured membership failure; an indeterminate mutation is never automatically replayed. */
public final class MembershipOperationException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public enum Reason {
        NOT_LEADER, NOT_READY, BUSY, STALE_CONFIGURATION, CONFLICTING_OPERATION,
        INVALID_MEMBERSHIP, IDENTITY_REUSED, OPERATION_RETIRED, IRREVERSIBLE,
        STALE_OPERATION_NUMBER, INCOMPATIBLE_HISTORY,
        STALE_PREPARATION, LEARNER_UNAVAILABLE, CAPACITY_EXCEEDED,
        QUORUM_UNAVAILABLE, STALE_EPOCH, PROTOCOL_MISMATCH, INTEGRITY_FAILURE,
        STORAGE_FAILURE, DEADLINE_EXCEEDED, REENTRANT_CALL, REMOVED, DRAINING, CLOSED
    }
    private final Reason reason;
    private final AutomaticReplicationException.Outcome outcome;
    private final Optional<MembershipOperationId> operation;

    public MembershipOperationException(Reason reason, AutomaticReplicationException.Outcome outcome,
            Optional<MembershipOperationId> operation, String message, Throwable cause) {
        super(Objects.requireNonNull(message, "message"), cause);
        this.reason = Objects.requireNonNull(reason, "reason");
        this.outcome = Objects.requireNonNull(outcome, "outcome");
        this.operation = Objects.requireNonNull(operation, "operation");
    }
    public Reason reason() { return reason; }
    public AutomaticReplicationException.Outcome outcome() { return outcome; }
    public Optional<MembershipOperationId> operation() { return operation; }
}
