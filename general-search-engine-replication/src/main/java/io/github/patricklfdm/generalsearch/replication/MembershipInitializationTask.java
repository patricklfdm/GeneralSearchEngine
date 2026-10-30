package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Objects;
import java.util.concurrent.TimeUnit;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One owned task and its cancellation/drain boundary, never an initialization
 * capability. The enclosing endpoint keeps its charge until this task exits. */
final class MembershipInitializationTask implements AutoCloseable {
    // Cancellation must be idempotent and safe concurrently with run/close.
    interface Action extends AutoCloseable {void run()throws IOException;void close()throws IOException;}
    @FunctionalInterface interface Factory {Action open()throws IOException;}
    private final long drainNanos;
    private boolean used,closed,finished;
    private Thread runner;
    private Action current;
    MembershipInitializationTask(long drainMillis) {
        require(drainMillis>0 && drainMillis<=TimeUnit.NANOSECONDS.toMillis(Long.MAX_VALUE/2),"initialization drain bound");
        drainNanos=TimeUnit.MILLISECONDS.toNanos(drainMillis);
    }
    void execute(Factory factory)throws IOException {
        Objects.requireNonNull(factory);
        synchronized(this){require(!closed && !used,"initialization task single use/closed");used=true;runner=Thread.currentThread();}
        Throwable failure=null;
        try {
            var made=Objects.requireNonNull(factory.open());
            synchronized(this){current=made;require(!closed,"initialization closed during acquisition admission");}
            made.run();
        }catch(IOException|RuntimeException|Error error){failure=error;throw error;}
        finally {
            try {Action action;synchronized(this){action=current;}
                if(action!=null){action.close();synchronized(this){if(current==action)current=null;}}
            }catch(IOException|RuntimeException|Error error){if(failure!=null)failure.addSuppressed(error);else throw error;}
            finally{synchronized(this){finished=true;notifyAll();}}
        }
    }
    @Override public void close()throws IOException {
        Action action;synchronized(this){closed=true;action=current;}
        if(action!=null)action.close();
        // Cancellation revokes new acquisition uses, but never interrupts an
        // already admitted force transaction or releases its owner's lifetime.
        long started=System.nanoTime();
        try{synchronized(this){while(used && !finished){
            require(runner!=Thread.currentThread(),"initialization cannot drain itself");
            long left=drainNanos-(System.nanoTime()-started);require(left>0,"initialization close drain timeout");
            TimeUnit.NANOSECONDS.timedWait(this,left);
        }}}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("initialization drain interrupted",error);}
        synchronized(this){action=current;}
        if(action!=null){action.close();synchronized(this){if(current==action)current=null;}}
    }
}
