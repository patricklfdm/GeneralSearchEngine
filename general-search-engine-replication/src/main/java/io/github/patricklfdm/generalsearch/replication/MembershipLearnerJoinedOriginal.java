package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Complete original installed-history validation. Cold inspection takes the
 * real root lock, makes no writes and returns diagnostics only. It cannot
 * authorize predecessor deletion, open a mutable journal or issue a vote. */
final class MembershipLearnerJoinedOriginal {
    private MembershipLearnerJoinedOriginal() {}
    record Inspection(String source,long index,String receipt,String generation,int installedMembers) {}
    /** Shape/extent checks before hashing any declared installed member. This
     * is an inventory check only, never an original-history capability. */
    static void bounds(Map<String,Object> inventory) {
        require(!inventory.isEmpty() && inventory.size()<=64,"joined original native inventory capacity");
        long metadata=0,misc=0;int images=0;
        for(var row:inventory.entrySet()) {
            String name=row.getKey();var value=object(row.getValue());
            require(value.get("key") instanceof String key && !key.isBlank() && key.length()<=4096,"joined original file identity bound");
            if(Boolean.TRUE.equals(value.get("directory"))) {
                require(value.keySet().equals(Set.of("directory","key")) && Set.of(".","generations","generations/a","sources").contains(name),"joined original native directory");continue;
            }
            require(value.keySet().equals(Set.of("key","size","sha256")),"joined original native file shape");
            long size=number(value.get("size")),limit;MembershipValidation.digest((String)value.get("sha256"));
            if(name.startsWith("generations/a/")) {
                String member=name.substring("generations/a/".length());limit=MembershipGenerationFiles.limit(member);
                if(member.endsWith(".image"))require(++images<=MembershipResources.Unit.APPLICATION.count,"joined original image count");
                else {metadata=Math.addExact(metadata,size);require(metadata<=MembershipResources.Unit.GENERATION.bytes,"joined original generation metadata capacity");}
            }else {
                limit=switch(name){case "replica.lock"->0;case "root.gsr"->16384;case "node.gsr",MembershipBallotAllocator.CURRENT,MembershipCurrentGeneration.SELECTOR->4096;
                    case "genesis.gsr"->65536;case "grants.gsr",MembershipPendingAccept.FILE->8192;default->throw new IllegalArgumentException("joined original native member path");};
                misc=Math.addExact(misc,size);require(misc<=MembershipResources.Unit.MISC.bytes,"joined original native metadata capacity");
            }
            require((name.equals("replica.lock")?size==0:size>0) && size<=limit,"joined original native member capacity");
        }
    }

    static <K,T> Inspection verify(MembershipLearnerJoinedAdmission admission,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config)throws IOException {
        admission.check();var scope=new Scope(admission.placement().custody().summary(),admission,null,null,captured,config);
        try{return scope.read(e->{});}finally{scope.closed=true;}
    }
    /** No new files, force, repair, remote source, caller observations or
     * escaped history capability. Incomplete originals remain incomplete. */
    static <K,T> Inspection inspect(MembershipLearnerPlan summary,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);
        try(var owner=MembershipOwnership.own(summary.request().replicaDirectory().resolve("replica.lock"),false)) {
            var scope=new Scope(summary,null,owner,null,captured,config);
            try{return scope.read(cut);}finally{scope.closed=true;}
        }
    }

    static <K,T> Inspection verifyRetirement(MembershipLearnerJoinedRetirement retirement,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config)throws IOException {
        retirement.checkOwner();var scope=new Scope(retirement.summary(),null,null,retirement,captured,config);
        try{return scope.read(e->{});}finally{scope.closed=true;}
    }
    private static final class Scope {
        private final MembershipLearnerPlan summary;
        private final MembershipLearnerJoinedAdmission admission;
        private final MembershipOwnership owner;
        private final MembershipLearnerJoinedRetirement retirement;
        private final Map<String,Object> originals,installed,value;
        private final Set<String> predecessors;
        private final Map<Path,FileIdentity> proofs=new LinkedHashMap<>();
        private final Map<Path,Object> directories=new LinkedHashMap<>();
        private final MembershipGenerationFiles.Guard configuration;
        private final Path replica,generation;
        private final byte[] joined;
        private boolean closed;
        private <K,T> Scope(MembershipLearnerPlan summary,MembershipLearnerJoinedAdmission admission,MembershipOwnership owner,MembershipLearnerJoinedRetirement retirement,
                SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config)throws IOException {
            this.summary=summary;this.admission=admission;this.owner=owner;this.retirement=retirement;replica=summary.request().replicaDirectory();generation=replica.resolve("generations/a");
            originals=MembershipLearnerPlacement.installedOriginal(summary);var nativeFiles=new TreeMap<String,Object>();var oldNames=new HashSet<String>();
            for(var row:originals.entrySet()) {
                String name=row.getKey(),first=name.split("/",2)[0];
                if(Set.of("learner",MembershipLearnerStore.ADMISSION).contains(first))oldNames.add(first);else nativeFiles.put(name,row.getValue());
            }
            installed=Collections.unmodifiableMap(nativeFiles);predecessors=Set.copyOf(oldNames);
            bounds(installed);
            Path placement=MembershipLearnerPlacement.directory(summary),custody=MembershipLearnerCustody.directory(summary);
            for(Path dir:List.of(placement,custody))directories.put(dir,key(dir));
            for(Path path:List.of(custody.resolve(MembershipLearnerCustody.FILE),placement.resolve(MembershipLearnerPlacement.PLAN),
                    placement.resolve(MembershipLearnerPlacement.READY),placement.resolve(MembershipLearnerJoinedAdmission.FILE))) {
                int bound=path.getFileName().toString().equals(MembershipLearnerCustody.FILE)?MembershipLearnerCustody.MAXIMUM:MembershipLearnerPlacement.MAXIMUM;
                byte[] bytes=AdmissionPaths.read(path,bound);proofs.put(path,MembershipBasisSources.inspect(path,bytes.length,hash(bytes)));
            }
            joined=AdmissionPaths.read(placement.resolve(MembershipLearnerJoinedAdmission.FILE),MembershipLearnerJoinedAdmission.MAXIMUM);
            value=object(parse(joined,MembershipLearnerJoinedAdmission.MAXIMUM));
            require(Arrays.equals(joined,canonical(value,MembershipLearnerJoinedAdmission.MAXIMUM)) && value.keySet().equals(Set.of(
                    "schema","root","identity","plan","replica","materialization","configuration","preparationSource","receipt","sealed",
                    "intent","certificate","source","cut","generation","promise","allocator","custody","placement","recordKey"))
                    && value.get("schema").equals("gse-v53-joined-admission/1.3"),"joined original admission shape");
            require(value.get("root").equals(summary.request().root().manifestDigest()) && value.get("plan").equals(summary.planDigest())
                    && value.get("identity").equals(MembershipBootstrapSeed.identity(summary.request().identity()))
                    && value.get("replica").equals(AdmissionPaths.binding(replica))
                    && value.get("recordKey").equals(key(placement.resolve(MembershipLearnerJoinedAdmission.FILE)).toString()),"joined original admission identity");
            for(String field:List.of("configuration","preparationSource","source","generation","promise","allocator"))MembershipValidation.digest((String)value.get(field));
            require(value.get("custody").equals(fingerprint(proofs.get(custody.resolve(MembershipLearnerCustody.FILE))))
                    && value.get("placement").equals(fingerprint(proofs.get(placement.resolve(MembershipLearnerPlacement.READY)))),"joined original decision fingerprints");
            var receipt=decode(MembershipBootstrapPlanData.unbase(value.get("receipt"),16384),"records","LEARNER");
            Path typed=MembershipLearnerPlacement.typedOriginal(summary,receipt);directories.put(typed,key(typed));
            for(String name:List.of(MembershipLearnerMaterialization.PLAN,MembershipLearnerMaterialization.RECEIPT)) {
                Path file=typed.resolve(name);byte[] bytes=AdmissionPaths.read(file,MembershipLearnerMaterialization.MAXIMUM_PLAN);
                proofs.put(file,MembershipBasisSources.inspect(file,bytes.length,hash(bytes)));
            }
            var plan=object(parse(AdmissionPaths.read(typed.resolve(MembershipLearnerMaterialization.PLAN),MembershipLearnerMaterialization.MAXIMUM_PLAN),MembershipLearnerMaterialization.MAXIMUM_PLAN));
            String descriptor=plan.get("configuration") instanceof String text?text:hash(canonical(plan.get("configuration"),MembershipLearnerMaterialization.MAXIMUM_PLAN));
            require(plan.get("plan").equals(summary.planDigest()) && plan.get("materialization").equals(value.get("materialization"))
                    && plan.get("source").equals(value.get("preparationSource")) && descriptor.equals(value.get("configuration")),"joined original typed configuration binding");
            configuration=()->MembershipLearnerJoinedAdmission.configuration(summary,joined,captured,config);check();
        }
        private static Map<String,Object> fingerprint(FileIdentity file) {
            return Map.of("key",file.key().toString(),"size",file.bytes(),"sha256",file.digest());
        }
        private void check()throws IOException {
            require(!closed,"joined original read scope expired");
            if(admission!=null)admission.check();else if(retirement!=null)retirement.checkOwner();else require(owner.lock().isValid(),"joined original root owner unavailable");
            configuration.check();
            for(var directory:directories.entrySet())require(directory.getValue().equals(key(directory.getKey())),"joined original decision directory changed");
            for(var proof:proofs.entrySet()){var f=proof.getValue();require(f.equals(MembershipBasisSources.inspect(proof.getKey(),f.bytes(),f.digest())),"joined original proof changed");}
            require(originals.equals(MembershipLearnerPlacement.installedOriginal(summary)),"joined original installation decision changed");
            for(var row:installed.entrySet()) {
                String name=row.getKey();Path path=AdmissionPaths.safe(name.equals(".")?replica:replica.resolve(name));var expected=object(row.getValue());
                if(Boolean.TRUE.equals(expected.get("directory"))) {
                    require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS) && key(path).toString().equals(expected.get("key")),"joined original installed directory changed");
                    var names=new TreeSet<>(children(path,64));if(name.equals("."))names.removeAll(predecessors);
                    var wanted=new TreeSet<String>();String prefix=name.equals(".")?"":name+"/";
                    for(String member:installed.keySet())if(!member.equals(".") && member.startsWith(prefix)) {
                        String relative=member.substring(prefix.length());if(!relative.isEmpty() && !relative.contains("/"))wanted.add(relative);
                    }
                    require(names.equals(wanted),"joined original installed directory inventory changed");
                }else {
                    var actual=MembershipBasisSources.inspect(path,number(expected.get("size")),(String)expected.get("sha256"));
                    require(actual.key().toString().equals(expected.get("key")),"joined original installed file replaced");
                }
            }
        }
        private void point(MembershipBallotAllocator.Cut cut,String event)throws IOException {check();cut.at(event);check();}
        private Inspection read(MembershipBallotAllocator.Cut cut)throws IOException {
            point(cut,"JOINED_ORIGINAL_BEFORE_READ");
            var files=new TreeMap<String,byte[]>();
            for(String name:children(generation,32))files.put(name,AdmissionPaths.read(generation.resolve(name),Math.toIntExact(MembershipGenerationFiles.limit(name))));
            var packet=MembershipSourcePacket.decode(Objects.requireNonNull(files.get("source.gscp")));var images=new TreeMap<String,byte[]>();
            for(String digest:packet.images().keySet())images.put(digest,files.get(digest+".image"));
            var root=decode(AdmissionPaths.read(replica.resolve("root.gsr"),16384),"records","ROOT");
            require(root.rootDigest().equals(summary.request().root().manifestDigest())
                    && root.value().get("groupId").equals(summary.request().root().groupId().value().toString())
                    && root.value().get("historyId").equals(summary.request().root().historyId().toString()),"joined original root");
            var node=decode(AdmissionPaths.read(replica.resolve("node.gsr"),4096),"records","NODE").value();
            require(node.get("root").equals(value.get("root")) && MembershipContext.identity(object(node.get("identity"))).equals(summary.request().identity()),"joined original node identity");
            AdmissionPaths.exact(replica.resolve("genesis.gsr"),packet.objectBytes((String)root.value().get("genesis")));
            var token=new Stored(this,packet,files);MembershipCapsule source;
            try{source=MembershipCapsule.verifyStored(root,packet,images,token);}finally{token.active=false;}
            var manifest=decode(files.get("generation.gsr"),"records","GENERATION");
            MembershipFloor.Copy.validateMaterialization(manifest,source,summary.request().identity(),files);
            var selector=decode(AdmissionPaths.read(replica.resolve(MembershipCurrentGeneration.SELECTOR),4096),"records","SELECTOR");
            require(selector.value().get("root").equals(value.get("root")) && selector.value().get("node").equals(summary.request().identity().nodeId().value())
                    && selector.value().get("generation").equals("a") && manifest.value().get("generation").equals("a")
                    && selector.value().get("digest").equals(manifest.digest()) && manifest.digest().equals(value.get("generation"))
                    && manifest.value().get("basis")==null && manifest.value().get("selection")==null && manifest.value().get("ownedTail")==null,
                    "joined original selected installation");
            require(hash(packet.bytes()).equals(value.get("source")) && source.context.cut.equals(value.get("cut")),"joined original installed source");
            var receipt=decode(MembershipBootstrapPlanData.unbase(value.get("receipt"),16384),"records","LEARNER");
            var row=MembershipLearnerIntent.matchReceipt(summary.request(),receipt,source);
            var sealed=new TreeMap<String,Object>();for(String name:List.of("request","prepared","receipt"))sealed.put(name,row.get(name));
            require(sealed.equals(value.get("sealed")),"joined original sealed request");
            var intent=decode(MembershipBootstrapPlanData.unbase(value.get("intent"),16384),"records","ENTRY");
            var certificate=decode(MembershipBootstrapPlanData.unbase(value.get("certificate"),16384),"records","CERTIFICATE");
            require(intent.value().get("kind").equals("INTENT") && certificate.value().get("entry").equals(intent.digest())
                    && Arrays.equals(source.packet.objectBytes(intent.digest()),intent.bytes())
                    && Arrays.equals(source.packet.objectBytes(certificate.digest()),certificate.bytes())
                    && object(command("INTENT",source.packet.objectBytes((String)intent.value().get("payload")))).get("sealed").equals(sealed)
                    && list(source.packet.capsule().value().get("items")).stream().map(MembershipFormat::object)
                        .anyMatch(edge->Objects.equals(edge.get("descriptor"),row.get("binding")) && Objects.equals(edge.get("certificate"),certificate.digest())),
                    "joined original INTENT certificate");
            var custody=object(parse(AdmissionPaths.read(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM),MembershipLearnerCustody.MAXIMUM));
            require(custody.get("receipt").equals(receipt.digest()) && custody.get("source").equals(value.get("source")),"joined original custody source/receipt");
            var promise=decode(files.get("promise.gsr"),"records","PROMISE");AdmissionPaths.exact(replica.resolve("grants.gsr"),promise.bytes());
            var fence=source.membershipCertificateFence().orElseThrow();
            require(promise.digest().equals(value.get("promise")) && promise.value().get("basisId")==null
                    && promise.value().get("view").equals(fence.value().get("authority"))
                    && promise.value().get("ballot").equals(fence.value().get("ballot")),"joined original certificate-derived fence");
            var allocator=decode(AdmissionPaths.read(replica.resolve(MembershipBallotAllocator.CURRENT),4096),"records","ALLOCATOR");
            require(allocator.digest().equals(value.get("allocator")) && allocator.value().get("root").equals(value.get("root"))
                    && allocator.value().get("node").equals(summary.request().identity().nodeId().value())
                    && allocator.value().get("counter").equals(object(fence.value().get("ballot")).get("counter")),"joined original allocator floor");
            AdmissionPaths.exact(replica.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());
            point(cut,"JOINED_ORIGINAL_VERIFIED");
            return new Inspection((String)value.get("source"),number(source.context.cut.get("index")),receipt.digest(),manifest.digest(),installed.size());
        }
    }
    /** Exists only within the complete original inventory read under an actual
     * root owner. No caller can mint this token or retain it after inspection. */
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final Scope scope;private final MembershipSourcePacket packet;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(Scope scope,MembershipSourcePacket packet,Map<String,byte[]> files){this.scope=scope;this.packet=packet;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            require(active,"joined original history read expired");scope.check();
            require(Arrays.equals(root.bytes(),AdmissionPaths.read(scope.replica.resolve("root.gsr"),16384))
                    && Arrays.equals(packet.bytes(),this.packet.bytes()) && hash(packet.bytes()).equals(scope.value.get("source")),"joined original history substitution");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.empty();}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
}
