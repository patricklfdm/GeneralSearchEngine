package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Real sockets and V4 application, test-only sealed-directory setup. */
final class V51RuntimeFixture implements AutoCloseable {
    static final ReplicationBounds BOUNDS=ReplicaLeaderTestSupport.bounds(1200,8);
    static final AutomaticLeadershipPolicy POLICY=new AutomaticLeadershipPolicy(1200,3600,6000,9600);
    final Path root;final byte[] manifest;
    final Map<String,AutomaticRuntime<Integer,Document>> nodes=new LinkedHashMap<>();
    final List<Map<String,Object>> wire=new java.util.concurrent.CopyOnWriteArrayList<>();
    V51RuntimeFixture(Path path) throws Exception {
        this(path,true,true);
    }
    V51RuntimeFixture(Path path,boolean create,boolean start) throws Exception {
        root=path.toAbsolutePath();var captured=SearchEngine.builder(SCHEMA).indexes(INDEXES).configuration();
        if(!create) {manifest=java.nio.file.Files.readAllBytes(root.resolve("node-1/manifest.gsr"));if(start)for(int i=1;i<=3;i++)open(i);return;}
        var samples=V51StorageFixture.samples();var m=V51StorageFixture.copy(decode(unbase(samples.get("MANIFEST")),"MANIFEST").value());
        var g=V51StorageFixture.copy(decode(unbase(samples.get("GENESIS")),"GENESIS").value());
        var ports=ReplicaLeaderTestSupport.ports();var members=new ArrayList<Object>();
        for(int i=0;i<3;i++)members.add(Map.of("node","node-"+(i+1),"host","127.0.0.1","port",(long)ports.get(i)));
        m.put("members",members);m.put("codecId",new Codec().codecId());m.put("codecVersion",1L);
        try(var app=new AutomaticApplication<>(captured,materialization(1),BOUNDS)) {
            m.put("schemaDigest",AutomaticApplication.schemaDigest(captured,materialization(1)));m.put("indexesDigest",app.encoder().indexDigest());
            g.put("schemaDigest",m.get("schemaDigest"));g.put("indexesDigest",m.get("indexesDigest"));g.put("application",b64(app.encoder().snapshot()));
        }
        byte[] genesis=encode("GENESIS",g);m.put("genesisDigest",digest(genesis));manifest=encode("MANIFEST",m);
        var plan=V51StorageFixture.copy(decode(unbase(samples.get("PLAN")),"PLAN").value());
        for(Object item:list(plan.get("targets"))) {
            object(item).put("policy",Map.of("heartbeatIntervalMillis",1200L,"minElectionTimeoutMillis",3600L,"maxElectionTimeoutMillis",6000L,"operationTimeoutMillis",9600L));
            object(object(item).get("bounds")).put("requestTimeoutMillis",1200L);
        }
        V51StorageFixture.setup(root,manifest,genesis,plan);
        if(start)for(int i=1;i<=3;i++)open(i);
    }
    DurableStorageConfig<Integer,Document> materialization(int i) {
        return DurableStorageConfig.builder(root.resolve("app-"+i),new Codec()).storageIdentity("fixture-storage").schemaIdentity("fixture-schema").maxDocuments(1000).maxBulkElements(100).build();
    }
    void open(int i) {
        open(i,AutomaticStore.Faults.NONE,AutomaticRuntime.Events.NONE,(barrier,request,response)->{});
    }
    void open(int i,AutomaticStore.Faults faults,AutomaticRuntime.Events events,AutomaticTransport.Events network) {
        var m=decode(manifest,"MANIFEST");var members=list(m.value().get("members")).stream().map(AutomaticRecords::object)
                .map(v->new ReplicationMember(new ReplicationNodeId(text(v,"node")),new ReplicationEndpoint(text(v,"host"),(int)number(v,"port")))).toList();
        var config=new AutomaticReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString(text(m.value(),"groupId"))),text(m.value(),"configurationId"),new ReplicationNodeId("node-"+i),members,root.resolve("node-"+i),materialization(i),BOUNDS,POLICY);
        nodes.put("node-"+i,new AutomaticRuntime<>(config,SearchEngine.builder(SCHEMA).indexes(INDEXES).configuration(),manifest,faults,
                (barrier,request,response)->{network.at(barrier,request,response);if(barrier.equals("AFTER_RESPONSE_READ")) {wire.add(request);wire.add(response);}},events));
    }
    AutomaticRuntime<Integer,Document> leader() throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        while(System.nanoTime()<end) {
            for(var runtime:nodes.values())if(runtime.failure()!=null)throw new AssertionError("runtime failure",runtime.failure());
            for(var runtime:nodes.values())if(runtime.view().state()==AutomaticReplicationState.LEADER_READY)return runtime;
            Thread.sleep(20);
        }
        throw new AssertionError(nodes.entrySet().stream().map(e->e.getKey()+":"+e.getValue().view()+" exchange="+e.getValue().lastExchangeFailure()).toList()+" wire="+wire.stream().skip(Math.max(0,wire.size()-8)).toList());
    }
    String name(AutomaticRuntime<Integer,Document> runtime) {return nodes.entrySet().stream().filter(e->e.getValue()==runtime).findFirst().orElseThrow().getKey();}
    void stop(String node) {nodes.remove(node).close();}
    @Override public void close() {for(var node:nodes.values())node.close();nodes.clear();}
}
