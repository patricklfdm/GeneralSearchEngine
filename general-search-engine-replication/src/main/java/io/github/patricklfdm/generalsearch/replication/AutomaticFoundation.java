package io.github.patricklfdm.generalsearch.replication;

import java.util.Optional;

/** Shared fail-before-effects guard; no transport/store/election implementation. */
final class AutomaticFoundation {
    private AutomaticFoundation() { }
    static AutomaticReplicationException unavailable() {
        return new AutomaticReplicationException(AutomaticReplicationException.Reason.NOT_READY,
                AutomaticReplicationException.Outcome.NOT_APPLICABLE, Optional.empty(),
                "automatic replication runtime and storage operations are not enabled in Phase 1");
    }
}
