package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static org.junit.jupiter.api.Assertions.*;

/** Harness bounds/provenance only; never substitutes for the native history. */
class V53JoiningInitializationHarnessTest {
    @TempDir Path temp;
    V53JoiningInitializationProcess.Spec spec() {
        var nodes=V53DeclarationsTest.members(4);var root=V53DeclarationsTest.ROOT;
        var change=new MembershipChangeRequest(new MembershipOperationId(root,1),V53DeclarationsTest.HASH,MembershipChangeKind.ADD,nodes);
        var request=new MembershipLearnerRequest(root,nodes.getLast(),change,temp.resolve("replica original"),temp.resolve("operation"));
        return new V53JoiningInitializationProcess.Spec(new MembershipLearnerPlan("cd".repeat(32),request),temp.resolve("application"),nodes.getFirst());
    }
    @Test void portableSpecPreservesExactOriginalRequestAndPaths() {
        var original=spec();assertEquals(original,V53JoiningInitializationProcess.Spec.read(original.bytes()));
        assertArrayEquals(original.bytes(),V53JoiningInitializationProcess.Spec.read(original.bytes()).bytes());
    }
    @Test void specRefusesForeignProposerOverlapUnknownFieldsAndNoncanonicalBytes() {
        var original=spec();
        assertThrows(IllegalArgumentException.class,()->new V53JoiningInitializationProcess.Spec(original.plan(),original.plan().request().replicaDirectory(),original.proposer()));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningInitializationProcess.Spec(original.plan(),original.application(),original.plan().request().identity()));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningInitializationProcess.Spec(original.plan(),original.application(),V53DeclarationsTest.node(9)));
        var value=new TreeMap<>(object(parse(original.bytes(),16384)));value.put("extra",true);
        assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.Spec.read(canonical(value,16384)));
        byte[] padded=Arrays.copyOf(original.bytes(),original.bytes().length+1);padded[padded.length-1]=' ';
        var trailing=assertThrows(ReplicationException.class,()->V53JoiningInitializationProcess.Spec.read(padded));
        assertEquals("trailing JSON bytes",trailing.getMessage());
        value.remove("extra");value.put("number",0L);
        assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.Spec.read(canonical(value,16384)));
    }
    @Test void catalogueIncludesEveryInitialTransactionWriteAndBothProcessModes() {
        var points=V53JoiningInitializationProcess.points();assertEquals(36,points.size());assertEquals(36,new HashSet<>(points).size());
        for(String part:List.of("SEED","PEERS","FUTURE","LEARNER","DONE")) {
            assertTrue(points.contains("JOINING_RETENTION_"+part+"_PREFIX_WRITTEN"));
            assertTrue(points.contains("JOINING_RETENTION_"+part+"_FORCED"));
            assertTrue(points.contains("JOINING_RETENTION_"+part+"_RENAMED"));
            assertTrue(points.contains("JOINING_RETENTION_"+part+"_PARENT_FORCED"));
        }
        for(String point:points)for(String mode:List.of("halt","kill"))
            assertEquals(new V53JoiningInitializationProcess.Case(point,mode),V53JoiningInitializationProcess.Case.parse(point+","+mode));
        for(String bad:List.of("","none,halt","JOINING_RETENTION_DONE_RENAMED,resume","JOINING_RETENTION_DONE_RENAMED,halt,retry"))
            assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.Case.parse(bad));
    }
    @Test void controlParserRefusesPartialUnknownAndUnframedMessages() {
        var good=Map.<String,Object>of("kind","CUT","value",Map.of("point","JOINING_RETENTION_DONE_RENAMED","mode","halt","pid",10L));
        assertEquals(good,V53JoiningInitializationProcess.message(canonical(good,4096)));
        var raw=canonical(good,4096);assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.message(Arrays.copyOf(raw,raw.length-1)));
        assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.message(canonical(Map.of("kind","RETRY","value",1L),4096)));
        assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.message(canonical(Map.of("kind","CUT","value",1L,"extra",true),4096)));
    }
    @Test void terminalReaderFailureAndMissingMarkerFailPromptlyInsteadOfSpendingBudget() {
        assertTimeoutPreemptively(Duration.ofSeconds(5),()->{
            var queue=new LinkedBlockingQueue<Map<String,Object>>();
            var failed=CompletableFuture.failedFuture(new IllegalArgumentException("truncated original"));
            var error=assertThrows(ExecutionException.class,()->V53JoiningInitializationProcess.await(queue,failed,"CUT"));
            assertEquals("truncated original",error.getCause().getMessage());
            var ended=CompletableFuture.completedFuture(null);
            assertThrows(java.io.IOException.class,()->V53JoiningInitializationProcess.await(queue,ended,"READY"));
        });
    }
    @Test void receivedMarkerSurvivesReaderEofButWrongOrderNeverPasses()throws Exception {
        var queue=new LinkedBlockingQueue<Map<String,Object>>();var ended=CompletableFuture.completedFuture(null);
        queue.add(Map.of("kind","CLOSED","value",42L));assertEquals(42L,V53JoiningInitializationProcess.await(queue,ended,"CLOSED"));
        queue.add(Map.of("kind","READY","value",42L));
        assertThrows(AssertionError.class,()->V53JoiningInitializationProcess.await(queue,ended,"CUT"));
    }
    @Test void incompleteOutputIsRetainedVerbatimAndNeverGivenAnInventedNewline()throws Exception {
        var queue=new LinkedBlockingQueue<Map<String,Object>>();var output=new java.io.ByteArrayOutputStream();
        byte[] row=canonical(Map.of("kind","STARTED","value",Map.of("mode","halt","pid",1L)),4096);
        var error=assertThrows(IllegalArgumentException.class,()->V53JoiningInitializationProcess.copyMessages(
            new java.io.ByteArrayInputStream(row),output,queue));
        assertEquals("joining process incomplete original line",error.getMessage());assertArrayEquals(row,output.toByteArray());assertTrue(queue.isEmpty());
        output.reset();byte[] terminated=Arrays.copyOf(row,row.length+1);terminated[row.length]='\n';
        V53JoiningInitializationProcess.copyMessages(new java.io.ByteArrayInputStream(terminated),output,queue);
        assertArrayEquals(terminated,output.toByteArray());assertEquals("STARTED",queue.remove().get("kind"));
    }
    @Test void readerCompletionBetweenPollAndEofCheckStillDeliversItsMarker()throws Exception {
        var queue=new LinkedBlockingQueue<Map<String,Object>>() {
            @Override public Map<String,Object> poll(long timeout,TimeUnit unit) {
                add(Map.of("kind","CLOSED","value",42L));return null;
            }
        };
        assertEquals(42L,V53JoiningInitializationProcess.await(queue,CompletableFuture.completedFuture(null),"CLOSED"));
    }
}
