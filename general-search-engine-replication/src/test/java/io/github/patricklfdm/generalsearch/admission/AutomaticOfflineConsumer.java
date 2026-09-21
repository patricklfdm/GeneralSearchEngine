package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.*;

/** Public API only; the gate also compiles this source against the packaged JARs. */
public final class AutomaticOfflineConsumer {
    private AutomaticOfflineConsumer() { }
    public static AutomaticReplicationBootstrapRequest<Integer,Doc> request(Path root,Path source) {
        var locals=configurations(root).stream().map(c -> new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),c.members(),
                c.replicaDirectory(),c.materialization(),c.bounds(),AutomaticLeadershipPolicy.forBounds(c.bounds()))).toList();
        return new AutomaticReplicationBootstrapRequest<>(source==null?ReplicationBootstrapSource.EMPTY:ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                source,locals,root.resolve("operation"),1L<<30,1L<<30);
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath(); String action=args[1]; Path source=args.length>2 && !args[2].equals("-")?Path.of(args[2]):null;
        var request=request(root,source); Path caller=root.resolve("caller-plan.txt");
        if(action.equals("apply")) {
            var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),request);
            Files.writeString(caller,plan.planDigest());
            var result=AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,plan);
            System.out.println("sequence="+result.applicationSequence());
        } else if(action.equals("resume")) {
            var first=request.replicas().getFirst();
            var plan=new ReplicationBootstrapPlan(first.groupId(),first.configurationId(),request.source(),source,
                    request.replicas().stream().map(AutomaticReplicationGroupConfig::replicaDirectory).toList(),Files.readString(caller));
            var result=AutomaticReplicationStorageOperations.resumeBootstrap(builder(),request,plan);
            if(!result.equals(AutomaticReplicationStorageOperations.readBootstrapResult(request.operationDirectory()))) throw new AssertionError("result differs");
            System.out.println("sequence="+result.applicationSequence());
        } else if(action.equals("cleanup")) {
            AutomaticReplicationStorageOperations.applyCleanup(AutomaticReplicationStorageOperations.planCleanup(request.operationDirectory()));
        } else throw new IllegalArgumentException("action");
    }
}
