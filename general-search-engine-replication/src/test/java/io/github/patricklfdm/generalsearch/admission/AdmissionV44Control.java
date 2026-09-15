package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.Path;
import java.util.Map;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;

/** Separately compiled published V4.4 backup producer and restore/query oracle. */
public final class AdmissionV44Control {
    private AdmissionV44Control() { }
    public static void main(String[] args) throws Exception {
        System.err.println("controlSource=" + Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        String command = args[0]; Path root = Path.of(args[1]); int minor = Integer.parseInt(args[2]);
        if (command.equals("simple-source")) {
            var config = OfflineApplication.storage(root.resolve("live"), minor);
            try (var engine = OfflineApplication.builder().buildDurable(config)) {
                engine.addAll(java.util.List.of(new OfflineApplication.Doc(3, "shared"), new OfflineApplication.Doc(1, "shared"))).join();
                var result = engine.backup(new DurableBackupRequest(root.resolve("source"), 1 << 20)).join();
                System.out.println(AdmissionJson.canonical(Map.of("history", result.sourceHistory().toString(), "sequence", result.sequence())));
            }
            return;
        }
        var builder = AdmissionSemanticModel.builder();
        var config = AdmissionSemanticModel.storage(root.resolve(command.equals("create") ? "live" : "restored"), minor);
        if (command.equals("restore")) builder.restoreDurableBackup(Path.of(args[3]), config);
        try (var engine = builder.buildDurable(config)) {
            if (command.equals("create")) {
                AdmissionSemanticModel.populate(engine);
                engine.backup(new DurableBackupRequest(root.resolve("source"), 1 << 20)).join();
            }
            System.out.println(AdmissionJson.canonical(Map.of("sequence", engine.currentSequence(), "semantics", AdmissionSemanticModel.report(engine))));
        }
    }
}
