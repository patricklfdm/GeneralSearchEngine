package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CoveredMinorityProfilesTest {
    @TempDir Path temp;
    @Test void allAdmittedInitialProfilesSettleOnlyCoveredBareVotes()throws Exception {
        Path out=Path.of("target/v53-covered-minority-profiles/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53CoveredMinorityProfilesEvidence="+out.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                String name="size-"+size+"-"+(backup?"backup":"empty");var producer=new V53CoveredMinorityTest();producer.temp=Files.createDirectory(temp.resolve(name));
                var p=producer.prepared(size,backup);producer.complete(p);var f=p.f();V53JournalApplicationTest.copy(f.raw,out.resolve(name));
                assertEquals(0,f.resources.usage().leases());
                rows.add(Map.of("case",name,"status","PASS","voters",size,"minority",size-(size/2+1),"nodePublications",size+size/2+1,
                        "peakImages",f.peakImages,"sequence",f.result.applicationSequence()+1));
                System.out.println("v53CoveredMinorityProfile="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-minority-profiles-v1","status",rows.size()==6?"PASS":"FAIL","cases",rows,
                    "publicBootstrap",true,"freshProcesses",false,"publicRuntime",false),65536));
        }
        assertEquals(6,rows.size());
    }
}
