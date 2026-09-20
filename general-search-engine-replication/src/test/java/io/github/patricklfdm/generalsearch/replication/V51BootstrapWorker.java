package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.admission.AutomaticOfflineConsumer;
import java.nio.file.*;
import java.util.*;

/** Fault seam only: all authority comes from the separately compiled public consumer. */
public final class V51BootstrapWorker {
    public static void main(String[] args) throws Exception {
        String cut=args[3],mode=args[4]; Path events=Path.of(args[0]).resolve("events.txt");
        AdmissionIo.FAULTS.set(point -> {
            Files.writeString(events,ProcessHandle.current().pid()+" "+point+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
            if(point.equals(cut)) {
                System.out.println("BARRIER "+ProcessHandle.current().pid()+" "+point); System.out.flush();
                if(mode.equals("halt")) Runtime.getRuntime().halt(71);
                while(true) try { Thread.sleep(1000); } catch(InterruptedException e) { throw new java.io.IOException(e); }
            }
        });
        AutomaticOfflineConsumer.main(Arrays.copyOf(args,3));
    }
}
