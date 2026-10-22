package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Supplemental parent ACKs come from actual journal-owned ends; historical bootstrap remains conditional. */
class V53ParentCheckpointTest {
    @TempDir Path temp;
    static List<String> cuts() {
        var result=new ArrayList<String>();
        for(String p:List.of("APPLY_PARENT_STATEMENT","APPLY_PARENT_ACK"))for(String s:List.of("CREATED","PREFIX_WRITTEN","WRITTEN","FORCED"))result.add(p+"_"+s);
        result.addAll(List.of("APPLY_END_FORCED","APPLY_BEFORE_RETURN"));return result;
    }
    static final List<String> PROCESS_CUTS=List.of("APPLY_PARENT_STATEMENT_PREFIX_WRITTEN","APPLY_PARENT_ACK_PREFIX_WRITTEN","APPLY_PARENT_ACK_FORCED",
            "PUBLICATION_SELECTOR_FORCED","COVERED_END_FILE_DELETED","COVERED_VOTE_PREFIX_WRITTEN");
    @Test void compactedParentsPublishFromActualEndsWithoutChangingOriginalSelection()throws Exception {
        for(int at:List.of(1,2,4)) {
            var f=new V53JournalPublicationTest.Fixture(temp.resolve("at-"+at),at);assertEquals(1,f.bridges.size());var bridge=f.bridges.getFirst();
            assertEquals((long)at,object(bridge.statement.value().get("start")).get("index"));
            assertEquals((long)at+1,object(bridge.statement.value().get("end")).get("index"));
            assertEquals(0L,object(f.applied.get(1).plan().statement.value().get("start")).get("index"));
            for(int n:f.nodes()) {
                var files=V53ReplayFilesTest.files(f.node(n));byte[] original=Files.readAllBytes(f.node(n).resolve("generations/b/selected.gsr"));
                var r=f.resources();try(var store=f.open(n,r,e->{})) {
                    f.publish(store,n);var copy=store.floorCopyCurrent();copy.capsule.verifyAncestry(MembershipGenerationPlan.ancestry(f.bridges),List.of(f.applied.get(n).plan().originalParent()));
                    assertArrayEquals(original,Files.readAllBytes(f.node(n).resolve("generations/a/selected.gsr")));
                    assertTrue(store.currentCertificate().isEmpty());assertEquals(3,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                }
                assertEquals(0,r.usage().leases());V53JournalPublicationTest.preserved(f.node(n),files);assertFalse(Files.exists(f.node(n).resolve("applied-end")));
                try(var store=f.open(n,r,e->{})) {
                    assertArrayEquals(original,Files.readAllBytes(f.node(n).resolve("generations/a/selected.gsr")));
                    assertEquals((long)at+1,object(store.prepareCurrent(f.application.f.f.f.fixture.source.ballot(21)).value().get("cut")).get("index"));
                }
            }
        }
    }
    @Test void everyParentWriteAndReturnCutRecoversAgainAndFencesBeforeReturning()throws Exception {
        for(String point:cuts()) {
            var f=new V53JournalPublicationTest.Fixture(temp.resolve(point),2,false);Path node=f.node(1);var original=V53ReplayFilesTest.files(node);var r=f.resources();
            try(var store=f.open(1,r,e->{if(e.equals(point))throw new IOException(point);})){assertThrows(IOException.class,()->f.application.apply(store));}
            try(var store=f.open(1,r,e->{if(e.equals("APPLY_PARENT_ACK_PREFIX_WRITTEN"))throw new IOException("again");})){assertThrows(IOException.class,()->f.application.apply(store));}
            try(var store=f.open(1,r,e->{})) {var applied=f.application.apply(store);assertTrue(applied.endorsement().parent().isPresent());f.applied.put(1,applied);f.publish(store,1);}
            assertEquals(0,r.usage().leases());V53JournalPublicationTest.preserved(node,original);
            var fenced=new V53JournalPublicationTest.Fixture(temp.resolve("fenced-"+point),2,false);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=fenced.open(1,fenced.resources(),e->{if(e.equals(point))ref[0].observeCurrent(fenced.application.f.f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->fenced.application.apply(store));
            }
        }
    }
    @Test void parentProofCannotBeOmittedSubstitutedOrInferredFromTheMainAck()throws Exception {
        var f=new V53JournalPublicationTest.Fixture(temp,2);var end=f.applied.get(1).endorsement();var parent=end.parent().orElseThrow();
        try(var store=f.open(1,f.resources(),e->{})) {
            var original=V53ReplayFilesTest.files(f.node(1));
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements,f.checkpoints,List.of()));
            var wrong=new MembershipSelection.Bridge(parent.statement(),f.acknowledgements,f.checkpoints);
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements,f.checkpoints,List.of(wrong)));
            var substituted=new MembershipGrantJournal.Applied(f.applied.get(1).plan(),new MembershipAppliedEndFiles.Endorsement(end.acknowledgement(),end.owned(),f.applied.get(2).endorsement().parent()));
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(substituted,f.acknowledgements,f.checkpoints,f.bridges));
            var omitted=new MembershipGrantJournal.Applied(f.applied.get(1).plan(),new MembershipAppliedEndFiles.Endorsement(end.acknowledgement(),end.owned(),Optional.empty()));
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(omitted,f.acknowledgements,f.checkpoints,f.bridges));
            f.observations.removeAll(f.bridges.getFirst().owned);assertThrows(IllegalArgumentException.class,()->f.publish(store,1));
            assertEquals(original,V53ReplayFilesTest.files(f.node(1)));
        }
    }
    @Test void partialAckRequiresCompleteEndAndExactParentAndCleanupRejectsCorruptionBeforeDeletion()throws Exception {
        for(String damage:List.of("image","statement","ack","main-ack","extra","hardlink")) {
            var f=new V53JournalPublicationTest.Fixture(temp.resolve(damage),2);Path node=f.node(1),end=node.resolve("applied-end");
            assertThrows(IOException.class,()->f.finish(e->{if(e.equals("PUBLICATION_SELECTOR_FORCED"))throw new IOException("stop");}));
            switch(damage) {
                case "image" -> Files.write(end.resolve("application.image"),new byte[0]);
                case "statement" -> Files.write(end.resolve("parent-statement.gsr"),Files.readAllBytes(end.resolve("statement.gsr")));
                case "ack" -> Files.write(end.resolve("parent-ack.gsr"),Files.readAllBytes(end.resolve("ack.gsr")));
                case "main-ack" -> Files.write(end.resolve("ack.gsr"),new byte[0]);
                case "extra" -> Files.write(end.resolve("foreign"),new byte[0]);
                case "hardlink" -> Files.createLink(f.root.resolve("alias"),end.resolve("parent-ack.gsr"));
            }
            var original=V53ReplayFilesTest.files(node);var r=f.resources();assertThrows(Exception.class,()->f.open(1,r,e->{}));
            assertEquals(0,r.usage().leases());assertEquals(original,V53ReplayFilesTest.files(node));
        }
        for(String missing:List.of("application.image","parent-statement.gsr","ack.gsr")) {
            var f=new V53JournalPublicationTest.Fixture(temp.resolve("missing-"+missing),2,false);Path end=f.node(1).resolve("applied-end");
            try(var store=f.open(1,f.resources(),e->{if(e.equals("APPLY_PARENT_ACK_PREFIX_WRITTEN"))throw new IOException("stop");})) {assertThrows(IOException.class,()->f.application.apply(store));}
            Files.delete(end.resolve(missing));var original=V53ReplayFilesTest.files(f.node(1));
            try(var store=f.open(1,f.resources(),e->{})){assertThrows(IllegalArgumentException.class,()->f.application.apply(store));}
            assertEquals(original,V53ReplayFilesTest.files(f.node(1)));
        }
    }
    @Test void actualParentPublicationSurvivesProcessDeathAndRepeatedRecovery()throws Exception {
        Path retained=Path.of("target/v53-parent-checkpoint-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:PROCESS_CUTS) {
                Path root=retained.resolve(mode+"-"+point);var f=new V53JournalPublicationTest.Fixture(root,2,false);Path node=f.node(1);var bridge=f.bridges.getFirst();
                Files.write(root.resolve("base.image"),f.application.base);Files.write(root.resolve("parent-statement.gsr"),bridge.statement.bytes());
                Files.write(root.resolve("observations.json"),canonical(Map.of("accepts",V53JournalApplicationTest.observations(f.application.cohort.accepts()),
                        "proofs",V53JournalApplicationTest.observations(f.application.cohort.proofs()),"checkpoints",V53JournalApplicationTest.observations(f.checkpoints),
                        "parents",V53JournalApplicationTest.observations(bridge.owned)),16384));
                for(var ack:f.acknowledgements)Files.write(root.resolve("ack-"+ack.value().get("voter")+".gsr"),ack.bytes());
                for(var ack:bridge.acknowledgements)Files.write(root.resolve("parent-"+ack.value().get("voter")+".gsr"),ack.bytes());
                V53JournalApplicationTest.copy(node,root.resolve("original"));V53JournalPublicationTest.child(root,"fault",point,mode);V53JournalApplicationTest.copy(node,root.resolve("crash"));
                boolean covered=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR").value().get("generation").equals("a");
                String again=covered?"COVERED_VOTE_CANDIDATE_FORCED":"APPLY_PARENT_ACK_PREFIX_WRITTEN";
                V53JournalPublicationTest.child(root,"recovery-fault",again,"halt");V53JournalApplicationTest.copy(node,root.resolve("recovery-crash"));
                V53JournalPublicationTest.child(root,"resume","none","none");V53JournalApplicationTest.copy(node,root.resolve("final"));V53JournalPublicationTest.preserved(node,V53ReplayFilesTest.files(root.resolve("original")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                rows.add(Map.of("mode",mode,"cut",point,"recoveryCut",again,"status","PASS","manifest",selector.value().get("digest")));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",(long)PROCESS_CUTS.size()*2,"freshJvms",(long)rows.size()*3,
                    "execution","private-parent-checkpoint-publication","bootstrap","private-fixture","phasedObservations","actual-local-owners",
                    "checkpointObservations","actual-forced-ends","selectorPublication",true,"powerLoss",false),65536));
            System.out.println("v53ParentCheckpointEvidence="+retained.toAbsolutePath());
        }
        assertEquals(PROCESS_CUTS.size()*2,rows.size());
    }
}
