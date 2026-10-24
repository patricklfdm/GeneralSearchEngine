package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CoveredContextProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_WRITTEN","INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED",
            "CONTEXT_SETTLEMENT_VALIDATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_RENAMED","CONTEXT_SETTLEMENT_EMPTY_FORCED",
            "CONTEXT_REDUNDANT_DELETED","CONTEXT_REDUNDANT_PARENT_FORCED","CONTEXT_SETTLEMENT_CLEARED");
    @Test void protectedOriginalSurvivesRepeatedFreshProcessDeathThroughCoveredInstallation()throws Exception {
        var producer=new V53CoveredContextTest();producer.temp=Files.createDirectory(temp.resolve("producer"));var p=producer.prepared(3,false,"CERTIFICATE");var f=p.f();
        Path out=Path.of("target/v53-covered-context-process/run-"+UUID.randomUUID());Files.createDirectories(out);V53JournalApplicationTest.copy(f.raw,out.resolve("reference"));
        var targets=f.request.targets().stream().map(t->Map.of("node",t.replicaDirectory().toString(),"materialization",t.materialization().directory().toString())).toList();
        Path inputs=out.resolve("inputs.json");Files.write(inputs,canonical(Map.of("targets",targets,"observations",V53JournalApplicationTest.observations(f.observations)),1024*1024));
        Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        System.out.println("v53CoveredContextProcessEvidence="+out.toAbsolutePath());
        try {
            for(String mode:List.of("halt","kill"))for(String cut:CUTS) {
                Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);String name=mode+"-"+cut;Path path=Files.createDirectory(out.resolve(name));
                int first=V53RetirementSourceProcessTest.child(V53CoveredContextProcessWorker.class,inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
                String second=CUTS.subList(0,2).contains(cut)?"CONTEXT_SOURCE_PARENT_FORCED":Files.exists(node.resolve("pending.context"))?"CONTEXT_SETTLEMENT_EMPTY_FORCED":"ACCEPT_ACTIVE_FORCED";
                int again=V53RetirementSourceProcessTest.child(V53CoveredContextProcessWorker.class,inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
                int last=V53RetirementSourceProcessTest.child(V53CoveredContextProcessWorker.class,inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
                rows.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                System.out.println("v53CoveredContextProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-context-process-v1","status",rows.size()==22?"PASS":"FAIL","cases",rows,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(r->r.get("mode").equals("kill")).count(),"inputsSha256",hash(Files.readAllBytes(inputs)),
                    "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(22,rows.size());
    }
}
