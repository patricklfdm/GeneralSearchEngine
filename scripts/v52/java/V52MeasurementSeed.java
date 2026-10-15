package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import static io.github.patricklfdm.generalsearch.admission.V52MeasurementQueries.*;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import java.nio.file.*;
import java.util.*;

/** One real published V4.4 backup shared by the independent fresh fixture histories. */
public final class V52MeasurementSeed {
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);
        System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        var corpus=(List<Map<String,Object>>)AdmissionJson.parse(Files.readString(Path.of(args[1])));
        if(corpus.size()!=64)throw new IllegalArgumentException("measurement seed corpus count");
        try(var engine=measurementBuilder().buildDurable(V52MeasurementQueries.storage(root.resolve("store")))) {
            engine.addAll(corpus.stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList()).join();
            engine.backup(new DurableBackupRequest(root.resolve("seed"),1<<20)).join();
            if(engine.currentSequence()!=1)throw new IllegalStateException("measurement seed sequence");
            System.out.println(AdmissionJson.canonical(Map.of("status","PASS","sequence",engine.currentSequence(),"documents",corpus.size())));
        }
    }
}
