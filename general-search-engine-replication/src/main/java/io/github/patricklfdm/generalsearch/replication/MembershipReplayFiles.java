package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32C;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Disposable typed-replay files only. Never deletes a generation, source, certificate or applied end. */
final class MembershipReplayFiles implements AutoCloseable {
    static final String DIRECTORY="application-replay", CLAIM="claim.json", WORK="work";
    static final int METADATA=8192;
    @FunctionalInterface interface Action<T> { T run(Path absentWork)throws IOException; }
    private record Member(Object key,long bytes,String digest,boolean directory) {}
    private final Path path;
    private final Map<String,Object> binding;
    private final MembershipResources resources;
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private Map<String,Member> members;
    private boolean closed;

    MembershipReplayFiles(Path requested,MembershipResources resources)throws IOException {
        path=AdmissionPaths.safe(requested);binding=AdmissionPaths.binding(path);this.resources=Objects.requireNonNull(resources);
        require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"replay shared journal reservation");
        try {members=scan();if(!members.isEmpty())reserve();}catch(IOException|RuntimeException|Error error){close();throw error;}
    }
    void reserveCompletion(){require(!closed,"replay files closed");reserve();}
    void releaseCompletion()throws IOException {check();require(!present(),"replay files still present");release();}
    private void reserve() {
        if(!leases.isEmpty())return;
        try {
            for(String name:List.of("input","output"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,
                    "application-replay-"+name,MembershipResources.Unit.APPLICATION.bytes));
        }catch(RuntimeException|Error error){release();throw error;}
    }
    private void release(){leases.forEach(MembershipResources.Lease::close);leases.clear();}
    boolean present(){return !members.isEmpty();}
    void check()throws IOException {
        require(!closed,"replay files closed");require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"replay shared journal reservation");
        require(members.equals(scan()),"replay inventory/content/inode changed");
    }
    private Map<String,Member> scan()throws IOException {
        AdmissionPaths.recheck(binding);var result=new TreeMap<String,Member>();
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS))return result;
        directory(result,"");var names=children(path,2);require(Set.of(CLAIM,WORK).containsAll(names),"replay root inventory");
        if(names.contains(CLAIM))file(result,CLAIM,4096);
        if(!names.contains(WORK))return result;
        require(names.contains(CLAIM),"replay work without claim");directory(result,WORK);var work=children(path.resolve(WORK),4);
        var stages=work.stream().filter(v->v.matches("\\.gse-v41-backup-[0-9a-f]{32}\\.staging")).toList();
        var markers=work.stream().filter(v->v.matches("\\.gse-v41-backup-[0-9a-f]{32}\\.staging\\.operation")).toList();
        require(stages.size()<=1 && markers.size()<=1 && !(work.contains("output") && !stages.isEmpty()),"replay output inventory");
        var allowed=new HashSet<>(List.of("input","output"));allowed.addAll(stages);allowed.addAll(markers);require(allowed.containsAll(work),"replay unknown work member");
        if(!stages.isEmpty())require(markers.contains(stages.getFirst()+".operation"),"replay staging without marker");
        if(work.contains("input"))bundle(result,WORK+"/input",false);
        if(work.contains("output"))bundle(result,WORK+"/output",false);
        for(String stage:stages)bundle(result,WORK+"/"+stage,true);
        for(String marker:markers) {
            String stage=marker.substring(0,marker.length()-".operation".length());byte[] expected=operation(stage);
            byte[] actual=AdmissionPaths.read(path.resolve(WORK).resolve(marker),4096);
            require(prefix(actual,expected) && (stages.isEmpty() || actual.length==expected.length),"replay original output marker");
            file(result,WORK+"/"+marker,4096);
        }
        return result;
    }
    private void directory(Map<String,Member> result,String name)throws IOException {
        Path p=path.resolve(name);require(Files.isDirectory(AdmissionPaths.safe(p),LinkOption.NOFOLLOW_LINKS),"replay directory type");result.put(name,new Member(key(p),0,"",true));
    }
    private long file(Map<String,Member> result,String name,int maximum)throws IOException {
        Path p=path.resolve(name);byte[] bytes=AdmissionPaths.read(p,maximum);var file=inspect(p,bytes.length,hash(bytes));
        result.put(name,new Member(file.key(),file.bytes(),file.digest(),false));return bytes.length;
    }
    private void bundle(Map<String,Member> result,String name,boolean staging)throws IOException {
        directory(result,name);var names=children(path.resolve(name),4);var allowed=new HashSet<>(MembershipApplicationImage.MEMBERS);
        if(staging)allowed.add("gse-backup-manifest.staging");
        require(allowed.containsAll(names) && !(names.contains("gse-backup-manifest") && names.contains("gse-backup-manifest.staging")),"replay backup member inventory");
        long bytes=0;for(String member:names) {
            bytes+=file(result,name+"/"+member,MembershipApplicationImage.MAXIMUM);
            require(bytes<=MembershipApplicationImage.MAXIMUM-MembershipApplicationImage.OVERHEAD,"replay application capacity");
        }
    }
    // Exact existing core operation marker, including interrupted prefixes. No authority is inferred from it.
    static byte[] operation(String stage)throws IOException {
        require(stage.matches("\\.gse-v41-backup-[0-9a-f]{32}\\.staging"),"replay marker name");String h=stage.substring(16,48);
        var id=UUID.fromString(h.substring(0,8)+"-"+h.substring(8,12)+"-"+h.substring(12,16)+"-"+h.substring(16,20)+"-"+h.substring(20));
        var buffer=new ByteArrayOutputStream();var out=new DataOutputStream(buffer);
        out.writeLong(0x4753454f50313030L);out.writeShort(1);out.writeShort(0);out.writeByte(1);out.writeLong(id.getMostSignificantBits());out.writeLong(id.getLeastSignificantBits());
        for(String value:List.of(stage,"output")){byte[] bytes=value.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(bytes.length);out.write(bytes);}
        var crc=new CRC32C();crc.update(buffer.toByteArray());out.writeInt((int)crc.getValue());return buffer.toByteArray();
    }
    private static byte[] claim(Decoded originalSelector,Decoded originalCertificate,MembershipIdentity identity) {
        var selector=decode(originalSelector.bytes(),"records","SELECTOR");var certificate=decode(originalCertificate.bytes(),"records","CERTIFICATE");
        require(selector.value().get("root").equals(certificate.value().get("root")) && selector.value().get("node").equals(identity.nodeId().value()),"replay original binding");
        return canonical(Map.of("schema","gse-v53-application-replay/1.3","root",selector.value().get("root"),
                "node",identity.nodeId().value(),"storage",identity.storageId().toString(),"selector",selector.digest(),"certificate",certificate.digest()),4096);
    }
    /** The exclusive owner supplies original authority and checks its fence. The action must use the typed core replay. */
    <T> T execute(Decoded selector,Decoded certificate,MembershipIdentity identity,Action<T> action,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        return execute(selector,certificate,identity,action,guard,cut,false);
    }
    /** An unresolved certificate retains reopen capacity until the journal owner closes/retires it. */
    <T> T executeRetained(Decoded selector,Decoded certificate,MembershipIdentity identity,Action<T> action,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        return execute(selector,certificate,identity,action,guard,cut,true);
    }
    private <T> T execute(Decoded selector,Decoded certificate,MembershipIdentity identity,Action<T> action,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut,boolean retainReservation)throws IOException {
        check();guard.check();byte[] expected=claim(selector,certificate,identity);
        if(members.containsKey(CLAIM))require(prefix(AdmissionPaths.read(path.resolve(CLAIM),4096),expected),"replay changed original claim");
        if(members.containsKey(WORK))require(members.get(CLAIM).bytes()==expected.length && members.get(CLAIM).digest().equals(hash(expected)),"replay incomplete original claim");
        reserve();event("REPLAY_RESERVED",guard,cut);
        if(!present()){Files.createDirectory(path);members=scan();event("REPLAY_DIRECTORY_CREATED",guard,cut);}
        boolean exists=members.containsKey(CLAIM);var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));if(!exists)options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(path.resolve(CLAIM),options)) {
            if(!exists){updateClaim(new byte[0]);event("REPLAY_CLAIM_CREATED",guard,cut);}
            int offset=Math.toIntExact(members.get(CLAIM).bytes()),middle=offset+(expected.length-offset)/2;channel.position(offset);
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));updateClaim(Arrays.copyOf(expected,middle));event("REPLAY_CLAIM_PREFIX_WRITTEN",guard,cut);
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));updateClaim(expected);event("REPLAY_CLAIM_WRITTEN",guard,cut);
            channel.force(true);AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("REPLAY_CLAIM_FORCED",guard,cut);
        }
        clearWork(guard,cut);event("REPLAY_BEFORE_APPLICATION",guard,cut);
        T result;
        try {result=action.run(path.resolve(WORK));}
        finally {
            // Only the delegated core writer may add work. The bound claim/parent must remain unchanged.
            var after=scan();for(String name:List.of("",CLAIM))require(Objects.equals(members.get(name),after.get(name)),"replay writer changed owner claim");members=after;
        }
        event("REPLAY_APPLICATION_FINISHED",guard,cut);clearWork(guard,cut);
        remove(CLAIM,guard,cut);remove("",guard,cut);if(!retainReservation)release();event("REPLAY_BEFORE_RETURN",guard,cut);return result;
    }
    private void updateClaim(byte[] expected)throws IOException {
        var after=scan();for(var row:members.entrySet())if(!row.getKey().equals(CLAIM))require(row.getValue().equals(after.get(row.getKey())),"replay prior member changed");
        var names=new TreeSet<>(members.keySet());names.add(CLAIM);require(names.equals(after.keySet()),"replay claim write inventory");
        var value=after.get(CLAIM);require(value.bytes()==expected.length && value.digest().equals(hash(expected))
                && (!members.containsKey(CLAIM) || members.get(CLAIM).key().equals(value.key())),"replay claim write identity");members=after;
    }
    private void clearWork(MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        // Children first; core operation marker last. No recursive unbounded walk/delete.
        var names=members.keySet().stream().filter(n->n.equals(WORK) || n.startsWith(WORK+"/"))
                .sorted(Comparator.<String>comparingInt(n->n.split("/").length).reversed().thenComparing(Comparator.naturalOrder())).toList();
        for(String name:names)remove(name,guard,cut);
    }
    private void remove(String name,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        event("REPLAY_BEFORE_DELETE",guard,cut);Files.delete(path.resolve(name));var expected=new TreeMap<>(members);expected.remove(name);
        var after=scan();require(expected.equals(after),"replay unlisted deletion/change");members=after;
        AdmissionPaths.forceDirectory(path.resolve(name).getParent());event("REPLAY_DELETED",guard,cut);
    }
    private void event(String event,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {check();guard.check();cut.at(event);check();guard.check();}
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){release();closed=true;}
}
