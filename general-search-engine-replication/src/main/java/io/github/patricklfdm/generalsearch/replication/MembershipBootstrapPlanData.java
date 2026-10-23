package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact offline plan container, separate from the frozen GSER/GSRP catalogs.
 * Decoding is metadata validation only; neither creation nor decoding commits replicas. */
final class MembershipBootstrapPlanData {
    static final int MAXIMUM=2*1024*1024,HEADER=48,MAGIC=0x47534250; // GSBP 1.3, kind 1 PLAN
    final MembershipBootstrapSeed seed;
    final long maximumSource,maximumOperation;
    private final byte[] bytes;
    private final MembershipBootstrapPlanMetadata metadata;
    private MembershipBootstrapPlanData(byte[] bytes,byte[] application) {
        metadata=new MembershipBootstrapPlanMetadata(bytes);maximumSource=metadata.maximumSource;maximumOperation=metadata.maximumOperation;
        require(application.length==metadata.layout.imageBytes && hash(application).equals(metadata.layout.application),"bootstrap plan image identity");
        seed=MembershipBootstrapSeed.restore(metadata.layout.root.bytes(),metadata.layout.genesis.bytes(),application,metadata.descriptor());
        this.bytes=bytes.clone();
    }
    static MembershipBootstrapPlanData create(MembershipBootstrapSeed seed,MembershipBootstrapRequest<?,?> request) {
        Objects.requireNonNull(seed);Objects.requireNonNull(request);
        require(seed.root.groupId().equals(request.groupId()) && seed.rootRecord.value().get("configurationId").equals(request.configurationId())
                && seed.genesis.value().get("source").equals(request.source().name()),"bootstrap plan request identity");
        var descriptor=seed.descriptor();var paths=list(descriptor.get("paths"));int begin=request.sourcePath().isPresent()?2:1;
        require(AdmissionConfiguration.path(paths.getFirst()).equals(request.operationDirectory()) && paths.size()==begin+2*request.targets().size(),"bootstrap plan operation/path count");
        if(begin==2)require(AdmissionConfiguration.path(paths.get(1)).equals(request.sourcePath().orElseThrow()),"bootstrap plan source path");
        for(int n=0;n<request.targets().size();n++) {
            var t=request.targets().get(n);require(AdmissionConfiguration.path(paths.get(begin+2*n)).equals(t.replicaDirectory())
                    && AdmissionConfiguration.path(paths.get(begin+2*n+1)).equals(t.materialization().directory().toAbsolutePath().normalize())
                    && list(descriptor.get("identities")).get(n).equals(MembershipBootstrapSeed.identity(t.identity()))
                    && Arrays.equals(canonical(descriptor.get("core"),65536),canonical(MembershipBootstrapSeed.core(t.materialization()),65536)),"bootstrap plan target binding");
        }
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-bootstrap-plan/1.3");value.put("root",base(seed.rootRecord.bytes()));value.put("genesis",base(seed.genesis.bytes()));
        byte[] application=seed.application();value.put("application",Map.of("bytes",(long)application.length,"sha256",hash(application)));value.put("descriptor",descriptor);
        value.put("maximumSource",request.maxSourceBytes());value.put("maximumOperation",request.maxOperationBytes());value.put("targets",targets(seed));
        return new MembershipBootstrapPlanData(encode(value),application);
    }
    static byte[] encode(Map<String,Object> value) {
        byte[] body=canonical(value,MAXIMUM-HEADER);byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putShort((short)1).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    static MembershipBootstrapPlanData decode(byte[] bytes,byte[] image){return new MembershipBootstrapPlanData(bytes,image);}
    private static List<Map<String,Object>> targets(MembershipBootstrapSeed seed) {
        var result=new ArrayList<Map<String,Object>>();for(var row:list(seed.rootRecord.value().get("initial"))) {
            var identity=MembershipContext.identity(object(row));var files=seed.payloads(identity);
            result.add(Map.of("identity",MembershipBootstrapSeed.identity(identity),"directories",MembershipBootstrapSeed.directories().stream().sorted().toList(),
                "files",files.entrySet().stream().map(f->Map.of("path",f.getKey(),"bytes",(long)f.getValue().length,"sha256",hash(f.getValue()))).toList()));
        }return result;
    }
    static String base(byte[] bytes){return Base64.getEncoder().encodeToString(bytes);}
    static byte[] unbase(Object value,int maximum){require(value instanceof String && ((String)value).length()<=4*((maximum+2)/3),"bootstrap plan encoded frame bound");
        byte[] bytes=Base64.getDecoder().decode((String)value);require(bytes.length<=maximum && base(bytes).equals(value),"bootstrap plan canonical frame encoding");return bytes;}
    byte[] bytes(){return bytes.clone();}
    String digest(){return hash(bytes);}
    Path operation(){return metadata.operation();}
    List<Map<String,Object>> bindings(){return metadata.bindings();}
    MembershipBootstrapPlan summary(){return metadata.summary();}
}
