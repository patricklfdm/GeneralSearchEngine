package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.*;

public final class V51MeasuredConfigured {
    public static List<ReplicationGroupConfig<Integer,AdmissionSemanticModel.Doc>> configs(Path root) throws Exception {
        var ports=Files.readAllLines(root.resolve("ports.txt"));var hosts=V51GuestEndpoints.hosts(root);var members=new ArrayList<ReplicationMember>();
        for(int i=0;i<3;i++)members.add(new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),new ReplicationEndpoint(hosts.get(i),Integer.parseInt(ports.get(i)))));
        var bounds=new ReplicationBounds(1<<20,16,4,4,2,1200,25,4096,64L<<20,64L<<20);
        return members.stream().map(m->new ReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString(Files.exists(root.resolve("group-id.txt"))?read(root.resolve("group-id.txt")):"51000000-0000-0000-0000-000000000006")),
                "phase6-local-v1",m.nodeId(),members.getFirst().nodeId(),members,root.resolve(m.nodeId().value()),
                V51RichWorkload.storage(root.resolve("app-"+m.nodeId().value())),bounds)).toList();
    }
    private static String read(Path path){try{return Files.readString(path).trim();}catch(Exception e){throw new IllegalStateException(e);}}
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);var plan=V51RichWorkload.plan(Path.of(args[2]));var configs=configs(root);
        if(args[1].equals("setup")) {
            var request=new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,Path.of(args[3]),configs,root.resolve("operation"),64L<<20,256L<<20);
            ReplicationStorageOperations.applyBootstrap(V51RichWorkload.builder(),request,ReplicationStorageOperations.planBootstrap(V51RichWorkload.builder(),request));return;
        }
        int ordinal=Integer.parseInt(args[1]);String node="node-"+ordinal;
        try(var engine=ReplicatedSearchEngines.builder(V51RichWorkload.builder(),configs.get(ordinal-1)).build()) {
            engine.start().join();
            var adapter=new V51Measurement.Adapter() {
                public Map<String,Object> status(){var s=engine.replicationStatus();return Map.of("state",s.state().name(),"sequence",s.applicationSequence(),"provenIndex",s.commitIndex(),"appliedIndex",s.appliedIndex(),"pending",s.pendingClientOperations());}
                public void command(String command,Map<String,Object> request) {
                    if(command.equals("activate"))engine.activateConfiguredLeader().join();
                    else if(command.equals("catchup"))engine.catchUp(new ReplicationNodeId((String)request.get("peer"))).join();
                    else throw new IllegalArgumentException(command);
                }
            };
            try(var measurement=new V51Measurement(root,node,"published-v5.0-configured",engine,plan,adapter)) {
                V51Measurement.print(Map.of("status","STARTED","identity",V51Measurement.identity("published-v5.0-configured",node,plan,ReplicatedSearchEngines.class)));
                measurement.loop();
            }
        }
    }
}
