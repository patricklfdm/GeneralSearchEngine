package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** The real nonvoting owner's inherited intent survives adoption-selector and
 * ledger-promotion death; no reconstructed remote vote observations are supplied. */
class V53InheritedFutureAdoptionProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("ADOPTION_INSTALL_FENCED","INSTALL_SELECTOR_FORCED","INSTALL_SELECTOR_RENAMED",
            "RETENTION_PREFIX_WRITTEN","RETENTION_RENAMED","INHERITED_FUTURE_RETENTION_PROMOTED","ADOPTION_INSTALL_BEFORE_RETURN");
    @Test void inheritedObligationsSurviveProcessDeathDuringRemovedOwnerAdoption()throws Exception {
        Path out=Files.createDirectories(Path.of("target/v53-inherited-adoption-process/run-"+UUID.randomUUID()));
        Path raw=Files.createDirectory(out.resolve("reference")),samples=Files.createDirectory(out.resolve("cases"));
        System.out.println("v53InheritedAdoptionProcessEvidence="+out.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        boolean success=false;
        try {
            V53InheritedFutureAdoptionTest.history(temp,raw,(f,walk)->{
                walk.beforeAdoption=(target,remote)->{
                    Path node=target.replicaDirectory(),seed=temp.resolve("seed"),inputs=out.resolve("inputs.json");
                    V53JournalApplicationTest.copy(node,seed);var source=f.request.targets().getFirst();
                    var sourceBefore=V53ReplayFilesTest.files(source.replicaDirectory());
                    Files.write(inputs,canonical(Map.of("node",node.toString(),"materialization",target.materialization().directory().toString(),
                            "source",source.replicaDirectory().toString(),"sourceMaterialization",source.materialization().directory().toString()),65536));
                    int ordinal=0;
                    for(String mode:List.of("halt","kill"))for(String cut:CUTS) {
                        Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);
                        Path sample=Files.createDirectory(samples.resolve(mode+"-"+cut));
                        int stopped=V53RetirementSourceProcessTest.child(V53OwnedAdoptionProcessWorker.class,inputs,node,sample,"fault",cut,mode);
                        V53JournalApplicationTest.copy(node,sample.resolve("interrupted"));
                        int resumed=V53RetirementSourceProcessTest.child(V53OwnedAdoptionProcessWorker.class,inputs,node,sample,"resume","none","none");
                        V53JournalApplicationTest.copy(node,sample.resolve("recovered"));
                        assertEquals(sourceBefore,V53ReplayFilesTest.files(source.replicaDirectory()));
                        rows.add(Map.of("mode",mode,"cut",cut,"status","PASS","exitCodes",List.of(stopped,resumed)));
                        System.out.println("v53InheritedAdoptionProcessCase="+mode+"-"+cut+" PASS");System.out.flush();
                    }
                    Files.move(node,temp.resolve("last"));V53JournalApplicationTest.copy(seed,node);
                };
            });
            assertEquals(14,rows.size());success=true;
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-inherited-adoption-process-v1","status",success?"PASS":"FAIL",
                    "cases",rows,"freshProcesses",rows.size()*2,"lockProbes",rows.stream().filter(r->r.get("mode").equals("kill")).count(),
                    "publicRuntime",false,"powerLoss",false),65536));
        }
    }
}
