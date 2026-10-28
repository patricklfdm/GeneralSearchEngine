package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Immutable offline learner plan metadata. It binds a verified original source,
 * but does not itself authenticate a capsule, create a learner store or grant votes. */
final class MembershipLearnerAdmissionPlan {
    static final int MAGIC=0x47534c50,MAXIMUM=65536; // GSLP 1.3, kind 1 PLAN
    final MembershipLearnerRequest request;
    final MembershipIdentity source;
    final Decoded root,generation;
    private final byte[] bytes;
    private final List<Map<String,Object>> paths;
    private final Map<String,Object> value;
    private MembershipLearnerAdmissionPlan(byte[] supplied) {
        require(supplied.length>HEADER && supplied.length<=MAXIMUM,"learner plan capacity");bytes=supplied.clone();
        var input=ByteBuffer.wrap(bytes);
        require(input.getInt()==MAGIC && input.getShort()==1 && input.getShort()==3 && input.getShort()==1 && input.getShort()==0
                && input.getInt()==bytes.length-HEADER,"learner plan header");
        byte[] checksum=new byte[32];input.get(checksum);byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(checksum,sha(Arrays.copyOf(bytes,16),body)),"learner plan checksum");
        value=object(parse(body,MAXIMUM-HEADER));require(Arrays.equals(body,canonical(value,MAXIMUM-HEADER)),"learner plan canonical body");
        require(value.keySet().equals(Set.of("schema","root","learner","request","source","cut","generation","files","paths"))
                && value.get("schema").equals("gse-v53-learner-plan/1.3"),"learner plan fields");
        root=MembershipFormat.decode(MembershipBootstrapPlanData.unbase(value.get("root"),16384),"records","ROOT");
        require(root.value().get("limits").equals(hash(canonical(CATALOG.get("resources"),16384))),"learner plan root limits");
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),
                UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var change=object(value.get("request"));require(change.keySet().equals(Set.of("root","number","expected","kind","target"))
                && change.get("root").equals(history.manifestDigest()),"learner plan request fields/root");
        var target=list(change.get("target")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
        var command=new MembershipChangeRequest(new MembershipOperationId(history,number(change.get("number"))),
                (String)change.get("expected"),MembershipChangeKind.valueOf((String)change.get("kind")),target);
        require(change.equals(MembershipLearnerDiscovery.request(command)),"learner plan canonical request");
        var learner=MembershipContext.identity(object(value.get("learner")));source=MembershipContext.identity(object(value.get("source")));
        require(value.get("learner").equals(MembershipBootstrapSeed.identity(learner)) && value.get("source").equals(MembershipBootstrapSeed.identity(source))
                && !learner.equals(source) && target.contains(source),"learner plan identity/source");
        var bindings=list(value.get("paths"));require(bindings.size()==2,"learner plan path count");
        paths=bindings.stream().map(MembershipFormat::object).map(MembershipLearnerAdmissionPlan::binding).toList();
        request=new MembershipLearnerRequest(history,learner,command,path(paths.get(1)),path(paths.get(0)));
        generation=MembershipFormat.decode(MembershipBootstrapPlanData.unbase(value.get("generation"),65536),"records","GENERATION");
        var cut=object(value.get("cut"));MembershipContext.checkView(object(cut.get("view")));
        require(generation.value().get("root").equals(history.manifestDigest()) && generation.value().get("node").equals(source.nodeId().value())
                && generation.value().get("cut").equals(cut)
                && MembershipContext.viewDigest(history.manifestDigest(),object(cut.get("view"))).equals(command.expectedConfigurationDigest())
                && object(cut.get("view")).get("operation")==null,"learner plan source generation/cut");
        var expected=new TreeMap<String,Map<String,Object>>();
        expected.put("generation.gsr",row("generation.gsr",generation.bytes()));
        long metadata=generation.size();
        for(Object member:list(generation.value().get("files"))) {
            var file=object(member);String name=(String)file.get("path");long size=number(file.get("size"));
            require(size>0 && size<=MembershipGenerationFiles.limit(name) && expected.putIfAbsent(name,file)==null,"learner plan generation member");
            if(!name.endsWith(".image")){metadata=Math.addExact(metadata,size);require(metadata<=MembershipResources.Unit.LEARNER.bytes,"learner plan metadata bound");}
        }
        require(expected.size()<=32 && list(value.get("files")).equals(List.copyOf(expected.values())),"learner plan exact original inventory");
    }
    static MembershipLearnerAdmissionPlan create(MembershipLearnerRequest request,MembershipFloor.Copy original)throws IOException {
        original.check();MembershipLearnerPrefixExport.originalReservation(original.capsule.context,request,original.owner);
        AdmissionPaths.disjoint(List.of(request.operationDirectory(),request.replicaDirectory()));
        AdmissionPaths.absent(request.operationDirectory());AdmissionPaths.absent(request.replicaDirectory());
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-learner-plan/1.3");
        value.put("root",MembershipBootstrapPlanData.base(original.capsule.packet.objectBytes(original.capsule.context.recordRootDigest())));
        value.put("learner",MembershipBootstrapSeed.identity(request.identity()));value.put("source",MembershipBootstrapSeed.identity(original.owner));
        value.put("request",MembershipLearnerDiscovery.request(request.change()));value.put("cut",original.capsule.context.cut);
        value.put("generation",MembershipBootstrapPlanData.base(original.generation.bytes()));
        value.put("files",new TreeSet<>(original.fileNames()).stream().map(n->row(n,original.fileBytes(n))).toList());
        value.put("paths",List.of(AdmissionPaths.binding(request.operationDirectory()),AdmissionPaths.binding(request.replicaDirectory())));
        var result=decode(encode(value));result.checkOriginal(original);return result;
    }
    private static Map<String,Object> row(String name,byte[] bytes){return Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes));}
    static Map<String,Object> binding(Map<String,Object> binding) {
        require(binding.keySet().equals(Set.of("path","parentRealPath","fileStoreName","fileStoreType","parentFileKey")),"learner plan path binding fields");
        for(Object field:binding.values())require(field instanceof String && !((String)field).isBlank()
                && ((String)field).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,"learner plan path binding text");
        Path path=path(binding),parent=Path.of((String)binding.get("parentRealPath"));
        require(path.getParent()!=null && path.getParent().equals(parent),"learner plan exact parent path");return Map.copyOf(binding);
    }
    static Path path(Map<String,Object> binding) {
        String text=(String)binding.get("path");Path path=Path.of(text);
        require(path.isAbsolute() && path.normalize().equals(path) && path.toString().equals(text),"learner plan absolute normalized path");return path;
    }
    static byte[] encode(Map<String,Object> value) {
        byte[] body=canonical(value,MAXIMUM-HEADER),prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3)
                .putShort((short)1).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    static MembershipLearnerAdmissionPlan decode(byte[] bytes){return new MembershipLearnerAdmissionPlan(bytes);}
    void checkOriginal(MembershipFloor.Copy original) {
        original.check();MembershipLearnerPrefixExport.originalReservation(original.capsule.context,request,original.owner);
        require(source.equals(original.owner) && Arrays.equals(generation.bytes(),original.generation.bytes())
                && value.get("files").equals(new TreeSet<>(original.fileNames()).stream().map(n->row(n,original.fileBytes(n))).toList()),
                "learner plan source differs from original");
    }
    void recheckPaths()throws IOException {recheckPaths(true);}
    void recheckPaths(boolean absent)throws IOException {for(var bound:paths)AdmissionPaths.recheck(bound);if(absent)AdmissionPaths.absent(request.replicaDirectory());}
    List<Map<String,Object>> inventory(){return list(value.get("files")).stream().map(MembershipFormat::object).toList();}
    byte[] bytes(){return bytes.clone();}
    MembershipLearnerPlan summary(){return new MembershipLearnerPlan(hash(bytes),request);}
}
