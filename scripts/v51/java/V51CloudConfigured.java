package io.github.patricklfdm.generalsearch.replication;
import io.github.patricklfdm.generalsearch.admission.*;
public final class V51CloudConfigured {
    public static void main(String[] args) throws Exception {
        V51Measurement.cloudMode=true;
        try {
            if(args[1].equals("setup"))V51MeasuredConfigured.main(args);
            else V51ConfiguredObserver.main(args);
        } finally {V51CloudJournal.closeAll();}
    }
}
