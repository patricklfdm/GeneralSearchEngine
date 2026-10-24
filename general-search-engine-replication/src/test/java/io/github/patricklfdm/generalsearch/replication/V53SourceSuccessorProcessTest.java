package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceSuccessorProcessTest {
    @TempDir Path temp;
    @Test void forcedSuccessorRetirementSurvivesRepeatedFreshProcessDeath()throws Exception {
        Path out=Path.of("target/v53-source-successor-process/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53SourceSuccessorProcessEvidence="+out.toAbsolutePath());
        var producer=new V53CoveredContextMixedTest();producer.temp=Files.createDirectory(temp.resolve("producer"));var rows=new ArrayList<Map<String,Object>>();
        var mixed=producer.prepared(4,false,(f,ids)->{
            var target=f.request.targets().getFirst();Path node=target.replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
            Path inputs=out.resolve("inputs.json");Files.write(inputs,canonical(Map.of("node",node.toString(),"materialization",target.materialization().directory().toString(),
                    "source",ids.get("node-1"),"voteSha256",hash(Files.readAllBytes(node.resolve("pending.accept"))),
                    "observations",V53JournalApplicationTest.observations(f.observations)),1024*1024));int ordinal=0;
            for(String mode:List.of("halt","kill"))for(String cut:V53SourceReleaseWorker.CUTS) {
                Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);String name=mode+"-"+cut;Path path=Files.createDirectory(out.resolve(name));
                int first=V53RetirementSourceProcessTest.child(V53SourceSuccessorProcessWorker.class,inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
                String second=Set.of("SOURCE_RETIREMENT_CLEARED","SOURCE_RETIREMENT_BEFORE_RETURN").contains(cut)?"ACCEPT_ACTIVE_FORCED":"SOURCE_RETIREMENT_JOURNAL_PRUNED";
                int again=V53RetirementSourceProcessTest.child(V53SourceSuccessorProcessWorker.class,inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
                int last=V53RetirementSourceProcessTest.child(V53SourceSuccessorProcessWorker.class,inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
                rows.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                System.out.println("v53SourceSuccessorProcessCase="+name+" PASS");System.out.flush();
            }
            Files.move(node,temp.resolve("last"));V53JournalApplicationTest.copy(seed,node);
        });
        V53CoveredContextMixedTest.complete(mixed);V53JournalApplicationTest.copy(mixed.prepared().f().raw,out.resolve("reference"));
        Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-source-successor-process-v1","status","PASS","cases",rows,
                "freshProcesses",rows.size()*3,"lockProbes",rows.size()/2,"inputsSha256",hash(Files.readAllBytes(out.resolve("inputs.json"))),
                "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        assertEquals(30,rows.size());
    }
}
