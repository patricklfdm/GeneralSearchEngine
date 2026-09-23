package io.github.patricklfdm.generalsearch.replication;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.LongSupplier;
import java.util.function.Supplier;

/** Test-only maintenance wait for background durable generation retirement. */
final class V51CheckpointAwait {
    private V51CheckpointAwait() {}
    @FunctionalInterface interface Pause { void sleep(long nanos) throws InterruptedException; }

    static void await(Supplier<CompletableFuture<Void>> checkpoint) throws Exception {
        await(checkpoint,System::nanoTime,TimeUnit.NANOSECONDS::sleep,TimeUnit.SECONDS.toNanos(30));
    }

    static int await(Supplier<CompletableFuture<Void>> checkpoint,LongSupplier clock,Pause pause,
            long budgetNanos) throws InterruptedException,ExecutionException,TimeoutException {
        long started=clock.getAsLong();int attempts=0;ExecutionException lastCapacity=null;
        try {
            while(true) {
                if(Thread.currentThread().isInterrupted())throw new InterruptedException("checkpoint wait interrupted");
                if(budgetNanos-(clock.getAsLong()-started)<=0)throw expired(attempts,lastCapacity);
                attempts++;
                var response=checkpoint.get();
                long remaining=budgetNanos-(clock.getAsLong()-started);
                if(remaining<=0)throw expired(attempts,lastCapacity);
                try {
                    response.get(remaining,TimeUnit.NANOSECONDS);
                    if(budgetNanos-(clock.getAsLong()-started)<=0)throw expired(attempts,lastCapacity);
                    return attempts;
                } catch(ExecutionException error) {
                    if(!(error.getCause() instanceof AutomaticReplicationException failure)
                            ||failure.reason()!=AutomaticReplicationException.Reason.CAPACITY_EXCEEDED
                            ||failure.outcome()!=AutomaticReplicationException.Outcome.NOT_APPLICABLE)throw error;
                    lastCapacity=error;
                }
                remaining=budgetNanos-(clock.getAsLong()-started);
                if(remaining<=0)throw expired(attempts,lastCapacity);
                pause.sleep(Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(250)));
            }
        } catch(InterruptedException error) {
            Thread.currentThread().interrupt();throw error;
        }
    }

    private static TimeoutException expired(int attempts,ExecutionException lastCapacity) {
        var error=new TimeoutException("checkpoint maintenance deadline after "+attempts+" attempt(s)");
        if(lastCapacity!=null)error.initCause(lastCapacity);
        return error;
    }
}
