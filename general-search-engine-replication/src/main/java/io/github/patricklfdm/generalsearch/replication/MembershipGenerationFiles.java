package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded inactive generation, including interrupted exact writes. Never deletes an old generation. */
final class MembershipGenerationFiles implements AutoCloseable {
    static final String PENDING="selector.pending.gsr";
    @FunctionalInterface interface Guard {void check() throws IOException;}
    private final Path parent,directory,path;
    private final String slot;
    private final MembershipResources resources;
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private Object pathKey;
    private FileIdentity pending;
    private boolean exists;
    private String reservedPlan;

    MembershipGenerationFiles(Path parent,String active,MembershipResources resources) throws IOException {
        this.parent=parent;this.resources=resources;slot=active.equals("a")?"b":"a";
        directory=parent.resolve(MembershipCurrentGeneration.DIRECTORY);path=directory.resolve(slot);
        try{capture();reserve(null);}catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    boolean exists(){return exists;}
    boolean pending(){return pending!=null;}
    String slot(){return slot;}
    boolean incompleteOrSelected(String selected) throws IOException {
        if(!exists)return false;
        if(!files.containsKey(MembershipCurrentGeneration.MANIFEST))return true;
        try{return selected!=null && selected.equals(decode(AdmissionPaths.read(path.resolve(MembershipCurrentGeneration.MANIFEST),65536),"records","GENERATION").value().get("selection"));}
        catch(IllegalArgumentException error){return true;}
    }
    static long limit(String name) {
        if(name.matches("[0-9a-f]{64}\\.image"))return MembershipResources.Unit.APPLICATION.bytes;
        return switch(name){case "source.gscp"->MembershipResources.Unit.GENERATION.bytes;case "generation.gsr","selected.gsr"->65536;
            case "ancestry.gsr"->96*1024;case "basis.gsr","adopted-certificate.gsr"->16384;case "promise.gsr","owned-tail.gsr"->8192;default->throw new IllegalArgumentException("unknown staged generation file");};
    }
    private void capture() throws IOException {
        files.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);pathKey=exists?key(path):null;
        if(exists) {
            long metadata=0;
            for(String name:children(path,32)) {
                Path file=path.resolve(name);long maximum=limit(name);byte[] bytes=AdmissionPaths.read(file,Math.toIntExact(maximum));
                if(!name.endsWith(".image")){metadata+=bytes.length;require(metadata<=MembershipResources.Unit.GENERATION.bytes,"staged generation metadata capacity");}
                files.put(name,inspect(file,bytes.length,hash(bytes)));
            }
        }
        Path selector=parent.resolve(PENDING);pending=null;
        if(Files.exists(selector,LinkOption.NOFOLLOW_LINKS)) {byte[] bytes=AdmissionPaths.read(selector,4096);pending=inspect(selector,bytes.length,hash(bytes));}
    }
    void check() throws IOException {
        require(exists==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"inactive generation changed");
        if(exists) {
            require(pathKey.equals(key(path)) && children(path,32).equals(files.keySet()),"inactive generation inventory changed");
            for(var row:files.entrySet())require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"inactive generation inode changed");
        }
        require((pending!=null)==Files.exists(parent.resolve(PENDING),LinkOption.NOFOLLOW_LINKS),"pending selector changed");
        if(pending!=null)require(pending.equals(inspect(parent.resolve(PENDING),pending.bytes(),pending.digest())),"pending selector inode changed");
    }
    private void reserve(MembershipGenerationPlan plan) {
        close();if(!exists && plan==null)return;
        try {
            long metadata=plan==null?files.entrySet().stream().filter(e->!e.getKey().endsWith(".image")).mapToLong(e->e.getValue().bytes()).sum():plan.metadata;
            leases.add(resources.reserve(MembershipResources.Unit.GENERATION,slot,Math.max(1,metadata)));
            if(plan==null) {
                for(var file:files.entrySet())if(file.getKey().endsWith(".image"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"generation-"+slot+":"+file.getKey(),Math.max(1,file.getValue().bytes())));
            }else for(var file:plan.files.entrySet())if(file.getKey().endsWith(".image"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"generation-"+slot+":"+file.getKey(),file.getValue().length));
            reservedPlan=plan==null?null:plan.manifest.digest();
        }catch(RuntimeException | Error error){close();throw error;}
    }
    void checkPlan(MembershipGenerationPlan plan) throws IOException {
        require(plan.manifest.value().get("generation").equals(slot),"installation slot");check();
        require(plan.files.keySet().containsAll(files.keySet()),"unexpected staged generation file");
        // A valid older generation is not staging space. It must first pass governing-floor retirement.
        if(files.containsKey(MembershipCurrentGeneration.MANIFEST)) {
            byte[] bytes=AdmissionPaths.read(path.resolve(MembershipCurrentGeneration.MANIFEST),65536);
            require(prefix(bytes,plan.manifest.bytes()),"inactive generation requires retirement or exact original install");
        }
        for(var row:files.entrySet())require(prefix(AdmissionPaths.read(path.resolve(row.getKey()),Math.toIntExact(limit(row.getKey()))),plan.files.get(row.getKey())),"staged generation differs from original plan");
        if(pending!=null)require(prefix(AdmissionPaths.read(parent.resolve(PENDING),4096),plan.selector.bytes()),"pending selector differs from original plan");
    }
    private void ensureReserved(MembershipGenerationPlan plan) {
        // Adoption holds this exact reservation across PROMISE force. Never release and
        // reacquire it after the bound was persisted: another user could take that space.
        if(!plan.manifest.digest().equals(reservedPlan))reserve(plan);
    }
    void reservePlan(MembershipGenerationPlan plan) throws IOException {checkPlan(plan);ensureReserved(plan);}
    void install(MembershipGenerationPlan plan,byte[] previousSelector,Guard owner,Guard oldGeneration,MembershipBallotAllocator.Cut cut) throws IOException {
        checkPlan(plan);owner.check();oldGeneration.check();ensureReserved(plan);cut.at("INSTALL_RESERVED");owner.check();oldGeneration.check();
        if(!exists)Files.createDirectory(path);capture();cut.at("INSTALL_DIRECTORY_CREATED");
        // The full manifest is the exact resumption plan; no replacement source is accepted after any prefix is written.
        complete(path.resolve(MembershipCurrentGeneration.MANIFEST),plan.manifest.bytes(),"INSTALL_MANIFEST",owner,cut);
        for(var file:plan.files.entrySet())if(!file.getKey().equals(MembershipCurrentGeneration.MANIFEST))
            complete(path.resolve(file.getKey()),file.getValue(),file.getKey().endsWith(".image")?"INSTALL_IMAGE":"INSTALL_MEMBER",owner,cut);
        require(children(path,32).equals(plan.files.keySet()),"installed generation inventory");
        for(Object row:list(plan.manifest.value().get("files"))) {
            var file=object(row);inspect(path.resolve((String)file.get("path")),number(file.get("size")),(String)file.get("sha256"));
        }
        inspect(path.resolve(MembershipCurrentGeneration.MANIFEST),plan.manifest.bytes().length,plan.manifest.digest());
        oldGeneration.check();owner.check();AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(directory);cut.at("INSTALL_GENERATION_FORCED");
        complete(parent.resolve(PENDING),plan.selector.bytes(),"INSTALL_SELECTOR",owner,cut);oldGeneration.check();owner.check();
        AdmissionPaths.exact(parent.resolve(MembershipCurrentGeneration.SELECTOR),previousSelector);
        Files.move(parent.resolve(PENDING),parent.resolve(MembershipCurrentGeneration.SELECTOR),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        capture();cut.at("INSTALL_SELECTOR_RENAMED");owner.check();AdmissionPaths.forceDirectory(parent);cut.at("INSTALL_PARENT_FORCED");
        AdmissionPaths.exact(parent.resolve(MembershipCurrentGeneration.SELECTOR),plan.selector.bytes());check();
    }
    private static boolean prefix(byte[] actual,byte[] expected) {return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    private void complete(Path file,byte[] bytes,String event,Guard owner,MembershipBallotAllocator.Cut cut) throws IOException {
        owner.check();check();
        if(Files.exists(file,LinkOption.NOFOLLOW_LINKS))require(prefix(AdmissionPaths.read(file,bytes.length),bytes),"generation member changed from exact prefix");
        try(var channel=FileChannel.open(file,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            channel.position(channel.size());AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,Math.toIntExact(channel.size()),bytes.length));
            capture();cut.at(event+"_WRITTEN");check();owner.check();channel.force(true);cut.at(event+"_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(file,bytes);capture();
    }
    @Override public void close(){leases.forEach(MembershipResources.Lease::close);leases.clear();reservedPlan=null;}
}
