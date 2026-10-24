package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53HiddenStagingProcessTest {
    @TempDir Path temp;
    @Test void hiddenDerivedCleanupSurvivesRepeatedFreshProcessDeath()throws Exception {
        var producer=new V53HiddenStagingTest();producer.temp=Files.createDirectory(temp.resolve("producer"));var helper=producer.helper();var p=producer.prepared(helper,3,false);var f=p.f();
        Files.write(f.raw.resolve("applied-ancestry.gsr"),MembershipGenerationPlan.ancestry(V53HiddenStagingTest.bridges(p)));
        var proof=V53HiddenStagingTest.bridges(p).getFirst();
        var offered=Map.of("statement",HexFormat.of().formatHex(proof.statement.bytes()),"acknowledgements",proof.acknowledgements.stream().map(v->HexFormat.of().formatHex(v.bytes())).toList());
        Path out=Path.of("target/v53-hidden-staging-process/run-"+UUID.randomUUID());Files.createDirectories(out);V53JournalApplicationTest.copy(f.raw,out.resolve("reference"));
        var targets=f.request.targets().stream().map(t->Map.of("node",t.replicaDirectory().toString(),"materialization",t.materialization().directory().toString())).toList();
        Path inputs=out.resolve("inputs.json");Files.write(inputs,canonical(Map.of("targets",targets,"observations",V53JournalApplicationTest.observations(f.observations),"appliedAncestry",offered),1024*1024));
        Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        var cuts=V53CoveredStagingTest.CUTS.stream().filter(s->!s.startsWith("REPLAY_")).toList();assertEquals(16,cuts.size());
        System.out.println("v53HiddenStagingProcessEvidence="+out.toAbsolutePath());
        try {
            for(String mode:List.of("halt","kill"))for(String cut:cuts) {
                Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);String name=mode+"-"+cut;Path path=Files.createDirectory(out.resolve(name));
                int first=V53RetirementSourceProcessTest.child(V53HiddenStagingProcessWorker.class,inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
                String second=Set.of("STAGED_RETIREMENT_BEFORE_RETURN","SUPERSEDED_END_DIRECTORY_DELETED").contains(cut)?"CERTIFICATE_ACTIVE_FORCED":"SUPERSEDED_END_AUTHORITY_FORCED";
                int again=V53RetirementSourceProcessTest.child(V53HiddenStagingProcessWorker.class,inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
                int last=V53RetirementSourceProcessTest.child(V53HiddenStagingProcessWorker.class,inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
                rows.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                System.out.println("v53HiddenStagingProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-hidden-staging-process-v1","status",rows.size()==32?"PASS":"FAIL","cases",rows,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(r->r.get("mode").equals("kill")).count(),"inputsSha256",hash(Files.readAllBytes(inputs)),
                    "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(32,rows.size());
    }
}
