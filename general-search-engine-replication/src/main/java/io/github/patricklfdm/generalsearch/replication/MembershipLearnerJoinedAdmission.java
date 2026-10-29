package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Forced joining admission under the actual installed learner owner. The next
 * retirement/journal handoff must consume this capability; these bytes alone do
 * not open a mutable journal, release predecessors or grant an ACK. */
final class MembershipLearnerJoinedAdmission {
    static final String FILE="joined.json";
    static final int MAXIMUM=64*1024;
    private final MembershipLearnerPlacement owner;
    private byte[] bytes;
    private final MembershipGenerationFiles.Guard configuration;
    private boolean forced;
    private MembershipLearnerJoinedAdmission(MembershipLearnerPlacement owner,byte[] bytes,MembershipGenerationFiles.Guard configuration) {
        this.owner=owner;this.bytes=bytes.clone();this.configuration=configuration;
    }
    static <K,T> MembershipLearnerJoinedAdmission install(MembershipLearnerPlacement owner,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);owner.check();var custody=owner.custody();var summary=custody.summary();
        byte[] bytes=original(summary,custody.receipt(),custody.source());
        MembershipGenerationFiles.Guard guard=()->configuration(summary,bytes,captured,config);
        guard.check();owner.check();
        var result=new MembershipLearnerJoinedAdmission(owner,bytes,guard);
        owner.forceJoined(result,event->{guard.check();cut.at(event);guard.check();});
        result.forced=true;result.check();MembershipLearnerJoinedOriginal.verify(result,captured,config);result.check();return result;
    }
    void check()throws IOException {require(forced,"learner joined admission not forced");configuration.check();owner.checkJoined(bytes);}
    void checkPlacement(MembershipLearnerPlacement expected)throws IOException {
        require(owner==expected,"learner joined admission foreign placement");configuration.check();owner.check();
    }
    byte[] forPlacement(MembershipLearnerPlacement expected)throws IOException {
        checkPlacement(expected);
        var value=new TreeMap<>(object(parse(bytes,MAXIMUM)));
        String key=key(MembershipLearnerPlacement.directory(owner.custody().summary()).resolve(FILE)).toString();
        require(key.length()<=4096,"learner joined admission file identity bound");value.put("recordKey",key);
        byte[] bound=canonical(value,MAXIMUM);require(!forced || Arrays.equals(bytes,bound),"learner joined admission original inode changed");
        bytes=bound;return bytes.clone();
    }
    byte[] originalRecord()throws IOException {check();return bytes.clone();}
    MembershipLearnerPlacement placement()throws IOException {check();return owner;}

    /** Read the exact original typed descriptor and original installation.
     * Callers must bracket this with their actual custody/read-only recovery
     * guard. This computation creates no owner or voting capability. */
    static byte[] original(MembershipLearnerPlan summary,Decoded receipt,MembershipCapsule source)throws IOException {
        var request=summary.request();var row=MembershipLearnerIntent.matchReceipt(request,receipt,source);
        Map<String,Object> typed=null;
        for(Path path:List.of(MembershipLearnerMaterialization.directory(summary),MembershipLearnerSuccessor.typedDirectory(summary),MembershipLearnerSlot.typedDirectory(summary))) {
            Path file=path.resolve(MembershipLearnerMaterialization.RECEIPT);
            if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))continue;
            if(!Arrays.equals(AdmissionPaths.read(file,16384),receipt.bytes()))continue;
            require(typed==null,"learner joined admission ambiguous typed original");
            typed=object(parse(AdmissionPaths.read(path.resolve(MembershipLearnerMaterialization.PLAN),MembershipLearnerMaterialization.MAXIMUM_PLAN),MembershipLearnerMaterialization.MAXIMUM_PLAN));
            require(typed.get("plan").equals(summary.planDigest()),"learner joined admission typed plan");
        }
        require(typed!=null,"learner joined admission original typed receipt missing");
        var materialization=MembershipLearnerAdmissionPlan.binding(object(typed.get("materialization")));AdmissionPaths.recheck(materialization);
        String configuration=typed.get("configuration") instanceof String text?text:hash(canonical(typed.get("configuration"),MembershipLearnerMaterialization.MAXIMUM_PLAN));
        MembershipValidation.digest(configuration);MembershipValidation.digest((String)typed.get("source"));
        var replica=request.replicaDirectory();var selector=decode(AdmissionPaths.read(replica.resolve(MembershipCurrentGeneration.SELECTOR),4096),"records","SELECTOR");
        require(selector.value().get("generation").equals("a"),"learner joined admission original generation slot");
        Path generation=replica.resolve("generations/a");
        var manifest=decode(AdmissionPaths.read(generation.resolve(MembershipCurrentGeneration.MANIFEST),65536),"records","GENERATION");
        require(selector.value().get("digest").equals(manifest.digest()) && manifest.value().get("root").equals(request.root().manifestDigest())
                && manifest.value().get("node").equals(request.identity().nodeId().value()) && manifest.value().get("selection")==null
                && manifest.value().get("basis")==null && manifest.value().get("ownedTail")==null,"learner joined admission original generation");
        require(Arrays.equals(AdmissionPaths.read(generation.resolve("source.gscp"),MembershipSourcePacket.MAXIMUM),source.packet.bytes()),"learner joined admission source changed");
        for(String name:List.of("cut","application","catalog"))require(manifest.value().get(name).equals(source.packet.capsule().value().get(name)),"learner joined admission source "+name);
        var promise=decode(AdmissionPaths.read(replica.resolve("grants.gsr"),8192),"records","PROMISE");
        require(manifest.value().get("promise").equals(promise.digest()) && promise.value().get("basisId")==null,"learner joined admission fence changed");
        AdmissionPaths.exact(generation.resolve("promise.gsr"),promise.bytes());
        var fence=source.membershipCertificateFence().orElseThrow();AdmissionPaths.exact(generation.resolve(MembershipGenerationPlan.ADOPTION),fence.bytes());
        require(promise.value().get("root").equals(request.root().manifestDigest()) && promise.value().get("view").equals(fence.value().get("authority"))
                && promise.value().get("ballot").equals(fence.value().get("ballot")),"learner joined admission certificate fence");
        var allocator=decode(AdmissionPaths.read(replica.resolve(MembershipBallotAllocator.CURRENT),4096),"records","ALLOCATOR");
        require(allocator.value().get("root").equals(request.root().manifestDigest()) && allocator.value().get("node").equals(request.identity().nodeId().value())
                && allocator.value().get("counter").equals(object(fence.value().get("ballot")).get("counter")),"learner joined admission allocator");
        Decoded intent=null,certificate=null;
        for(Object raw:list(source.packet.capsule().value().get("items"))) {
            var edge=object(raw);if(!edge.get("kind").equals("MEMBERSHIP") || !Objects.equals(edge.get("descriptor"),row.get("binding")))continue;
            var proof=source.context.record((String)edge.get("certificate"),"CERTIFICATE");var entry=source.context.record((String)proof.value().get("entry"),"ENTRY");
            if(entry.value().get("kind").equals("INTENT")){require(intent==null,"learner joined admission duplicate INTENT");intent=entry;certificate=proof;}
        }
        require(intent!=null,"learner joined admission INTENT missing");
        var sealed=new TreeMap<String,Object>();for(String name:List.of("request","prepared","receipt"))sealed.put(name,row.get(name));
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-joined-admission/1.3");
        value.put("root",request.root().manifestDigest());value.put("identity",MembershipBootstrapSeed.identity(request.identity()));value.put("plan",summary.planDigest());
        value.put("replica",AdmissionPaths.binding(replica));value.put("materialization",materialization);value.put("configuration",configuration);
        value.put("preparationSource",typed.get("source"));value.put("receipt",MembershipBootstrapPlanData.base(receipt.bytes()));value.put("sealed",sealed);
        value.put("intent",MembershipBootstrapPlanData.base(intent.bytes()));value.put("certificate",MembershipBootstrapPlanData.base(certificate.bytes()));
        value.put("source",hash(source.packet.bytes()));value.put("cut",source.context.cut);value.put("generation",manifest.digest());
        value.put("promise",promise.digest());value.put("allocator",allocator.digest());
        value.put("custody",fingerprint(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM));
        value.put("placement",fingerprint(MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerPlacement.READY),MembershipLearnerPlacement.MAXIMUM));
        Path record=MembershipLearnerPlacement.directory(summary).resolve(FILE);
        value.put("recordKey",Files.exists(record,LinkOption.NOFOLLOW_LINKS)?key(record).toString():"x".repeat(4096));
        return canonical(value,MAXIMUM);
    }
    private static Map<String,Object> fingerprint(Path path,int maximum)throws IOException {
        byte[] bytes=AdmissionPaths.read(path,maximum);var file=inspect(path,bytes.length,hash(bytes));
        return Map.of("key",file.key().toString(),"size",file.bytes(),"sha256",file.digest());
    }
    static <K,T> void configuration(MembershipLearnerPlan summary,byte[] original,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config)throws IOException {
        var value=object(parse(original,MAXIMUM));var request=summary.request();
        require(config.root().equals(request.root()) && config.localIdentity().equals(request.identity())
                && config.replicaDirectory().equals(request.replicaDirectory()),"learner joined admission local configuration");
        var binding=MembershipLearnerAdmissionPlan.binding(object(value.get("materialization")));AdmissionPaths.recheck(binding);
        require(config.materialization().directory().equals(MembershipLearnerAdmissionPlan.path(binding)),"learner joined admission core path");
        var descriptor=Map.of("application",AdmissionConfiguration.application(captured),"core",MembershipBootstrapSeed.core(config.materialization()));
        require(value.get("configuration").equals(hash(canonical(descriptor,MembershipLearnerMaterialization.MAXIMUM_PLAN))),"learner joined admission typed configuration");
    }
    static void prefix(Path file,byte[] expected)throws IOException {
        byte[] actual=AdmissionPaths.read(file,MAXIMUM);
        require(actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length)),"learner joined admission differs from original prefix");
    }
}
