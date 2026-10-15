package io.github.patricklfdm.generalsearch.replication;

import java.util.UUID;

/** One application-worker publication. Generation is process-local and never token authority. */
record AutomaticReadCut(ReplicationGroupId group, UUID history, String manifest,
                        long index, long sequence, long generation) {
    ReplicaReadToken token() {
        return new ReplicaReadToken(1, group, history, manifest, index);
    }

    void compatible(ReplicaReadToken minimum) {
        if (!group.equals(minimum.groupId()) || !history.equals(minimum.historyId())
                || !manifest.equals(minimum.manifestDigest()))
            throw new ReplicaReadException(ReplicaReadException.Reason.INCOMPATIBLE_HISTORY,
                    "replica read identity differs from the verified manifest");
    }
}
