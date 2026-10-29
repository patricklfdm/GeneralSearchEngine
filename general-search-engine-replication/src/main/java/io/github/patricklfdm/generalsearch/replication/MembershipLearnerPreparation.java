package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact PREPARING input under the original nonvoting store owner. This is not
 * typed materialization or a forced LEARNER receipt, and conveys no voting rights.
 * A prepared image may differ from the current application after ordinary DATA. */
final class MembershipLearnerPreparation {
    private final MembershipLearnerStore owner;
    private final MembershipLearnerImageSource successor;
    private final MembershipLearnerRequest request;
    private final byte[] prepared;
    private final String packet,application;
    private final long size,revision;

    private MembershipLearnerPreparation(MembershipLearnerStore owner,MembershipLearnerImageSource successor,long revision)throws IOException {
        this.owner=Objects.requireNonNull(owner);this.successor=successor;this.revision=revision;
        request=owner.summary().request();var capsule=original();var operation=operation(capsule,request,revision);
        prepared=canonical(operation.get("prepared"),8192);application=(String)object(operation.get("prepared")).get("application");
        packet=hash(capsule.packet.bytes());Long bytes=capsule.packet.images().get(application);
        require(bytes!=null && bytes>0 && bytes<=MembershipApplicationImage.MAXIMUM,"learner prepared original image missing");size=bytes;
        check();
    }
    static MembershipLearnerPreparation from(MembershipLearnerStore owner,long revision)throws IOException {
        return new MembershipLearnerPreparation(owner,null,revision);
    }
    static MembershipLearnerPreparation from(MembershipLearnerImageSource source,long revision)throws IOException {
        return new MembershipLearnerPreparation(source.store(),source,revision);
    }
    private MembershipCapsule original()throws IOException {return successor==null?owner.capsule():successor.source();}
    private static Map<String,Object> operation(MembershipCapsule capsule,MembershipLearnerRequest request,long revision) {
        var context=capsule.context;
        require(revision>0 && revision<=64 && Objects.equals(context.catalog.get("active"),request.change().id().number())
                && context.view.get("operation")==null && context.authority().equals(request.change().expectedConfigurationDigest())
                && !context.voters().contains(request.identity().nodeId().value())
                && request.identity().equals(context.identities.get(request.identity().nodeId().value())),"learner preparation active nonvoting reservation");
        var row=list(context.catalog.get("results")).stream().map(MembershipFormat::object)
                .filter(v->object(v.get("request")).get("number").equals(context.catalog.get("active"))).findFirst().orElseThrow();
        require(row.get("phase").equals("PREPARING") && number(row.get("revision"))==revision && row.get("receipt")==null
                && row.get("request").equals(MembershipLearnerDiscovery.request(request.change())),"learner preparation exact current revision");
        var value=object(row.get("prepared"));
        require(number(value.get("revision"))==revision && number(object(value.get("cut")).get("index"))<number(context.cut.get("index")),
                "learner preparation certified successor cut");
        return row;
    }
    private MembershipCapsule check()throws IOException {
        var capsule=original();var operation=operation(capsule,request,revision);
        require(packet.equals(hash(capsule.packet.bytes())) && Arrays.equals(prepared,canonical(operation.get("prepared"),8192)),
                "learner preparation original source changed");return capsule;
    }
    Map<String,Object> prepared()throws IOException {check();return object(parse(prepared,8192));}
    byte[] image()throws IOException {
        check();byte[] bytes=successor==null?owner.originalImage(application,size):successor.originalImage(application,size);check();return bytes;
    }
    MembershipLearnerPlan summary()throws IOException {check();return owner.summary();}
    String packet()throws IOException {check();return packet;}
    void reserveTypedImage()throws IOException {check();if(successor==null)owner.reserveTypedImage(size);else successor.reserveTypedImage();}
    void attach(MembershipLearnerMaterialization<?> typed)throws IOException {check();if(successor==null)owner.attachTyped(typed);else successor.attachTyped(typed);}
    boolean successor(){return successor!=null;}
    java.nio.file.Path directory()throws IOException {
        check();return successor==null?MembershipLearnerMaterialization.directory(owner.summary()):successor.typedDirectory();
    }
    void requireInitialGeneration()throws IOException {check();require(successor==null,"learner successor generation already installed; retirement required");}
    MembershipLearnerSuccessor.View promote(MembershipLearnerMaterialization<?> typed)throws IOException {
        check();require(successor instanceof MembershipLearnerSuccessor.View,"learner initial handoff requires original successor");return ((MembershipLearnerSuccessor.View)successor).promote(typed);
    }
    void requireCurrentTyped(MembershipLearnerMaterialization<?> typed)throws IOException {
        check();require(successor!=null,"learner refresh requires promoted typed source");successor.requireCurrentTyped(typed);
    }
    void requireRefreshPaths(java.nio.file.Path... paths)throws IOException {
        check();require(successor!=null,"learner refresh requires promoted typed source");successor.requireRefreshPaths(paths);
    }
    MembershipResources.GenerationClaim prepareGeneration()throws IOException {check();return owner.prepareGeneration();}
    void selectedGeneration(MembershipLearnerMaterialization<?> selected,MembershipResources.GenerationClaim claim)throws IOException {
        check();owner.selectedGeneration(selected,claim);
    }
    boolean preparedGeneration()throws IOException {check();return owner.preparedGeneration();}
    MembershipCapsule source()throws IOException{return check();}
    MembershipResources resources()throws IOException{check();return owner.resources();}
    MembershipLearnerStore store()throws IOException{check();return owner;}
    Decoded receiptBytes()throws IOException {
        var capsule=check();var receipt=receiptBytes(capsule,request,revision);check();return receipt;
    }
    static Decoded receiptBytes(MembershipCapsule capsule,MembershipLearnerRequest request,long revision) {
        var prepared=object(operation(capsule,request,revision).get("prepared"));String application=(String)prepared.get("application");
        require(capsule.packet.images().containsKey(application),"learner prepared original image missing");
        var value=Map.<String,Object>of("root",request.root().manifestDigest(),"number",request.change().id().number(),
                "request",hash(canonical(MembershipLearnerDiscovery.request(request.change()),8192)),"identity",MembershipBootstrapSeed.identity(request.identity()),
                "image",application,"prepared",prepared);
        // Internal bytes only. Only a typed, forced owner may expose the record.
        return decode(encode("records","LEARNER",Map.of("root",request.root().manifestDigest(),"receipt",value)),"records","LEARNER");
    }
    /** Check the captured builder/root identity before any typed scratch writes.
     * The core semantic reader must additionally validate the original image,
     * storage descriptor and codec before a later owner can force readiness. */
    <K,T> void configuration(SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config)throws IOException {
        var capsule=check();
        require(config.root().equals(request.root()) && config.localIdentity().equals(request.identity())
                && config.replicaDirectory().equals(request.replicaDirectory()),"learner preparation local configuration binding");
        AdmissionPaths.disjoint(List.of(config.materialization().directory(),request.replicaDirectory(),request.operationDirectory()));
        if(successor!=null)successor.requireTypedPaths(config.materialization().directory(),directory());
        var root=decode(capsule.packet.objectBytes(capsule.context.recordRootDigest()),"records","ROOT");
        configuration(root,captured,config.materialization());check();
    }
    static <K,T> void configuration(Decoded root,SearchEngineConfiguration<K,T> captured,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage) {
        var descriptor=AdmissionConfiguration.application(captured);
        require(root.kind().equals("ROOT") && root.value().get("codecId").equals(storage.codec().codecId())
                && number(root.value().get("codecVersion"))==storage.codec().codecVersion()
                && root.value().get("schema").equals(hash(canonical(Map.of("schemaIdentity",storage.schemaIdentity(),"application",descriptor),1024*1024)))
                && root.value().get("indexes").equals(hash(canonical(descriptor.get("indexes"),262144))),"learner preparation root application descriptor");
    }
}
