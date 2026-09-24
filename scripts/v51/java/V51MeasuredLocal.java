package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.durability.*;
import java.nio.file.*;
import java.util.*;

/** Published V4.4 only: prepare, timed public calls, checkpoint and public restore. */
public final class V51MeasuredLocal {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]),source=Path.of(args[3]);var plan=V51RichWorkload.plan(Path.of(args[2]));
        if(args[1].equals("prepare")) {
            try(var engine=V51RichWorkload.builder().buildDurable(V51RichWorkload.storage(root.resolve("seed")))) {
                V51RichWorkload.populate(engine,plan);engine.backup(new DurableBackupRequest(source,16L<<20)).join();
            }
            return;
        }
        if(args[1].equals("reopen")) {
            try(var engine=V51RichWorkload.builder().buildDurable(V51RichWorkload.storage(root.resolve("store")))) {
                V51Measurement.print(Map.of("sequence",engine.durabilityMetrics().currentSequence(),"indexCount",engine.metrics().registeredIndexCount(),
                        "documents",engine.search(d->true).stream().map(d->List.of(d.id(),d.title(),d.category(),d.price(),d.body())).toList()));
            }
            return;
        }
        if(args[1].equals("restore")) {
            var storage=V51RichWorkload.storage(root.resolve("restored"));V51RichWorkload.builder().restoreDurableBackup(source,storage);
            try(var engine=V51RichWorkload.builder().buildDurable(storage)) {
                V51Measurement.print(Map.of("sequence",engine.durabilityMetrics().currentSequence(),"indexCount",engine.metrics().registeredIndexCount(),
                        "documents",engine.search(d->true).stream().map(d->List.of(d.id(),d.title(),d.category(),d.price(),d.body())).toList()));
            }
            return;
        }
        var storage=V51RichWorkload.storage(root.resolve("store"));
        V51RichWorkload.builder().restoreDurableBackup(source,storage);
        try(var engine=V51RichWorkload.builder().buildDurable(storage);
            var measurement=new V51Measurement(root,"local","published-v4.4-local",engine,plan,()->Map.of("state","READY","sequence",engine.durabilityMetrics().currentSequence()))) {
            V51Measurement.print(Map.of("status","STARTED","identity",V51Measurement.identity("published-v4.4-local","local",plan,null)));
            measurement.loop();
        }
    }
}
