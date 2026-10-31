package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Objects;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Serial scheduling only. The caller supplies the original lifetime and full
 * installed-authority guard; a due tick cannot create READY or renew that lifetime.
 * One instance lives within the native round's existing metadata reservation. */
final class MembershipWorkPulse {
    private final LongSupplier clock;
    private final long interval;
    private long completed;
    private boolean armed,sampling;
    MembershipWorkPulse(LongSupplier clock,long interval) {
        require(interval>0 && interval<Long.MAX_VALUE/2,"work pulse interval");
        this.clock=Objects.requireNonNull(clock);this.interval=interval;
    }
    void completed(){completed=clock.getAsLong();armed=true;}
    void due(MembershipSourcePull.Guard sample)throws IOException {
        if(!armed || sampling)return;
        long elapsed=clock.getAsLong()-completed;require(elapsed>=0,"work pulse clock moved backwards");
        if(elapsed<interval)return;
        sampling=true;
        try{sample.check();completed();}finally{sampling=false;}
    }
}
