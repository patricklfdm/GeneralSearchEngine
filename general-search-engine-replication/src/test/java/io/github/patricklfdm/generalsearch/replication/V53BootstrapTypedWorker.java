package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh typed-coordinator process using the exact retained test request. */
public final class V53BootstrapTypedWorker {
    static MembershipBootstrapRequest<Integer,Doc> request(MembershipBootstrapPlanData plan) {
        var source=MembershipBootstrapSource.valueOf((String)plan.seed.genesis.value().get("source"));
        var paths=list(plan.seed.descriptor().get("paths"));var identities=list(plan.seed.rootRecord.value().get("initial"));
        var targets=new ArrayList<MembershipBootstrapTarget<Integer,Doc>>();
        for(int i=0;i<identities.size();i++)targets.add(new MembershipBootstrapTarget<>(MembershipContext.identity(object(identities.get(i))),
                plan.summary().absentTargets().get(2*i),storage(plan.summary().absentTargets().get(2*i+1),2)));
        return new MembershipBootstrapRequest<>(plan.seed.root.groupId(),(String)plan.seed.rootRecord.value().get("configurationId"),source,
                source==MembershipBootstrapSource.EMPTY?Optional.empty():Optional.of(AdmissionConfiguration.path(paths.get(1))),targets,
                plan.operation(),plan.maximumSource,plan.maximumOperation);
    }
    static void line(Map<String,Object> value){System.out.println(new String(canonical(value,65536),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        Path raw=Path.of(args[0]);String point=args[1],mode=args[2];
        var plan=MembershipBootstrapPlanData.decode(Files.readAllBytes(raw.resolve("original-plan.gsbp")),Files.readAllBytes(raw.resolve("original-application.image")));
        var result=MembershipBootstrapCoordinator.apply(builder().configuration(),request(plan),plan.summary(),Boolean.parseBoolean(args[3]),event->{
            line(Map.of("event",event));if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(83);
                if(mode.equals("kill")){line(Map.of("event","AWAITING_KILL","cut",point));while(true)java.util.concurrent.locks.LockSupport.parkNanos(1_000_000L);}
                throw new java.io.IOException("unknown process cut mode");
            }
        });
        line(Map.of("status","PASS","plan",result.planDigest(),"receipt",result.receiptDigest(),"history",result.root().historyId().toString()));
    }
}
