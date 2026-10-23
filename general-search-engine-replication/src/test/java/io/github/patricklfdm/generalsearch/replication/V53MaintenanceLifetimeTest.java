package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Coordinated installation/floor/source maintenance, with two successive fresh-process interruptions. */
class V53MaintenanceLifetimeTest {
    static final List<List<String>> CUTS=List.of(
            List.of("INSTALL_MANIFEST_FORCED","INSTALL_GENERATION_FORCED"),
            List.of("INSTALL_SELECTOR_RENAMED","FLOOR_COPIES_FORCED"),
            List.of("FLOOR_AUTHORITY_FORCED","RETIREMENT_AUTHORITY_FORCED"),
            List.of("RETIREMENT_FILE_DELETED","RETIREMENT_AUTHORITY_RESEALED"),
            List.of("SOURCE_RETIREMENT_FORCED","JOURNAL_ROTATION_FORCED"),
            List.of("JOURNAL_ROTATION_RENAMED","SOURCE_RETIREMENT_FORCED"),
            List.of("SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_FORCED"),
            List.of("FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_AUTHORITY_FORCED"),
            List.of("FLOOR_RELEASE_AUTHORITY_CLEARED","FLOOR_RELEASE_CLEARED"));
    @Test void originalSelectedMaintenanceSurvivesTwoCrashesAndSettlesWithoutRecreatingAFloor()throws Exception {
        Path root=Path.of("target/v53-maintenance-lifetime").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);
        Path seed=root.resolve("seed");var f=new V53PublicationLifetimeTest.Fixture(seed);f.cycle(1);var setup=f.prepare(2);
        Files.createDirectory(seed.resolve("inputs"));
        for(int n:List.of(1,2,3))V53JournalApplicationTest.copy(f.node(n),seed.resolve("inputs/node-"+n));
        for(int n:List.of(2,3))try(var store=f.open(n)){store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images());}
        var bridge=f.bridges.getFirst();Files.write(seed.resolve("parent-statement.gsr"),bridge.statement.bytes());
        for(var ack:bridge.acknowledgements)Files.write(seed.resolve("parent-"+((String)ack.value().get("voter")).substring(5)+".gsr"),ack.bytes());
        Files.write(seed.resolve("inputs.json"),canonical(Map.of("observations",V53JournalApplicationTest.observations(f.observations),
                "parents",V53JournalApplicationTest.observations(bridge.owned),"obsolete",setup.obsolete().get(1),"rounds",f.rows),65536));
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(var cuts:CUTS) {
                String cut=cuts.getFirst(),again=cuts.getLast();Path work=root.resolve(mode+"-"+cut);V53JournalApplicationTest.copy(seed,work);
                Path node=work.resolve("node-1");V53JournalApplicationTest.copy(node,work.resolve("original"));
                V53JournalPublicationTest.child(work,"fault",cut,mode,V53MaintenanceLifetimeWorker.class);V53JournalApplicationTest.copy(node,work.resolve("crash"));
                V53JournalPublicationTest.child(work,"recovery-fault",again,"halt",V53MaintenanceLifetimeWorker.class);V53JournalApplicationTest.copy(node,work.resolve("recovery-crash"));
                V53JournalPublicationTest.child(work,"resume","none","none",V53MaintenanceLifetimeWorker.class);V53JournalApplicationTest.copy(node,work.resolve("final"));
                var finished=V53ReplayFilesTest.files(node);
                V53JournalPublicationTest.child(work,"duplicate","none","none",V53MaintenanceLifetimeWorker.class);
                assertEquals(finished,V53ReplayFilesTest.files(node));
                for(String immutable:List.of("root.gsr","genesis.gsr","node.gsr","allocator.gsr","pending.accept"))
                    assertArrayEquals(Files.readAllBytes(work.resolve("original/"+immutable)),Files.readAllBytes(node.resolve(immutable)));
                assertFalse(Files.exists(node.resolve("generations/a")));assertFalse(Files.exists(node.resolve("floor-copies")));
                assertFalse(Files.exists(node.resolve("sources/"+setup.obsolete().get(1))));
                try(var files=Files.list(node.resolve("sources"))){assertEquals(1,files.count());}
                assertArrayEquals(Files.readAllBytes(work.resolve("inputs/node-1/generations/a/ancestry.gsr")),Files.readAllBytes(node.resolve("generations/b/ancestry.gsr")));
                rows.add(Map.of("mode",mode,"cut",cut,"recoveryCut",again,"status","PASS"));
                System.out.println("v53MaintenanceLifetimeCase="+mode+"-"+cut+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",18L,"freshJvms",(long)rows.size()*4,
                    "execution","private-coordinated-maintenance","historicalBootstrap","conditional-fixture","runtimeEnabled",false,"powerLoss",false),65536));
            System.out.println("v53MaintenanceLifetimeEvidence="+root.toAbsolutePath());
        }
        assertEquals(18,rows.size());
    }
}
