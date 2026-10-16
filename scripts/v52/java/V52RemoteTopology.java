package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Structural input only. A private address does not authorize starting a guest. */
public record V52RemoteTopology(String placement, UUID groupId, List<ReplicationMember> members) {
    public static final String FILE="remote-topology.json";
    public V52RemoteTopology {members=List.copyOf(members);}
    private static void need(boolean condition,String reason) {
        if(!condition)throw new IllegalArgumentException("remote topology "+reason);
    }
    private static int[] address(Object raw) {
        need(raw instanceof String,"address");String host=(String)raw;
        need(host.length()>=7&&host.length()<=15,"address");String[] parts=host.split("\\.",-1);
        need(parts.length==4,"address");int[] octets=new int[4];
        for(int i=0;i<4;i++) {
            need(parts[i].matches("0|[1-9][0-9]{0,2}"),"address");octets[i]=Integer.parseInt(parts[i]);
            need(octets[i]<=255,"address");
        }
        return octets;
    }
    public static V52RemoteTopology read(Path root) throws IOException {
        Path path=root.resolve(FILE);
        if(Files.isSymbolicLink(path)||!Files.isRegularFile(path)||Files.size(path)<=0||Files.size(path)>4096)
            throw new IOException("remote topology file bound/type");
        byte[] bytes;try(var input=Files.newInputStream(path)){bytes=input.readNBytes(4097);}
        if(bytes.length>4096)throw new IOException("remote topology byte bound");
        Object parsed=AdmissionJson.parse(new String(bytes,StandardCharsets.UTF_8));
        need(parsed instanceof Map<?,?>,"fields");var value=(Map<?,?>)parsed;
        need(value.keySet().equals(Set.of("schema","placement","groupId","members")),"fields");
        need("gse-v52-remote-topology-v1".equals(value.get("schema")),"domain");
        Object placement=value.get("placement");need("local-no-gcp".equals(placement)||"owned-private-hosts".equals(placement),"domain");
        Object group=value.get("groupId");need(group instanceof String&&((String)group).length()==36,"group");
        UUID id=UUID.fromString((String)group);need(id.toString().equals(group)&&!id.equals(new UUID(0,0)),"group");
        need(value.get("members") instanceof List<?>,"voter count");var rows=(List<?>)value.get("members");need(rows.size()==3,"voter count");
        var members=new ArrayList<ReplicationMember>();var hosts=new HashSet<String>();var endpoints=new HashSet<ReplicationEndpoint>();
        for(int i=0;i<3;i++) {
            Object entry=rows.get(i);need(entry instanceof Map<?,?>,"ordered voter");var row=(Map<?,?>)entry;
            String node="node-"+(i+1);need(row.keySet().equals(Set.of("node","host","port"))&&node.equals(row.get("node")),"ordered voter");
            int[] ip=address(row.get("host"));String host=(String)row.get("host");
            boolean privateAddress=ip[0]==10||ip[0]==172&&ip[1]>=16&&ip[1]<=31||ip[0]==192&&ip[1]==168;
            need(placement.equals("local-no-gcp")?ip[0]==127:privateAddress,"placement/address");
            Object port=row.get("port");need(port instanceof Long&&((Long)port)>=1024&&((Long)port)<=65535,"port");
            var endpoint=new ReplicationEndpoint(host,((Long)port).intValue());need(endpoints.add(endpoint),"duplicate endpoint");hosts.add(host);
            members.add(new ReplicationMember(new ReplicationNodeId(node),endpoint));
        }
        need(placement.equals("local-no-gcp")||hosts.size()==3,"requires three private hosts");
        return new V52RemoteTopology((String)placement,id,members);
    }
    public List<AutomaticReplicationGroupConfig<Integer,V52ReadQueries.Doc>> configs(Path root) throws IOException {
        var parameters=V52MeasurementConfiguration.read(root);
        var bounds=new ReplicationBounds(1<<20,100,8,parameters.pendingLimit(),2,1200,25,65536,64L<<20,64L<<20);
        return members.stream().map(m->new AutomaticReplicationGroupConfig<>(new ReplicationGroupId(groupId),"v52-measurement",
            m.nodeId(),members,root.resolve(m.nodeId().value()),V52MeasurementQueries.storage(root.resolve("app-"+m.nodeId().value())),
            bounds,new AutomaticLeadershipPolicy(1200,3600,6000,parameters.operationTimeoutMillis()))).toList();
    }
    public Map<String,Object> value() {
        return Map.of("schema","gse-v52-remote-topology-v1","placement",placement,"groupId",groupId.toString(),"members",
            members.stream().map(m->Map.of("node",m.nodeId().value(),"host",m.endpoint().host(),"port",m.endpoint().port())).toList());
    }
    public static void main(String[] args) throws Exception {
        need(args.length==1,"arguments");System.out.println(AdmissionJson.canonical(read(Path.of(args[0])).value()));
    }
}
