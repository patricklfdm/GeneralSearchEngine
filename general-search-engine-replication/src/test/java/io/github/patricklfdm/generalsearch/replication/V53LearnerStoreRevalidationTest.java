package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerAdmissionFiles.*;

/** Final-source actual admission plus exact original recovery/refusal. The
 * separate process matrix retains its own earlier immutable runtime identity. */
class V53LearnerStoreRevalidationTest {
    @TempDir Path temp;
    @Test void currentNativeStoreRetainsSourceAfterDisconnectAndPreservesForeignRefusals()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-learner-store-review/run-"+UUID.randomUUID()));
        System.out.println("v53LearnerStoreReviewEvidence="+raw.toAbsolutePath());
        var helper=new V53LearnerSourceNetworkTest();helper.temp=temp;var history=new AtomicReference<Path>();
        try {
            helper.exercise((source,request,nativeRaw)->{
                history.set(nativeRaw);var events=new ArrayList<String>();var original=source.source();var originalCut=original.capsule.context.cut;
                var summary=source.plan(events::add);
                try(var store=source.admit(summary,events::add)) {
                    source.close();assertEquals(originalCut,store.capsule().context.cut);assertEquals(summary,store.summary());
                }
                var plan=MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(request.operationDirectory().resolve(FILE)));
                Files.write(raw.resolve("original.gslp"),plan.bytes());Files.write(raw.resolve("admission-events.json"),canonical(events,65536));
                V53LearnerStoreNetworkTest.snapshot(raw.resolve("admitted"),plan);
                var resources=new MembershipResources(512*MembershipResources.MIB);var resumed=new ArrayList<String>();
                try(var store=MembershipLearnerStore.resume(summary,resources,resumed::add)) {assertEquals(originalCut,store.capsule().context.cut);}
                assertEquals(0,resources.usage().leases());Files.write(raw.resolve("resume-events.json"),canonical(resumed,65536));
                V53LearnerStoreNetworkTest.snapshot(raw.resolve("resumed"),plan);
                for(String mode:List.of("source","replica")) {
                    Path operation=request.operationDirectory(),replica=request.replicaDirectory();
                    Files.copy(operation.resolve(FILE),operation.resolve(NEXT));Files.copy(operation.resolve(RETAIN),operation.resolve(RETAIN_NEXT));
                    Path foreign=replica.resolve(mode.equals("source")?"learner":"").resolve("foreign");Files.write(foreign,new byte[]{7,8,9});
                    Path refusal=Files.createDirectory(raw.resolve("refused-"+mode));
                    V53JournalApplicationTest.copy(operation,refusal.resolve("operation-before"));V53JournalApplicationTest.copy(replica,refusal.resolve("replica-before"));
                    var error=assertThrows(Exception.class,()->MembershipLearnerStore.resume(summary,resources,event->{throw new AssertionError("refusal performed a force");}));
                    assertEquals(0,resources.usage().leases());
                    V53JournalApplicationTest.copy(operation,refusal.resolve("operation-after"));V53JournalApplicationTest.copy(replica,refusal.resolve("replica-after"));
                    assertEquals(V53ReplayFilesTest.files(refusal.resolve("operation-before")),V53ReplayFilesTest.files(refusal.resolve("operation-after")));
                    assertEquals(V53ReplayFilesTest.files(refusal.resolve("replica-before")),V53ReplayFilesTest.files(refusal.resolve("replica-after")));
                    Files.write(refusal.resolve("result.json"),canonical(Map.of("status","REFUSED","type",error.getClass().getSimpleName(),"reason",error.getMessage()),4096));
                    Files.delete(foreign);Files.delete(operation.resolve(NEXT));Files.delete(operation.resolve(RETAIN_NEXT));
                }
                try(var store=MembershipLearnerStore.resume(summary,resources,event->{})){store.summary();}
                assertEquals(0,resources.usage().leases());
            });
        }finally {if(history.get()!=null)V53JournalApplicationTest.copy(history.get(),raw.resolve("source-history"));}
    }
}
