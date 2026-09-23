package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Supplier;

/** Deterministic maintenance admission checks against the actual semantic helper. */
public final class PublicSemanticCheckpointProbe {
    private static final long SECOND=TimeUnit.SECONDS.toNanos(1);
    private static final class Trial {
        final Path output;long now;int calls;
        Trial(Path root,String name){output=root.resolve(name+".json");}
        void run(Supplier<CompletableFuture<Void>> operation,long budget) throws Exception {
            PublicSemanticConsumer.checkpointWhenAvailable(output,()->{calls++;return operation.get();},()->now,nanos->now+=nanos,budget);
        }
        void rejects(Supplier<CompletableFuture<Void>> operation,Class<? extends Exception> expected,long budget) throws Exception {
            try {run(operation,budget);throw new AssertionError("unexpected checkpoint success");}
            catch(Exception error){require(expected.isInstance(error),"wrong failure: "+error);}
            require(report().get("status").equals("FAIL"),"lost failure receipt");
        }
        @SuppressWarnings("unchecked") Map<String,Object> report() throws Exception {return (Map<String,Object>)AdmissionJson.parse(Files.readString(output));}
    }
    private static CompletableFuture<Void> rejection(Reason reason,Outcome outcome) {
        return CompletableFuture.failedFuture(new AutomaticReplicationException(reason,outcome,Optional.empty(),"probe rejection"));
    }
    private static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);int cases=0;
        var direct=new Trial(root,"direct-success");direct.run(()->CompletableFuture.completedFuture(null),SECOND);
        require(direct.calls==1&&direct.report().get("status").equals("PASS"),"direct success");cases++;
        var recovery=new Trial(root,"capacity-then-success");
        recovery.run(()->recovery.calls<3?rejection(Reason.CAPACITY_EXCEEDED,Outcome.NOT_APPLICABLE):CompletableFuture.completedFuture(null),SECOND);
        require(recovery.calls==3&&recovery.now==SECOND/2&&recovery.report().get("status").equals("PASS"),"capacity did not recover");
        require(((List<?>)recovery.report().get("attempts")).size()==3,"missing capacity attempts");cases++;
        var exhausted=new Trial(root,"permanent-capacity");
        exhausted.rejects(()->rejection(Reason.CAPACITY_EXCEEDED,Outcome.NOT_APPLICABLE),TimeoutException.class,SECOND);
        require(exhausted.calls==4&&exhausted.now==SECOND,"capacity extended total deadline");cases++;
        for(Reason reason:Reason.values())if(reason!=Reason.CAPACITY_EXCEEDED) {
            var trial=new Trial(root,"reason-"+reason);trial.rejects(()->rejection(reason,Outcome.NOT_APPLICABLE),ExecutionException.class,SECOND);
            require(trial.calls==1&&trial.now==0,"retried non-capacity failure");cases++;
        }
        for(Outcome outcome:Outcome.values())if(outcome!=Outcome.NOT_APPLICABLE) {
            var trial=new Trial(root,"outcome-"+outcome);trial.rejects(()->rejection(Reason.CAPACITY_EXCEEDED,outcome),ExecutionException.class,SECOND);
            require(trial.calls==1&&trial.now==0,"retried uncertain capacity failure");cases++;
        }
        var unclassified=new Trial(root,"unclassified");
        unclassified.rejects(()->CompletableFuture.failedFuture(new IllegalStateException("unclassified")),ExecutionException.class,SECOND);
        require(unclassified.calls==1,"retried unclassified failure");cases++;
        var synchronous=new Trial(root,"synchronous");
        synchronous.rejects(()->{throw new IllegalStateException("synchronous");},IllegalStateException.class,SECOND);
        require(synchronous.calls==1,"retried synchronous failure");cases++;
        var lost=new Trial(root,"lost-response");lost.rejects(CompletableFuture::new,TimeoutException.class,1);
        require(lost.calls==1&&Files.readString(lost.output).contains("PENDING"),"retried/lost pending response");cases++;
        var interrupt=new Trial(root,"interrupted");
        Thread.currentThread().interrupt();
        try {
            interrupt.rejects(CompletableFuture::new,InterruptedException.class,SECOND);
            require(interrupt.calls==1&&Thread.currentThread().isInterrupted(),"lost interrupt or retried");
        } finally {Thread.interrupted();}
        cases++;
        var expired=new Trial(root,"expired");expired.rejects(()->CompletableFuture.completedFuture(null),TimeoutException.class,0);
        require(expired.calls==0,"submitted after total deadline");cases++;
        System.out.println(AdmissionJson.canonical(Map.of("status","PASS","cases",cases)));
    }
}
