package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

public final class V51MeasuredAutomatic {
    public static List<AutomaticReplicationGroupConfig<Integer,AdmissionSemanticModel.Doc>> configs(Path root) throws Exception {
        var ports=Files.readAllLines(root.resolve("ports.txt"));var hosts=V51GuestEndpoints.hosts(root);var members=new ArrayList<ReplicationMember>();
        for(int i=0;i<3;i++)members.add(new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),new ReplicationEndpoint(hosts.get(i),Integer.parseInt(ports.get(i)))));
        var bounds=new ReplicationBounds(1<<20,16,4,4,2,1200,25,4096,64L<<20,64L<<20);
        var policy=new AutomaticLeadershipPolicy(1200,3600,6000,9600);
        var group=new ReplicationGroupId(UUID.fromString(Files.readString(root.resolve("group-id.txt")).trim()));
        return members.stream().map(m->new AutomaticReplicationGroupConfig<>(group,"phase6-local-v1",m.nodeId(),members,
                root.resolve(m.nodeId().value()),V51RichWorkload.storage(root.resolve("app-"+m.nodeId().value())),bounds,policy)).toList();
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);var plan=V51RichWorkload.plan(Path.of(args[2]));var configs=configs(root);
        if(args[1].equals("setup")) {
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,Path.of(args[3]),configs,root.resolve("operation"),64L<<20,256L<<20);
            AutomaticReplicationStorageOperations.applyBootstrap(V51RichWorkload.builder(),request,AutomaticReplicationStorageOperations.planBootstrap(V51RichWorkload.builder(),request));return;
        }
        int ordinal=Integer.parseInt(args[1]);String node="node-"+ordinal;
        try(var engine=AutomaticReplicatedSearchEngines.builder(V51RichWorkload.builder(),configs.get(ordinal-1)).build()) {
            if(engine.start().get(15,TimeUnit.SECONDS).state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("automatic local follower startup");
            V51Measurement.Adapter adapter=()->{var s=engine.leadershipStatus();return Map.of("state",s.state().name(),"epoch",s.promisedEpoch(),
                    "activeEpoch",s.activeEpoch(),"incarnation",s.promisedIncarnation().toString(),"sequence",s.applicationSequence(),
                    "provenIndex",s.provenIndex(),"appliedIndex",s.appliedIndex(),"pending",s.pendingOperations());};
            try(var measurement=new V51Measurement(root,node,"candidate-v5.1-automatic",engine,plan,adapter)) {
                V51Measurement.print(Map.of("status","STARTED","identity",V51Measurement.identity("candidate-v5.1-automatic",node,plan,AutomaticReplicatedSearchEngines.class)));
                measurement.loop();
            }
        }
    }
}
