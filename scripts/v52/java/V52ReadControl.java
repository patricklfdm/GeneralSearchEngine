package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import java.nio.file.*;
import java.util.*;

/** Runs with the pinned published core only; no replication API or candidate classpath. */
public final class V52ReadControl {
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);
        System.err.println("controlSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        if(args[1].equals("seed")) {
            try(var engine=builder().buildDurable(storage(root.resolve("control-store")))) {
                engine.addAll(List.of(new Doc(1,"java search"),new Doc(3,"java memory search"),new Doc(7,"query search"),new Doc(9,"removed"))).join();
                engine.remove(9).join();engine.update(new Doc(3,"java memory tuned search")).join();engine.add(new Doc(5,"java query search")).join();
                engine.backup(new DurableBackupRequest(root.resolve("seed"),1<<20)).join();
                System.out.println(AdmissionJson.canonical(report(core(engine))));
            }
        } else if(args[1].equals("oracle")) {
            var input=(Map<String,Object>)AdmissionJson.parse(Files.readString(Path.of(args[2])));
            var target=storage(root.resolve("restored"));builder().restoreDurableBackup(Path.of(args[3]),target);
            try(var engine=builder().buildDurable(target)) {
                for(var command:(List<Map<String,Object>>)input.get("commands")) {
                    int operation=((Number)command.get("operation")).intValue();
                    var docs=((List<Map<String,Object>>)command.get("documents")).stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList();
                    switch(operation) {
                        case 1 -> engine.add(docs.getFirst()).join();
                        case 2 -> engine.update(docs.getFirst()).join();
                        case 3 -> engine.remove(((Number)((List<?>)command.get("keys")).getFirst()).intValue()).join();
                        case 4 -> engine.addAll(docs).join();
                        case 5 -> engine.updateAll(docs).join();
                        case 6 -> engine.removeAll(((List<Number>)command.get("keys")).stream().map(Number::intValue).toList()).join();
                        case 7 -> {
                            var index=(Map<String,Object>)command.get("index");
                            if(!index.equals(Map.of("field","id","kind","equality","analyzer","")))
                                throw new IllegalArgumentException("undeclared control index");
                            engine.createIndex(IndexDefinition.equality(ID)).join();
                        }
                        case 8 -> engine.dropIndex((String)command.get("field")).join();
                        case 9 -> {if(!docs.isEmpty())throw new IllegalArgumentException("NO_OP documents");}
                        default -> throw new IllegalArgumentException("unsupported declared fixture operation");
                    }
                }
                if(engine.currentSequence()!=((Number)input.get("sequence")).longValue())throw new IllegalStateException("control sequence differs");
                System.out.println(AdmissionJson.canonical(report(core(engine))));
            }
        } else throw new IllegalArgumentException("unknown control operation");
    }
}
