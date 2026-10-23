package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Six historical bridge groups are conditional; all new votes and ends are actual owners. */
class V53AncestryPruningTest {
    static final List<String> CUTS=List.of("SELECTED_SOURCES_WRITTEN","SELECTED_SOURCES_FORCED","PUBLICATION_SELECTOR_FORCED",
            "COVERED_END_FILE_DELETED","COVERED_VOTE_PREFIX_WRITTEN");
    static void prepare(Path root)throws Exception {
        var f=new V53PublicationAdmissionTest.Fixture(root,6,true);var cohort=V53PublicationAdmissionTest.certify(f,false);
        var historical=new HashSet<>(f.f.f.fixture.owned);var checkpoints=new HashSet<Owned>();var parents=new HashSet<Owned>();
        Path generation=f.node().resolve("generations/b");
        var manifest=decode(Files.readAllBytes(generation.resolve("generation.gsr")),"records","GENERATION");
        Files.write(root.resolve("base.image"),Files.readAllBytes(generation.resolve(manifest.value().get("application")+".image")));
        for(int n:List.of(2,3))try(var store=f.open(n,new ArrayList<>())) {
            var applied=store.applyCurrent(f.application.configuration(),f.application.storage(),cohort.owned());
            assertTrue(applied.plan().additionalParents().isEmpty());var parent=applied.endorsement().parent().orElseThrow();
            checkpoints.add(applied.endorsement().owned());parents.add(parent.owned());
            Files.write(root.resolve("ack-node-"+n+".gsr"),applied.endorsement().acknowledgement().bytes());
            Files.write(root.resolve("parent-node-"+n+".gsr"),parent.acknowledgement().bytes());
            Path statement=root.resolve("parent-statement.gsr");
            if(Files.exists(statement))assertArrayEquals(Files.readAllBytes(statement),parent.statement().bytes());else Files.write(statement,parent.statement().bytes());
        }
        Files.write(root.resolve("observations.json"),canonical(Map.of("accepts",V53JournalApplicationTest.observations(cohort.accepts()),
                "proofs",V53JournalApplicationTest.observations(cohort.proofs()),"checkpoints",V53JournalApplicationTest.observations(checkpoints),
                "parents",V53JournalApplicationTest.observations(parents),"historical",V53AncestorCheckpointTest.observations(historical)),65536));
    }
    @Test void sixOldGroupsBecomeOneOnlyAfterExactPublicationAcrossRepeatedProcessCrashes()throws Exception {
        Path retained=Path.of("target/v53-ancestry-pruning-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String cut:CUTS) {
                Path root=retained.resolve(mode+"-"+cut);prepare(root);Path node=root.resolve("node-1");V53JournalApplicationTest.copy(node,root.resolve("original"));
                V53JournalPublicationTest.child(root,"fault",cut,mode,V53AncestryPruningWorker.class);V53JournalApplicationTest.copy(node,root.resolve("crash"));
                String again=V53JournalPublicationTest.recoveryPoint(node);
                V53JournalPublicationTest.child(root,"recovery-fault",again,"halt",V53AncestryPruningWorker.class);V53JournalApplicationTest.copy(node,root.resolve("recovery-crash"));
                V53JournalPublicationTest.child(root,"resume","none","none",V53AncestryPruningWorker.class);V53JournalApplicationTest.copy(node,root.resolve("final"));
                V53JournalPublicationTest.preserved(node,V53ReplayFilesTest.files(root.resolve("original")));
                assertArrayEquals(Files.readAllBytes(root.resolve("original/generations/b/selected-sources.gsr")),Files.readAllBytes(node.resolve("generations/a/selected-sources.gsr")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                rows.add(Map.of("mode",mode,"cut",cut,"recoveryCut",again,"status","PASS","manifest",selector.value().get("digest")));
                System.out.println("v53AncestryPruningCase="+mode+"-"+cut+" PASS");
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",10L,"freshJvms",(long)rows.size()*3,
                    "execution","private-ancestry-pruning-publication","historicalAuthority","conditional-fixture","currentObservations","actual-local-votes-and-ends",
                    "selectorPublication",true,"powerLoss",false),65536));
            System.out.println("v53AncestryPruningEvidence="+retained.toAbsolutePath());
        }
        assertEquals(10,rows.size());
    }
}
