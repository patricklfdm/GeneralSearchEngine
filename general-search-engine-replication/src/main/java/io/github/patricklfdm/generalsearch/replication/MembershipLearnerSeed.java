package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original slot A after a new head has captured its exact deletion inventory.
 * A live handoff keeps the original lock/leases; cold recovery owns them anew.
 * This object never supplies a source capsule or makes a voting receipt. */
final class MembershipLearnerSeed implements AutoCloseable {
    private final MembershipLearnerStore parent;
    private final MembershipLearnerSuccessor borrowed;
    private final Path directory,source,typed;
    private final MembershipLearnerSuccessor.SeedData original;
    private final byte[] plan,head;
    private final Map<String,Object> binding;
    private final SortedSet<String> sourceNames;
    private final Object metadataFiles;
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private MembershipOwnership lock;
    private boolean closed,retired;

    static MembershipLearnerSeed capture(MembershipLearnerStore parent)throws IOException {
        return new MembershipLearnerSeed(parent,parent.seedOwner(),null);
    }
    static MembershipLearnerSeed restore(MembershipLearnerStore parent,Object metadataFiles)throws IOException {
        return new MembershipLearnerSeed(parent,null,metadataFiles);
    }
    private MembershipLearnerSeed(MembershipLearnerStore parent,MembershipLearnerSuccessor borrowed,Object expected)throws IOException {
        this.parent=parent;this.borrowed=borrowed;var summary=parent.summary();
        directory=MembershipLearnerSuccessor.directory(summary);source=directory.resolve(MembershipLearnerSuccessor.SOURCE);
        typed=MembershipLearnerSuccessor.typedDirectory(summary);plan=AdmissionPaths.read(directory.resolve(MembershipLearnerSuccessor.PLAN),MembershipLearnerSuccessor.MAXIMUM);
        original=MembershipLearnerSuccessor.seedData(parent,plan);binding=original.path();
        AdmissionPaths.exact(directory.resolve(MembershipLearnerSuccessor.SELECTED),original.selector());
        head=AdmissionPaths.read(directory.resolve(MembershipLearnerSuccessor.HEAD),MembershipLearnerSuccessor.HEAD_MAXIMUM);
        var value=object(parse(head,MembershipLearnerSuccessor.HEAD_MAXIMUM));
        var files=list(original.value().get("files")).stream().map(MembershipFormat::object).toList();
        var packet=files.stream().filter(f->f.get("path").equals("source.gscp")).findFirst().orElseThrow();
        require(Arrays.equals(head,canonical(value,MembershipLearnerSuccessor.HEAD_MAXIMUM))
                && value.keySet().equals(Set.of("schema","plan","installed","source","generation","receipt","previousFiles","currentFiles"))
                && value.get("schema").equals("gse-v53-learner-head/1.3") && value.get("plan").equals(summary.planDigest())
                && value.get("installed").equals(hash(plan)) && value.get("source").equals(packet.get("sha256"))
                && value.get("generation").equals(original.generation().digest()),"learner slot original seed head");
        MembershipValidation.digest((String)value.get("receipt"));
        MembershipLearnerFingerprints.shape(value.get("previousFiles"),MembershipLearnerSuccessor.typedPaths(true));
        MembershipLearnerFingerprints.shape(value.get("currentFiles"),MembershipLearnerFingerprints.typed());
        sourceNames=new TreeSet<>(List.of("."));for(var file:files)sourceNames.add((String)file.get("path"));
        if(expected==null) {
            require(borrowed!=null,"learner seed capture without original owner");borrowed.seedLock();
            metadataFiles=MembershipLearnerFingerprints.capture(directory,MembershipLearnerFingerprints.seed(),Set.of(MembershipLearnerSuccessor.SOURCE),false,MembershipLearnerSuccessor.MAXIMUM);
        }else metadataFiles=expected;
        try {
            if(borrowed==null)lock=MembershipOwnership.own(directory.resolve(MembershipLearnerSuccessor.LOCK),false);
            checkMetadata();
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    Object metadata(){return metadataFiles;}
    Object sourceFiles()throws IOException {
        checkMetadata();return MembershipLearnerFingerprints.capture(source,sourceNames,Set.of(),false,MembershipApplicationImage.MAXIMUM);
    }
    Object typedFiles()throws IOException {
        checkMetadata();return MembershipLearnerFingerprints.capture(typed,MembershipLearnerFingerprints.typed(),Set.of(),false,MembershipApplicationImage.MAXIMUM);
    }
    Map<String,Object> anchor(Object core)throws IOException {
        checkMetadata();var originalCore=MembershipLearnerAdmissionPlan.binding(object(core));AdmissionPaths.recheck(originalCore);
        var value=object(parse(head,MembershipLearnerSuccessor.HEAD_MAXIMUM));var generation=original.generation().value();
        return Map.of("head",hash(head),"receipt",value.get("receipt"),"core",originalCore,
                "previous",Map.of("source",value.get("source"),"cut",generation.get("cut"),"catalog",generation.get("catalog"),"application",generation.get("application")));
    }
    void checkMetadata()throws IOException {
        require(!closed,"learner seed owner closed");parent.requireOriginalRetiredFilesAbsent();
        if(borrowed!=null)borrowed.seedLock();else require(lock!=null && lock.lock().isValid(),"learner seed lock unavailable");
        AdmissionPaths.recheck(binding);AdmissionPaths.absent(MembershipLearnerAdmissionPlan.path(original.staging()));
        MembershipLearnerFingerprints.check(directory,MembershipLearnerFingerprints.seed(),Set.of(MembershipLearnerSuccessor.SOURCE),metadataFiles,false,MembershipLearnerSuccessor.MAXIMUM);
    }
    void checkRemaining(Object sourceFiles,Object typedFiles,boolean remaining)throws IOException {
        checkMetadata();
        MembershipLearnerFingerprints.check(source,sourceNames,Set.of(),sourceFiles,remaining,MembershipApplicationImage.MAXIMUM);
        MembershipLearnerFingerprints.check(typed,MembershipLearnerFingerprints.typed(),Set.of(),typedFiles,remaining,MembershipApplicationImage.MAXIMUM);
    }
    List<Path> removalOrder() {
        var result=new ArrayList<>(MembershipLearnerFingerprints.removalOrder(source,sourceNames));
        result.addAll(MembershipLearnerFingerprints.removalOrder(typed,MembershipLearnerFingerprints.typed()));return result;
    }
    void reserve()throws IOException {
        checkMetadata();if(borrowed!=null)return;
        require(leases.isEmpty(),"learner seed already accounted");long metadata=0;
        for(Object raw:list(original.value().get("files"))){var file=object(raw);if(!((String)file.get("path")).endsWith(".image"))metadata=Math.addExact(metadata,number(file.get("size")));}
        var resources=parent.resources();leases.add(resources.reserve(MembershipResources.Unit.GENERATION,"learner-seed-a",metadata));
        for(Object raw:list(original.value().get("files"))){var file=object(raw);if(((String)file.get("path")).endsWith(".image"))
            leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-seed-a:"+file.get("path"),number(file.get("size"))));}
        leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-seed-a-typed",MembershipApplicationImage.MAXIMUM));
    }
    void supersede()throws IOException {checkMetadata();if(borrowed!=null)borrowed.supersede();}
    void release()throws IOException {
        checkMetadata();AdmissionPaths.absent(source);AdmissionPaths.absent(typed);
        if(borrowed!=null)borrowed.retireSeedResources();
        MembershipLearnerSource.closeChildren(leases.toArray(AutoCloseable[]::new));leases.clear();retired=true;
    }
    boolean retired(){return retired;}
    void forceParents()throws IOException {checkMetadata();AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(typed.getParent());}
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var values=new ArrayList<AutoCloseable>(leases);values.add(lock);MembershipLearnerSource.closeChildren(values.toArray(AutoCloseable[]::new));
    }
}
