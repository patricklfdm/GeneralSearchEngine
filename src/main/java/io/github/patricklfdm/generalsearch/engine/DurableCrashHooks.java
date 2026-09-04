package io.github.patricklfdm.generalsearch.engine;

import java.util.Set;
import java.util.concurrent.locks.LockSupport;

final class DurableCrashHooks {
    static final String BARRIER_PROPERTY = "gse.v4.crashBarrier";
    static final String ACTION_PROPERTY = "gse.v4.crashAction";
    static final Set<String> BARRIERS = Set.of(
            "v4-wal-before-sequence-v1",
            "v4-wal-after-sequence-v1",
            "v4-wal-partial-header-v1",
            "v4-wal-partial-payload-v1",
            "v4-wal-partial-trailer-v1",
            "v4-wal-complete-before-force-v1",
            "v4-wal-after-force-v1",
            "v4-wal-before-publication-v1",
            "v4-wal-after-publication-v1",
            "v4-wal-before-future-completion-v1",
            "v4-recovery-after-tail-truncate-v1",
            "v4-recovery-after-replay-v1",
            "v4-recovery-before-ready-publication-v1",
            "v4-checkpoint-after-old-wal-force-v1",
            "v4-checkpoint-after-new-wal-header-force-v1",
            "v4-checkpoint-partial-data-v1",
            "v4-checkpoint-after-data-force-v1",
            "v4-checkpoint-after-data-publication-v1",
            "v4-checkpoint-partial-manifest-v1",
            "v4-checkpoint-after-manifest-force-v1",
            "v4-checkpoint-after-manifest-rename-v1",
            "v4-checkpoint-after-directory-force-v1",
            "v4-checkpoint-before-wal-cleanup-v1",
            "v4-checkpoint-after-wal-cleanup-v1",
            "v41-backup-before-writer-cut-v1",
            "v41-backup-after-b-selection-v1",
            "v41-backup-after-wal-cut-v1",
            "v41-backup-after-source-checkpoint-authority-v1",
            "v41-backup-after-checkpoint-pin-v1",
            "v41-backup-after-marker-force-v1",
            "v41-backup-during-metadata-copy-v1",
            "v41-backup-after-metadata-force-v1",
            "v41-backup-during-checkpoint-copy-v1",
            "v41-backup-after-checkpoint-force-v1",
            "v41-backup-after-manifest-force-v1",
            "v41-backup-after-manifest-rename-v1",
            "v41-backup-before-final-rename-v1",
            "v41-backup-after-final-rename-v1",
            "v41-backup-after-parent-force-v1",
            "v41-backup-before-future-completion-v1",
            "v41-restore-after-marker-force-v1",
            "v41-restore-after-metadata-force-v1",
            "v41-restore-after-checkpoint-rename-v1",
            "v41-restore-after-wal-force-v1",
            "v41-restore-after-manifest-force-v1",
            "v41-restore-after-manifest-rename-v1",
            "v41-restore-before-final-rename-v1",
            "v41-restore-after-final-rename-v1",
            "v41-restore-after-parent-force-v1",
            "v41-restore-before-return-v1",
            "v41-cleanup-before-delete-v1",
            "v41-cleanup-after-delete-v1",
            "v41-cleanup-before-directory-force-v1",
            "v41-cleanup-after-directory-force-v1",
            "v41-cleanup-before-post-verify-v1",
            "v41-cleanup-after-post-verify-v1",
            "v42-migration-after-marker-force-v1",
            "v42-migration-after-metadata-force-v1",
            "v42-migration-after-checkpoint-rename-v1",
            "v42-migration-after-wal-force-v1",
            "v42-migration-after-manifest-rename-v1",
            "v42-migration-before-final-rename-v1",
            "v42-migration-after-final-rename-v1",
            "v42-migration-after-parent-force-v1"
    );

    private DurableCrashHooks() {
    }

    static boolean active(String barrierId) {
        return barrierId.equals(System.getProperty(BARRIER_PROPERTY));
    }

    static void reach(String barrierId) {
        if (!active(barrierId)) {
            return;
        }
        if (!BARRIERS.contains(barrierId)) {
            throw new IllegalArgumentException("unsupported V4 crash barrier");
        }
        long pid = ProcessHandle.current().pid();
        System.out.println("GSE_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrierId + "\",\"pid\":" + pid + "}");
        System.out.flush();
        String action = System.getProperty(ACTION_PROPERTY, "halt");
        if (action.equals("halt")) {
            Runtime.getRuntime().halt(86);
        }
        if (!action.equals("wait")) {
            throw new IllegalArgumentException("unsupported V4 crash action");
        }
        while (active(barrierId)
                && "wait".equals(System.getProperty(ACTION_PROPERTY))) {
            LockSupport.parkNanos(1_000_000_000L);
        }
    }
}
