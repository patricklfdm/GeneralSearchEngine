package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual previous-round votes, selected installation and maintenance in repeatedly killed JVMs. */
class V53CarriedProcessTest {
    static final List<List<String>> CUTS=List.of(
            List.of("INSTALL_MANIFEST_FORCED","INSTALL_GENERATION_FORCED"),
            List.of("INSTALL_SELECTOR_RENAMED","ACCEPT_ACTIVE_FORCED"),
            List.of("ACCEPT_PREFIX_WRITTEN","ACCEPT_CANDIDATE_FORCED"),
            List.of("ACCEPT_RENAMED","FLOOR_COPIES_FORCED"),
            List.of("FLOOR_PROPOSAL_FORCED","FLOOR_AUTHORITY_FORCED"),
            List.of("FLOOR_AUTHORITY_FORCED","RETIREMENT_AUTHORITY_FORCED"),
            List.of("RETIREMENT_FILE_DELETED","RETIREMENT_AUTHORITY_RESEALED"),
            List.of("SOURCE_RETIREMENT_FORCED","JOURNAL_ROTATION_FORCED"),
            List.of("SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_FORCED"),
            List.of("FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_AUTHORITY_FORCED"),
            List.of("FLOOR_RELEASE_AUTHORITY_CLEARED","FLOOR_RELEASE_CLEARED"));
    static void seed(Path seed)throws Exception {
        var f=new V53RoundStorageTest.Fixture(seed);byte[] payload;
        try(var encoder=f.f.initial.application.app.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(203,"carried-original"))));
        }
        var entry=f.entry("DATA",payload);Files.write(seed.resolve("entry.gsr"),entry.bytes());Files.write(seed.resolve("payload.bin"),payload);
        for(int n:V53CarriedPublicationTest.NODES)try(var store=f.f.open(n)){f.f.observations.add(store.acceptCurrent(entry,payload));}
        V53CarriedPublicationTest.snapshot(f,"old-accepted");var setup=f.f.prepare(1);V53CarriedPublicationTest.snapshot(f,"prepared");
        for(int n:V53CarriedPublicationTest.NODES)try(var store=f.f.open(n)){store.installCurrent(setup.sources(),List.of(),setup.images());}
        V53CarriedPublicationTest.snapshot(f,"installed");
        for(int n:V53CarriedPublicationTest.NODES)try(var store=f.f.open(n)){store.acceptCurrent(entry,payload);}
        V53CarriedPublicationTest.snapshot(f,"reaccepted");f.f.maintain(setup.obsolete());V53CarriedPublicationTest.snapshot(f,"reclaimed");
        V53CarriedPublicationTest.finish(f,f.apply(entry,payload));V53CarriedPublicationTest.snapshot(f,"published");
        var barrier=new TreeMap<>(f.entry("BARRIER",new byte[0]).value());barrier.put("origin",setup.ballot());
        V53CarriedPublicationTest.finish(f,f.apply(decode(encode("records","ENTRY",barrier),"records","ENTRY"),new byte[0]));V53CarriedPublicationTest.snapshot(f,"continued");
        for(int n:V53CarriedPublicationTest.NODES)try(var store=f.f.open(n)){store.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22));}
        V53CarriedPublicationTest.snapshot(f,"fresh");
        // Only actual local phases/ends participate in this gate's observation set.
        // Conditional bootstrap helpers contain unrelated historical observations.
        var actual=new HashSet<Owned>();
        for(int n:V53CarriedPublicationTest.NODES) {
            var identity=V53DeclarationsTest.node(n);
            var old=MembershipPendingAccept.decode(Files.readAllBytes(seed.resolve("carried-snapshots/old-accepted/node-"+n+"/pending.accept")));
            actual.add(new Owned(identity.nodeId().value(),identity.storageId(),old.accept().digest(),cutDigest(object(setup.sources().get(n-1).basis.value().get("cut")))));
            for(int slot:List.of(1,2,3)) {
                Path original=seed.resolve("originals/slot-"+slot+"/node-"+n);
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(original.resolve("pending.accept")));
                var selector=decode(Files.readAllBytes(original.resolve("selector.gsr")),"records","SELECTOR");
                var manifest=decode(Files.readAllBytes(original.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
                String parent=cutDigest(object(manifest.value().get("cut")));
                for(var phase:List.of(vote.accept(),vote.proof()))actual.add(new Owned(identity.nodeId().value(),identity.storageId(),phase.digest(),parent));
                try(var files=Files.list(original.resolve("applied-end"))) {
                    for(Path path:files.filter(p->p.getFileName().toString().endsWith("ack.gsr")).toList()) {
                        var ack=decode(Files.readAllBytes(path),"records","CHECKPOINT_ACK");actual.add(new Owned(identity.nodeId().value(),identity.storageId(),ack.digest(),cutDigest(object(ack.value().get("cut")))));
                    }
                }
            }
        }
        assertEquals(39,actual.size());assertTrue(f.f.observations.containsAll(actual));
        Files.write(seed.resolve("inputs.json"),canonical(Map.of("observations",V53JournalApplicationTest.observations(actual),
                "obsolete",setup.obsolete().get(1)),65536));assertEquals(0,f.f.resources.usage().leases());
    }
    @Test void carriedOriginalVoteAndBoundedMaintenanceSurviveRepeatedProcessCrashes()throws Exception {
        Path root=Path.of("target/v53-carried-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);var rows=new ArrayList<Map<String,Object>>();
        try {
            seed(root.resolve("seed"));Path initial=root.resolve("seed/carried-snapshots/prepared/node-1"),settled=root.resolve("seed/carried-snapshots/reclaimed/node-1");
            for(String mode:List.of("halt","kill"))for(var cuts:CUTS) {
                String point=cuts.getFirst(),again=cuts.getLast();Path work=root.resolve(mode+"-"+point);Files.createDirectory(work);
                Path node=work.resolve("node-1");V53JournalApplicationTest.copy(initial,node);V53JournalApplicationTest.copy(node,work.resolve("original"));
                V53JournalPublicationTest.child(work,"fault",point,mode,V53CarriedProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("crash"));
                V53JournalPublicationTest.child(work,"recovery-fault",again,"halt",V53CarriedProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("recovery-crash"));
                V53JournalPublicationTest.child(work,"resume","none","none",V53CarriedProcessWorker.class);V53JournalApplicationTest.copy(node,work.resolve("final"));
                assertEquals(V53ReplayFilesTest.files(settled),V53ReplayFilesTest.files(node));
                V53JournalPublicationTest.child(work,"duplicate","none","none",V53CarriedProcessWorker.class);assertEquals(V53ReplayFilesTest.files(settled),V53ReplayFilesTest.files(node));
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
                assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));assertEquals(21L,object(vote.accept().value().get("ballot")).get("counter"));
                rows.add(Map.of("mode",mode,"cut",point,"recoveryCut",again,"status","PASS"));System.out.println("v53CarriedProcessCase="+mode+"-"+point+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("execution","private-carried-maintenance-process","cases",rows,"expectedCases",22L,"freshJvms",(long)rows.size()*4,
                    "historicalBootstrap","conditional-fixture","runtimeEnabled",false,"powerLoss",false),65536));
            System.out.println("v53CarriedProcessEvidence="+root.toAbsolutePath());
        }
        assertEquals(22,rows.size());
    }
}
