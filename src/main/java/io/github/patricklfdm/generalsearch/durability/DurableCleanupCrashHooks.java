package io.github.patricklfdm.generalsearch.durability;

import java.util.Set;
import java.util.concurrent.locks.LockSupport;

/** Stable production transition barriers for the V4.1 cleanup crash matrix. */
final class DurableCleanupCrashHooks {
    static final String BARRIER_PROPERTY = "gse.v4.crashBarrier";
    static final String ACTION_PROPERTY = "gse.v4.crashAction";
    static final Set<String> BARRIERS = Set.of(
            "v41-cleanup-before-delete-v1",
            "v41-cleanup-after-delete-v1",
            "v41-cleanup-before-directory-force-v1",
            "v41-cleanup-after-directory-force-v1",
            "v41-cleanup-before-post-verify-v1",
            "v41-cleanup-after-post-verify-v1"
    );

    private DurableCleanupCrashHooks() {
    }

    static void reach(String barrier) {
        if (!barrier.equals(System.getProperty(BARRIER_PROPERTY))) {
            return;
        }
        if (!BARRIERS.contains(barrier)) {
            throw new IllegalArgumentException("unsupported V4.1 cleanup barrier");
        }
        System.out.println("GSE_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrier + "\",\"pid\":"
                + ProcessHandle.current().pid() + "}");
        System.out.flush();
        String action = System.getProperty(ACTION_PROPERTY, "halt");
        if (action.equals("halt")) {
            Runtime.getRuntime().halt(86);
        }
        if (!action.equals("wait")) {
            throw new IllegalArgumentException("unsupported V4.1 cleanup action");
        }
        while (barrier.equals(System.getProperty(BARRIER_PROPERTY))
                && "wait".equals(System.getProperty(ACTION_PROPERTY))) {
            LockSupport.parkNanos(1_000_000_000L);
        }
    }
}
