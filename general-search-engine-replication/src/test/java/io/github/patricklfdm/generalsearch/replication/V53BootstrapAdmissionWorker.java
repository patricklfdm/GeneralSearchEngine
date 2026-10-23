package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.Map;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh-process private transaction fixture; no public typed admission claim. */
public final class V53BootstrapAdmissionWorker {
    static void line(Map<String,Object> value){System.out.println(new String(canonical(value,65536),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        Path raw=Path.of(args[0]);String point=args[1],mode=args[2];
        var plan=MembershipBootstrapPlanData.decode(Files.readAllBytes(raw.resolve("original-plan.gsbp")),Files.readAllBytes(raw.resolve("original-application.image")));
        var result=MembershipBootstrapTransaction.applyAdmitted(plan.summary(),Boolean.parseBoolean(args[3]),p->{},p->{},event->{
            line(Map.of("event",event));if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(83);
                if(mode.equals("kill")){line(Map.of("event","AWAITING_KILL","cut",point));while(true)java.util.concurrent.locks.LockSupport.parkNanos(1_000_000L);}
                throw new java.io.IOException("unknown process cut mode");
            }
        });
        line(Map.of("status","PASS","plan",result.planDigest(),"receipt",result.receiptDigest(),"history",result.root().historyId().toString()));
    }
}
