package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Caller-selected fixture policy; observations never choose a larger budget. */
enum V53NativeResourceProfile {
    SMALL_FIXTURE(512 * MembershipResources.MIB),
    DEFAULT_SNAPSHOT_STAGING(ReplicationBounds.defaults().maxSnapshotStagingBytes());

    final long stagingBytes;
    V53NativeResourceProfile(long stagingBytes) { this.stagingBytes=stagingBytes; }

    void check(MembershipBootstrapSource source,V53WireArchive.Layout layout) {
        require(this==SMALL_FIXTURE || source==MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP &&
                layout==V53WireArchive.Layout.SEGMENTED_BACKUP,"default staging requires explicit segmented backup");
    }
}
