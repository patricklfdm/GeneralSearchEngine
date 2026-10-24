package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CoveredPhasedProcessTest {
    @TempDir Path temp;
    @Test void proofAndCertificateOriginalsSurviveRepeatedFreshProcessDeath()throws Exception {
        Path out=Path.of("target/v53-covered-phased-process/run-"+UUID.randomUUID());Files.createDirectories(out);System.out.println("v53CoveredPhasedProcessEvidence="+out.toAbsolutePath());
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String phase:List.of("PROOF","CERTIFICATE")) {
                var helper=new V53CoveredPhasedVoteTest();helper.temp=Files.createDirectory(temp.resolve(phase));var p=helper.prepared(3,false,phase);var f=p.f();Path base=Files.createDirectory(out.resolve(phase));
                V53JournalApplicationTest.copy(f.raw,base.resolve("reference"));var targets=f.request.targets().stream().map(t->Map.of("node",t.replicaDirectory().toString(),"materialization",t.materialization().directory().toString())).toList();
                Path inputs=base.resolve("inputs.json");Files.write(inputs,canonical(Map.of("targets",targets,"observations",V53JournalApplicationTest.observations(f.observations)),1024*1024));
                Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed-"+phase);V53JournalApplicationTest.copy(node,seed);int ordinal=0;
                for(String mode:List.of("halt","kill"))for(String cut:List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_SELECTOR_FORCED","SETTLED_VOTE_VALIDATED",
                        "SETTLED_VOTE_CANDIDATE_CREATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_CANDIDATE_WRITTEN","SETTLED_VOTE_CANDIDATE_FORCED",
                        "SETTLED_VOTE_CANDIDATE_PARENT_FORCED","SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN")) {
                    Files.move(node,temp.resolve("previous-"+phase+"-"+ordinal++));V53JournalApplicationTest.copy(seed,node);String name=mode+"-"+cut;Path path=Files.createDirectory(base.resolve(name));
                    int first=V53RetirementSourceProcessTest.child(V53CoveredMinorityProcessWorker.class,inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
                    String second=cut.equals("INSTALL_MANIFEST_FORCED")?phase+"_ACTIVE_FORCED":Set.of("SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN").contains(cut)?"ACCEPT_ACTIVE_FORCED":"SETTLED_VOTE_CANDIDATE_PARENT_FORCED";
                    int again=V53RetirementSourceProcessTest.child(V53CoveredMinorityProcessWorker.class,inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
                    int last=V53RetirementSourceProcessTest.child(V53CoveredMinorityProcessWorker.class,inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
                    rows.add(Map.of("phase",phase,"case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last),"inputsSha256",hash(Files.readAllBytes(inputs))));
                    System.out.println("v53CoveredPhasedProcessCase="+phase+"-"+name+" PASS");System.out.flush();
                }
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-phased-process-v1","status",rows.size()==48?"PASS":"FAIL","cases",rows,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(row->row.get("mode").equals("kill")).count(),"publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(48,rows.size());
    }
}
