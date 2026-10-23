package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Sequential fresh child JVMs over private offline copies of one actual three-owner seed. */
class V53RoundProcessTest {
    static final List<List<String>> CUTS=List.of(
            List.of("ACCEPT_PREFIX_WRITTEN","ACCEPT_CANDIDATE_FORCED"),
            List.of("PROOF_PREFIX_WRITTEN","PROOF_CANDIDATE_FORCED"),
            List.of("CERTIFICATE_PREFIX_WRITTEN","CERTIFICATE_CANDIDATE_FORCED"),
            List.of("APPLY_ANCESTOR_0_ACK_PREFIX_WRITTEN","APPLY_ANCESTOR_0_ACK_FORCED"),
            List.of("ROUND_COVERAGE_WRITTEN","ROUND_COVERAGE_FORCED"),
            List.of("ROUND_COVERAGE_FORCED","INSTALL_GENERATION_FORCED"),
            List.of("INSTALL_SELECTOR_RENAMED","COVERED_VOTE_CANDIDATE_FORCED"),
            List.of("PUBLICATION_SELECTOR_FORCED","COVERED_END_FILE_DELETED"),
            List.of("COVERED_END_FILE_DELETED","COVERED_VOTE_PREFIX_WRITTEN"),
            List.of("COVERED_VOTE_PREFIX_WRITTEN","COVERED_VOTE_CANDIDATE_FORCED"),
            List.of("COVERED_VOTE_RENAMED","ACCEPT_ACTIVE_FORCED"));
    @Test void originalRoundSurvivesRepeatedProcessCrashesFromVoteThroughCoveredCleanup()throws Exception {
        Path root=Path.of("target/v53-round-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);Path seed=root.resolve("seed");
        var f=new V53RoundStorageTest.Fixture(seed);f.finish(f.apply(f.entry("BARRIER",new byte[0]),new byte[0]));
        for(int n:List.of(1,2,3)) {
            Path snapshot=seed.resolve("snapshots/slot-2/node-"+n);Files.createDirectories(snapshot.getParent());V53JournalApplicationTest.copy(f.f.node(n),snapshot);
        }
        byte[] payload;try(var encoder=f.f.initial.application.app.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(103,"round-3"))));
        }
        f.apply(f.entry("DATA",payload),payload);
        var accepts=new HashSet<MembershipContext.Owned>();var proofs=new HashSet<MembershipContext.Owned>();
        for(int n:List.of(1,2,3))try(var store=f.f.open(n)) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve("pending.accept")));String parent=MembershipContext.cutDigest(store.floorCopyCurrent().capsule.context.cut);
            accepts.add(new MembershipContext.Owned("node-"+n,V53DeclarationsTest.node(n).storageId(),vote.accept().digest(),parent));
            proofs.add(new MembershipContext.Owned("node-"+n,V53DeclarationsTest.node(n).storageId(),vote.proof().digest(),parent));
        }
        var actualRecords=new HashSet<String>();
        for(int slot:List.of(1,2,3))for(int n:List.of(1,2,3)) {
            Path original=seed.resolve("originals/slot-"+slot+"/node-"+n);var vote=MembershipPendingAccept.decode(Files.readAllBytes(original.resolve("pending.accept")));
            actualRecords.add(vote.accept().digest());actualRecords.add(vote.proof().digest());
            try(var files=Files.list(original.resolve("applied-end"))) {
                for(var file:files.filter(v->v.getFileName().toString().endsWith("-ack.gsr") || v.getFileName().toString().equals("ack.gsr")).toList())
                    actualRecords.add(hash(Files.readAllBytes(file)));
            }
        }
        var actual=f.f.observations.stream().filter(v->actualRecords.contains(v.record())).collect(java.util.stream.Collectors.toSet());
        assertEquals(36,actual.size(),"only actual local phased/end observations enter the child");
        Files.write(seed.resolve("observations.json"),canonical(Map.of("all",V53JournalApplicationTest.observations(actual),
                "accepts",V53JournalApplicationTest.observations(accepts),"proofs",V53JournalApplicationTest.observations(proofs)),65536));
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(var pair:CUTS) {
                String cut=pair.getFirst(),again=pair.getLast();Path work=root.resolve(mode+"-"+cut);Files.createDirectory(work);
                V53JournalApplicationTest.copy(seed.resolve("snapshots/slot-2/node-1"),work.resolve("node-1"));
                Path node=work.resolve("node-1");V53JournalApplicationTest.copy(node,work.resolve("original"));
                V53JournalPublicationTest.child(work,"fault",cut,mode,V53RoundProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("crash"));
                V53JournalPublicationTest.child(work,"recovery-fault",again,"halt",V53RoundProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("recovery-crash"));
                V53JournalPublicationTest.child(work,"resume","none","none",V53RoundProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("final"));
                var finished=V53ReplayFilesTest.files(node);V53JournalPublicationTest.child(work,"duplicate","none","none",V53RoundProcessWorker.class);
                assertEquals(finished,V53ReplayFilesTest.files(node));
                for(var original:V53ReplayFilesTest.files(work.resolve("original")).entrySet())if(!Set.of("selector.gsr","pending.accept").contains(original.getKey()))
                    assertEquals(original.getValue(),hash(Files.readAllBytes(node.resolve(original.getKey()))),original.getKey());
                assertFalse(Files.exists(node.resolve("applied-end")));assertArrayEquals(MembershipPendingAccept.empty(),Files.readAllBytes(node.resolve("pending.accept")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                rows.add(Map.of("mode",mode,"cut",cut,"recoveryCut",again,"status","PASS","manifest",selector.value().get("digest")));
                System.out.println("v53RoundProcessCase="+mode+"-"+cut+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",22L,"freshJvms",(long)rows.size()*4,
                    "execution","private-same-round-process","historicalBootstrap","conditional-fixture","runtimeEnabled",false,"powerLoss",false),65536));
            System.out.println("v53RoundProcessEvidence="+root.toAbsolutePath());
        }
        assertEquals(22,rows.size());
    }
}
