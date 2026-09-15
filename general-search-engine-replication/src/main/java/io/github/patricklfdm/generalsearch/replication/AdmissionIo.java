package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;

/** Package-local fault seam; public calls use ordinary synchronous filesystem operations. */
final class AdmissionIo {
    @FunctionalInterface interface Barrier { void at(String barrier) throws IOException; }
    static final ThreadLocal<Barrier> FAULTS = ThreadLocal.withInitial(() -> barrier -> { });
    private AdmissionIo() { }
    static void at(String barrier) throws IOException { FAULTS.get().at(barrier); }
}
