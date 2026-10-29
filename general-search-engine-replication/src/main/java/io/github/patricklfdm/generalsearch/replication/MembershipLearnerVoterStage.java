package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Dormant, original INTENT-bound voter installation bytes. No voter owner,
 * allocation, grant, ACK, selector in the live replica or deletion permission.
 * The subsequent ownership handoff must consume the live Ready capability. */
final class MembershipLearnerVoterStage implements AutoCloseable {
    static final String PLAN="voter-plan.json",READY="voter-ready.json";
    static final int MAXIMUM=64*1024;
    private static final Set<String> DIRECTORIES=Set.of("generations","generations/a","sources");
    private final MembershipLearnerIntent.Forced intent;
    private final MembershipBallotAllocator.Cut cut;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Map<String,byte[]> files=new TreeMap<>();
    private final Map<String,FileIdentity> originals=new TreeMap<>();
    private final Map<String,Object> directories=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final MembershipGenerationPlan generation;
    private final Decoded promise,allocator;
    private byte[] plan,ready;
    private Object directoryKey;
    private volatile boolean closed;
    private boolean failed,complete;

    static Path directory(MembershipLearnerPlan plan) {
        return plan.request().operationDirectory().resolveSibling(".gse-v53-learner-voter-"+plan.planDigest());
    }
    private MembershipLearnerVoterStage(MembershipLearnerIntent.Forced intent,MembershipBallotAllocator.Cut cut)throws IOException {
        this.intent=Objects.requireNonNull(intent);this.cut=Objects.requireNonNull(cut);
        var source=intent.source();var head=intent.head();var request=head.request();
        directory=directory(intent.plan());head.requireDisjoint(directory);binding=AdmissionPaths.binding(directory);
        var certificate=source.membershipCertificateFence().orElseThrow();
        // This is a certificate-derived fence, not a new campaign. Preserve its
        // ballot, and let the eventual local allocator reserve strictly above it.
        var values=new TreeMap<String,Object>();values.put("root",request.root().manifestDigest());
        values.put("view",certificate.value().get("authority"));values.put("ballot",certificate.value().get("ballot"));values.put("basisId",null);
        promise=decode(encode("records","PROMISE",values),"records","PROMISE");
        allocator=decode(encode("records","ALLOCATOR",Map.of("root",request.root().manifestDigest(),
                "node",request.identity().nodeId().value(),"counter",object(certificate.value().get("ballot")).get("counter"))),"records","ALLOCATOR");
        var images=new TreeMap<String,byte[]>();for(String hash:source.packet.images().keySet())images.put(hash,intent.member(hash+".image"));
        generation=MembershipGenerationPlan.adopted(request.root(),request.identity(),"a",promise,source,
                source.verifiedAncestry(intent.ancestry()),images);
        generation.files.forEach((name,bytes)->files.put("generations/a/"+name,bytes.clone()));
        files.put("replica.lock",new byte[0]);files.put("root.gsr",source.packet.objectBytes(source.context.recordRootDigest()));
        files.put("genesis.gsr",source.packet.objectBytes((String)source.packet.capsule().value().get("initial")));
        files.put("node.gsr",encode("records","NODE",Map.of("root",request.root().manifestDigest(),"identity",MembershipBootstrapSeed.identity(request.identity()))));
        files.put(MembershipBallotAllocator.CURRENT,allocator.bytes());files.put("grants.gsr",promise.bytes());
        files.put(MembershipPendingAccept.FILE,MembershipPendingAccept.empty());files.put(MembershipCurrentGeneration.SELECTOR,generation.selector.bytes());
        intent.guard();
    }
    private byte[] plan()throws IOException {
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-learner-voter-stage/1.3");
        value.put("plan",intent.plan().planDigest());value.put("path",binding);value.put("directoryKey",directoryKey.toString());
        value.put("replica",AdmissionPaths.binding(intent.head().request().replicaDirectory()));
        value.put("receipt",intent.head().receipt().digest());value.put("source",hash(generation.files.get("source.gscp")));
        value.put("generation",generation.manifest.digest());value.put("promise",promise.digest());value.put("allocator",allocator.digest());
        value.put("files",files.entrySet().stream().map(e->Map.of("path",e.getKey(),"size",(long)e.getValue().length,"sha256",hash(e.getValue()))).toList());
        return canonical(value,MAXIMUM);
    }
    static MembershipLearnerVoterStage install(MembershipLearnerIntent.Forced intent,MembershipBallotAllocator.Cut cut)throws IOException {
        return open(intent,cut,false);
    }
    static MembershipLearnerVoterStage resume(MembershipLearnerIntent.Forced intent,MembershipBallotAllocator.Cut cut)throws IOException {
        return open(intent,cut,true);
    }
    private static MembershipLearnerVoterStage open(MembershipLearnerIntent.Forced intent,MembershipBallotAllocator.Cut cut,boolean resume)throws IOException {
        var result=new MembershipLearnerVoterStage(intent,cut);
        try {
            intent.attach(result);
            if(resume) {
                result.directoryKey=key(result.directory);result.plan=result.plan();
                // Missing/torn decision cannot turn a directory into a new plan.
                AdmissionPaths.exact(result.directory.resolve(PLAN),result.plan);
                result.capture();result.validatePrefixes();
            }else AdmissionPaths.absent(result.directory);
            result.reserve();intent.guard();
            if(!resume) {
                Files.createDirectory(result.directory);result.directoryKey=key(result.directory);result.plan=result.plan();
                AdmissionPaths.forceDirectory(result.directory.getParent());result.point("VOTER_STAGE_DIRECTORY_FORCED");
                result.write(PLAN,result.plan,"VOTER_STAGE_PLAN");
            }
            result.finish();return result;
        }catch(IOException|RuntimeException|Error error){result.failed=true;try{result.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void reserve()throws IOException {
        long metadata=files.entrySet().stream().filter(e->!e.getKey().endsWith(".image")).mapToLong(e->e.getValue().length).sum();
        // Charge the entire dormant metadata copy plus both bounded companions.
        // The learner's already reserved MISC area is not borrowed implicitly.
        metadata=Math.addExact(metadata,2L*MAXIMUM);var resources=intent.head().resources();
        leases.add(resources.reserve(MembershipResources.Unit.GENERATION,"learner-voter-stage",metadata));
        for(var file:files.entrySet())if(file.getKey().endsWith(".image"))
            leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"voter:"+file.getKey(),file.getValue().length));
    }
    private Set<String> expectedNames() {
        var names=new HashSet<>(files.keySet());names.addAll(DIRECTORIES);names.add(PLAN);names.add(READY);return names;
    }
    private void capture()throws IOException {
        AdmissionPaths.recheck(binding);require(key(directory).equals(directoryKey),"learner voter stage directory replaced");
        var foundFiles=new TreeMap<String,FileIdentity>();var foundDirectories=new TreeMap<String,Object>();
        try(var walk=Files.walk(directory,3)) {
            var iterator=walk.iterator();int count=0;
            while(iterator.hasNext()) {
                Path path=iterator.next();if(path.equals(directory))continue;
                require(++count<=64,"learner voter stage inventory capacity");String name=directory.relativize(path).toString();
                require(expectedNames().contains(name),"learner voter stage unexpected member");AdmissionPaths.safe(path);
                if(DIRECTORIES.contains(name)){require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"learner voter stage directory type");foundDirectories.put(name,key(path));}
                else {
                    AdmissionPaths.regular(path);long size=Files.size(path);byte[] wanted=files.get(name);
                    require(size<=(wanted==null?MAXIMUM:wanted.length),"learner voter stage member capacity");
                    byte[] bytes=AdmissionPaths.read(path,Math.toIntExact(size));foundFiles.put(name,inspect(path,size,hash(bytes)));
                }
            }
        }
        originals.clear();originals.putAll(foundFiles);directories.clear();directories.putAll(foundDirectories);
    }
    private void guard()throws IOException {
        require(!closed && !failed,"learner voter stage owner closed/failed");
        try {
            intent.guard();var oldFiles=new TreeMap<>(originals);var oldDirectories=new TreeMap<>(directories);capture();
            require(oldFiles.equals(originals) && oldDirectories.equals(directories),"learner voter stage original members changed");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** A legitimate write may update only its own inode's length/digest. Never
     * absorb replacement/deletion of an earlier member into the next seal. */
    private void changed(String name)throws IOException {
        var oldFiles=new TreeMap<>(originals);var oldDirectories=new TreeMap<>(directories);
        var old=oldFiles.remove(name);oldDirectories.remove(name);capture();
        var remainingFiles=new TreeMap<>(originals);var remainingDirectories=new TreeMap<>(directories);
        var next=remainingFiles.remove(name);remainingDirectories.remove(name);
        require(oldFiles.equals(remainingFiles) && oldDirectories.equals(remainingDirectories)
                && (old==null || next!=null && old.key().equals(next.key())),"learner voter stage concurrent replacement");
    }
    private void validatePrefixes()throws IOException {
        for(var file:originals.entrySet()) {
            String name=file.getKey();if(name.equals(READY))continue;
            byte[] wanted=name.equals(PLAN)?plan:files.get(name),actual=AdmissionPaths.read(directory.resolve(name),wanted.length);
            require(Arrays.equals(actual,Arrays.copyOf(wanted,actual.length)),"learner voter stage differs from original prefix");
        }
        if(originals.containsKey(READY)) {
            require(originals.keySet().containsAll(files.keySet()) && directories.keySet().equals(DIRECTORIES),"learner voter stage seal missing members");
            for(var file:files.entrySet())AdmissionPaths.exact(directory.resolve(file.getKey()),file.getValue());
            ready=ready();byte[] actual=AdmissionPaths.read(directory.resolve(READY),MAXIMUM);
            require(Arrays.equals(actual,Arrays.copyOf(ready,actual.length)),"learner voter stage original seal changed");
        }
    }
    private void point(String event)throws IOException {guard();cut.at(event);guard();}
    private void write(String name,byte[] wanted,String event)throws IOException {
        guard();Path path=directory.resolve(name);var old=originals.get(name);
        byte[] before=old==null?new byte[0]:AdmissionPaths.read(path,wanted.length);
        require(Arrays.equals(before,Arrays.copyOf(wanted,before.length)),"learner voter stage write original prefix");
        try(var channel=FileChannel.open(path,old==null?Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            if(old==null){changed(name);point(event+"_CREATED");}
            if(before.length<wanted.length) {
                channel.position(before.length);int middle=before.length+(wanted.length-before.length)/2;
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,before.length,middle));changed(name);point(event+"_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,middle,wanted.length));changed(name);point(event+"_WRITTEN");
            }
            channel.force(true);point(event+"_FORCED");
        }
        AdmissionPaths.forceDirectory(path.getParent());point(event+"_PARENT_FORCED");
    }
    private byte[] ready() {
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-learner-voter-ready/1.3");value.put("plan",hash(plan));
        value.put("directories",directories.entrySet().stream().map(e->Map.of("path",e.getKey(),"key",e.getValue().toString())).toList());
        value.put("files",originals.entrySet().stream().filter(e->!e.getKey().equals(READY)).map(e->Map.of("path",e.getKey(),
                "key",e.getValue().key().toString(),"size",e.getValue().bytes(),"sha256",e.getValue().digest())).toList());return canonical(value,MAXIMUM);
    }
    private void finish()throws IOException {
        guard();validatePrefixes();write(PLAN,plan,"VOTER_STAGE_PLAN");
        for(String name:new TreeSet<>(DIRECTORIES)) {
            guard();Path path=directory.resolve(name);if(!directories.containsKey(name)){Files.createDirectory(path);changed(name);point("VOTER_STAGE_CHILD_CREATED");}
            AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());point("VOTER_STAGE_CHILD_FORCED");
        }
        for(var file:files.entrySet())write(file.getKey(),file.getValue(),file.getKey().endsWith(".image")?"VOTER_STAGE_IMAGE":"VOTER_STAGE_MEMBER");
        for(String name:DIRECTORIES)AdmissionPaths.forceDirectory(directory.resolve(name));AdmissionPaths.forceDirectory(directory);
        point("VOTER_STAGE_PAYLOAD_FORCED");ready=ready();write(READY,ready,"VOTER_STAGE_READY");
        intent.check();point("VOTER_STAGE_BEFORE_RETURN");complete=true;
    }
    final class Ready {
        private Ready(){}
        void check()throws IOException {
            require(complete,"learner voter stage not complete");guard();validatePrefixes();AdmissionPaths.exact(directory.resolve(READY),ready);
        }
        Path directory()throws IOException {check();return directory;}
        Decoded promise()throws IOException {check();return promise;}
        Decoded allocator()throws IOException {check();return allocator;}
    }
    Ready readyCapability()throws IOException {var result=new Ready();result.check();return result;}
    boolean closed(){return closed;}
    @Override public synchronized void close(){if(closed)return;closed=true;for(var lease:leases)lease.close();leases.clear();}
}
