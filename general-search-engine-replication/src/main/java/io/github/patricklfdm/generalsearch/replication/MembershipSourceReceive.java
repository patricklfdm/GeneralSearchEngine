package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One complete source received into a new, caller-owned scratch directory outside authority.
 * Original records must first be fetched from the authenticated peer. This class checks bytes
 * and ownership, but does not manufacture Owned observations or authorize an install ACK. */
final class MembershipSourceReceive implements AutoCloseable {
    private final Path directory;
    private final Object directoryKey;
    private final Map<String,Object> parent;
    private final Decoded promise,basis;
    private final String root,cut;
    private final UUID session,basisId;
    private final MembershipIdentity source;
    private final MembershipResources resources;
    private final MembershipResources.Lease records;
    private final LongSupplier clock;
    private final long started,budget;
    private final int chunkLimit;
    private final Map<String,MembershipReceiveFile> files=new TreeMap<>();
    private final Map<String,MembershipTransfer.Binding> bindings=new TreeMap<>();
    private MembershipSourcePacket packet;
    private boolean closed,failed,removed;

    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            UUID session,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget)throws IOException {
        MembershipValidation.digest(root);MembershipValidation.uuid(session);
        require(promise.family().equals("records") && promise.kind().equals("PROMISE")
                && basis.family().equals("records") && basis.kind().equals("BASIS"),"receive original record kinds");
        for(String field:List.of("root","view","ballot","basisId"))require(Objects.equals(promise.value().get(field),basis.value().get(field)),"receive original grant binding");
        require(root.equals(basis.value().get("root")) && source.nodeId().value().equals(basis.value().get("voter"))
                && promise.value().get("basisId")!=null,"receive source root/identity");
        require(offer.kind()==MembershipTransfer.Kind.CAPSULE && chunkLimit>0 && budget>0 && budget<Long.MAX_VALUE/2,"receive packet/limits");
        this.root=root;this.source=source;this.promise=promise;this.basis=basis;this.session=session;this.resources=resources;
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.chunkLimit=chunkLimit;
        basisId=UUID.fromString((String)basis.value().get("basisId"));cut=cutDigest(object(basis.value().get("cut")));time();
        this.directory=AdmissionPaths.safe(directory);parent=AdmissionPaths.binding(this.directory);AdmissionPaths.absent(this.directory);
        records=resources.reserve(MembershipResources.Unit.CONTROL,"received-records-"+UUID.randomUUID(),promise.size()+(long)basis.size());
        Object key;
        try{Files.createDirectory(this.directory);key=MembershipBasisSources.key(this.directory);}
        catch(IOException|RuntimeException|Error error){records.close();throw error;}
        directoryKey=key;
        try{create(offer,"source.gscp",MembershipResources.Unit.SOURCE);check();}
        catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void time(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget){failed=true;throw new IllegalArgumentException("original source receive deadline");}}
    private void directory()throws IOException {
        AdmissionPaths.recheck(parent);AdmissionPaths.safe(directory);
        require(directoryKey.equals(MembershipBasisSources.key(directory)),"receive directory replaced");
        var present=new HashSet<String>();for(var item:files.entrySet())if(item.getValue().present())present.add(item.getKey());
        require(MembershipBasisSources.children(directory,8).equals(present),"receive directory inventory");
    }
    private void check()throws IOException {
        require(!closed && !failed,"source receive closed/failed");
        try{time();directory();}catch(IOException|RuntimeException error){failed=true;throw error;}
    }
    private MembershipTransfer.Binding binding(MembershipSourceExport.Content content) {
        return new MembershipTransfer.Binding(root,session,UUID.randomUUID(),source,basisId,basis.digest(),cut,content.digest(),content.bytes(),content.kind());
    }
    private void create(MembershipSourceExport.Content offer,String name,MembershipResources.Unit unit)throws IOException {
        var binding=binding(offer);
        var file=new MembershipReceiveFile(directory.resolve(name),binding,resources,unit,chunkLimit,clock,started,budget,MembershipReceiveFile.Events.NONE);
        files.put(name,file);bindings.put(name,binding);
    }
    synchronized MembershipTransfer.Binding packetBinding()throws IOException {check();return bindings.get("source.gscp");}
    synchronized List<MembershipTransfer.Binding> imageBindings()throws IOException {
        check();require(packet!=null,"source packet not complete");
        return bindings.entrySet().stream().filter(v->!v.getKey().equals("source.gscp")).map(Map.Entry::getValue).toList();
    }
    private String name(MembershipTransfer.Binding incoming) {
        String name=incoming.kind()==MembershipTransfer.Kind.CAPSULE?"source.gscp":incoming.digest()+".image";
        require(incoming.equals(bindings.get(name)),"receive exact content binding");return name;
    }
    synchronized void chunk(MembershipTransfer.Binding incoming,long offset,byte[] bytes,String digest)throws IOException {
        check();String name=name(incoming);files.get(name).chunk(incoming,offset,bytes,digest);time();
    }
    synchronized void finish(MembershipTransfer.Binding incoming)throws IOException {
        check();String name=name(incoming);var file=files.get(name);
        try {
            file.finish(incoming,path->{
                if(name.equals("source.gscp")) {
                    var received=MembershipSourcePacket.decode(AdmissionPaths.read(path,MembershipSourcePacket.MAXIMUM));received.bind(basis);
                    // Reserve every declared image before accepting any application chunk.
                    for(var image:new TreeMap<>(received.images()).entrySet())create(new MembershipSourceExport.Content(image.getKey(),image.getValue(),MembershipTransfer.Kind.APPLICATION),image.getKey()+".image",MembershipResources.Unit.APPLICATION);
                    packet=received;
                }
            });
            check();
        }catch(IOException|RuntimeException error){failed=true;throw error;}
    }
    synchronized MembershipSourcePacket packet()throws IOException {
        check();require(packet!=null,"source packet not complete");files.get("source.gscp").checkVerified();return packet;
    }
    synchronized Map<String,byte[]> images()throws IOException {
        packet();var images=new TreeMap<String,byte[]>();
        for(String digest:packet.images().keySet())images.put(digest,files.get(digest+".image").bytes());
        packet.verifyImages(images);for(var file:files.values())file.checkVerified();check();return Collections.unmodifiableMap(images);
    }
    synchronized Decoded basis()throws IOException {check();return basis;}
    synchronized Decoded promise()throws IOException {check();return promise;}
    /** Cleanup can be retried after an I/O failure; reservations for remaining files stay live. */
    @Override public synchronized void close()throws IOException {
        if(closed)return;
        if(!removed) {
            directory();
            for(String name:List.copyOf(files.keySet())){files.get(name).close();files.remove(name);bindings.remove(name);}
            directory();Files.delete(directory);removed=true;
        }
        AdmissionPaths.recheck(parent);AdmissionPaths.forceDirectory(directory.getParent());records.close();closed=true;
    }
}
