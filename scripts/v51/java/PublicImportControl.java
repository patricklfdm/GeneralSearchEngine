package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import java.nio.file.*;
import java.util.*;

/** Compiled and executed with published V4.4; its source data never comes from the candidate. */
public final class PublicImportControl {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        var docs=List.of(new Doc(3,"import-third"),new Doc(1,"import-first"),new Doc(2,"import-second"));
        var target=root.resolve("import-backup");
        try(var engine=builder().buildDurable(storage(root.resolve("control-anchor")))) {
            engine.addAll(docs).join();
            for(int i=1;i<41;i++)engine.update(new Doc(1,"import-first")).join();
            engine.backup(new DurableBackupRequest(target,1<<20)).join();
        }
        var restored=storage(root.resolve("control-restored"));builder().restoreDurableBackup(target,restored);
        try(var engine=builder().buildDurable(restored)) {
            System.out.println(AdmissionJson.canonical(Map.of("sequence",engine.currentSequence(),"documents",
                    engine.search(d->true).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList())));
        }
    }
}
