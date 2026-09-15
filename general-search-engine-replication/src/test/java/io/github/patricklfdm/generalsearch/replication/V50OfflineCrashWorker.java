package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Files;
import java.nio.file.Path;

/** Test-only fault coordinator. Authority operations execute solely in the public consumer. */
public final class V50OfflineCrashWorker {
    private V50OfflineCrashWorker() { }
    public static void main(String[] args) throws Exception {
        String selected = System.getProperty("gse.offline.cut", "");
        String marker = System.getProperty("gse.offline.marker", "");
        AdmissionIo.FAULTS.set(barrier -> {
            if (barrier.equals(selected)) {
                Path pending = Path.of(marker + ".pending");
                Files.writeString(pending, ProcessHandle.current().pid() + "\n" + barrier + "\n");
                Files.move(pending, Path.of(marker), java.nio.file.StandardCopyOption.ATOMIC_MOVE);
                try { new java.util.concurrent.CountDownLatch(1).await(); }
                catch (InterruptedException failure) { Thread.currentThread().interrupt(); throw new java.io.IOException(failure); }
            }
        });
        try { io.github.patricklfdm.generalsearch.admission.OfflinePublicConsumer.main(args); }
        finally { AdmissionIo.FAULTS.remove(); }
    }
}
