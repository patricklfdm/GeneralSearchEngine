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
            "v4-recovery-before-ready-publication-v1"
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
        while (true) {
            LockSupport.parkNanos(1_000_000_000L);
        }
    }
}
