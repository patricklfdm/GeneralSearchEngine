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
final class MembershipSourceReceive implements AutoCloseable,MembershipImageBorrow {
    private final Path directory;
    private final Object directoryKey;
    private final Map<String,Object> parent;
    private final Decoded promise,basis;
    private final String root,cut;
    private final Map<String,Object> expectedCut;
    private final UUID session,basisId;
    private final MembershipIdentity source;
    private final MembershipResources resources;
    private final MembershipResources.Lease records;
    private final LongSupplier clock;
    private final long started,budget;
    private final int chunkLimit;
    private final Map<String,MembershipReceiveFile> files=new TreeMap<>();
    private final Map<String,MembershipTransfer.Binding> bindings=new TreeMap<>();
    private final MembershipImageBorrow localImages;
    private final Map<String,Long> borrowedImages=new TreeMap<>();
    private MembershipSourcePacket packet;
    private boolean closed,failed,removed;

    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            UUID session,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget)throws IOException {
        this(directory,root,source,promise,basis,session,UUID.randomUUID(),offer,resources,chunkLimit,clock,started,budget);
    }
    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget)throws IOException {
        this(directory,root,source,promise,basis,session,packetTransfer,offer,resources,chunkLimit,clock,started,budget,null);
    }
    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget,MembershipImageBorrow localImages)throws IOException {
        this(directory,root,source,promise,basis,object(basis.value().get("cut")),session,packetTransfer,offer,resources,chunkLimit,clock,started,budget,localImages);
    }
    /** No frozen grant: only content for the exact discovered cut. */
    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Map<String,Object> expectedCut,
            UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget)throws IOException {
        this(directory,root,source,expectedCut,session,packetTransfer,offer,resources,chunkLimit,clock,started,budget,null);
    }
    MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Map<String,Object> expectedCut,
            UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget,MembershipImageBorrow localImages)throws IOException {
        this(directory,root,source,null,null,expectedCut,session,packetTransfer,offer,resources,chunkLimit,clock,started,budget,localImages);
    }
    private MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            Map<String,Object> expectedCut,UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,
            int chunkLimit,LongSupplier clock,long started,long budget,MembershipImageBorrow localImages)throws IOException {
        this(directory,root,source,promise,basis,expectedCut,session,packetTransfer,offer,resources,chunkLimit,clock,started,budget,localImages,MembershipResources.Unit.SOURCE);
    }
    static MembershipSourceReceive learner(Path directory,String root,MembershipIdentity source,Map<String,Object> expectedCut,
            UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,int chunkLimit,
            LongSupplier clock,long started,long budget)throws IOException {
        return new MembershipSourceReceive(directory,root,source,null,null,expectedCut,session,packetTransfer,offer,resources,chunkLimit,
                clock,started,budget,null,MembershipResources.Unit.LEARNER);
    }
    private MembershipSourceReceive(Path directory,String root,MembershipIdentity source,Decoded promise,Decoded basis,
            Map<String,Object> expectedCut,UUID session,UUID packetTransfer,MembershipSourceExport.Content offer,MembershipResources resources,
            int chunkLimit,LongSupplier clock,long started,long budget,MembershipImageBorrow localImages,MembershipResources.Unit unit)throws IOException {
        require(unit==MembershipResources.Unit.SOURCE || (unit==MembershipResources.Unit.LEARNER && basis==null && localImages==null),"receive staging category");
        MembershipValidation.digest(root);MembershipValidation.uuid(session);
        MembershipValidation.uuid(packetTransfer);require((promise==null)==(basis==null),"receive optional grant pair");
        this.expectedCut=Map.copyOf(expectedCut);
        if(basis!=null) {
        require(promise.family().equals("records") && promise.kind().equals("PROMISE")
                && basis.family().equals("records") && basis.kind().equals("BASIS"),"receive original record kinds");
        for(String field:List.of("root","view","ballot","basisId"))require(Objects.equals(promise.value().get(field),basis.value().get(field)),"receive original grant binding");
        require(root.equals(basis.value().get("root")) && source.nodeId().value().equals(basis.value().get("voter"))
                && promise.value().get("basisId")!=null,"receive source root/identity");
        }
        require(offer.kind()==MembershipTransfer.Kind.CAPSULE && chunkLimit>0 && budget>0 && budget<Long.MAX_VALUE/2,"receive packet/limits");
        this.root=root;this.source=source;this.promise=promise;this.basis=basis;this.session=session;this.resources=resources;
        this.localImages=localImages;
        require(localImages==null || localImages.imageRoot().equals(root),"receive borrowed image root");
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.chunkLimit=chunkLimit;
        basisId=basis==null?null:UUID.fromString((String)basis.value().get("basisId"));cut=cutDigest(expectedCut);time();
        this.directory=AdmissionPaths.safe(directory);parent=AdmissionPaths.binding(this.directory);AdmissionPaths.absent(this.directory);
        records=resources.reserve(MembershipResources.Unit.CONTROL,"received-records-"+UUID.randomUUID(),basis==null?4096:promise.size()+(long)basis.size());
        Object key;
        try{Files.createDirectory(this.directory);key=MembershipBasisSources.key(this.directory);}
        catch(IOException|RuntimeException|Error error){records.close();throw error;}
        directoryKey=key;
        try{create(offer,"source.gscp",unit,packetTransfer);check();}
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
    private MembershipTransfer.Binding binding(MembershipSourceExport.Content content,UUID id) {
        return new MembershipTransfer.Binding(root,session,id,source,basisId,basis==null?null:basis.digest(),cut,content.digest(),content.bytes(),content.kind());
    }
    private void create(MembershipSourceExport.Content offer,String name,MembershipResources.Unit unit)throws IOException {
        create(offer,name,unit,UUID.randomUUID());
    }
    private void create(MembershipSourceExport.Content offer,String name,MembershipResources.Unit unit,UUID id)throws IOException {
        var binding=binding(offer,id);
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
                    var received=MembershipSourcePacket.decode(AdmissionPaths.read(path,MembershipSourcePacket.MAXIMUM));
                    if(basis!=null)received.bind(basis);
                    else require(received.capsule().value().get("root").equals(root)
                            && received.capsule().value().get("cut").equals(expectedCut),"received prefix root/cut");
                    // Reserve every declared image before accepting any application chunk.
                    for(var image:new TreeMap<>(received.images()).entrySet()) {
                        if(localImages!=null && localImages.hasImage(image.getKey(),image.getValue()))borrowedImages.put(image.getKey(),image.getValue());
                        else create(new MembershipSourceExport.Content(image.getKey(),image.getValue(),MembershipTransfer.Kind.APPLICATION),image.getKey()+".image",MembershipResources.Unit.APPLICATION);
                    }
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
        for(String digest:packet.images().keySet())images.put(digest,borrowedImages.containsKey(digest)?localImages.image(digest,borrowedImages.get(digest)):files.get(digest+".image").bytes());
        packet.verifyImages(images);for(var file:files.values())file.checkVerified();check();return Collections.unmodifiableMap(images);
    }
    @Override public synchronized String imageRoot()throws IOException {recheck();return root;}
    @Override public synchronized boolean hasImage(String digest,long bytes)throws IOException {
        recheck();return Objects.equals(packet.images().get(digest),bytes);
    }
    @Override public synchronized byte[] image(String digest,long bytes)throws IOException {
        require(hasImage(digest,bytes),"received original image unavailable");
        byte[] result=borrowedImages.containsKey(digest)?localImages.image(digest,bytes):files.get(digest+".image").bytes();
        require(result.length==bytes && hash(result).equals(digest),"received borrowed image changed");recheck();return result;
    }
    synchronized Decoded basis()throws IOException {check();require(basis!=null,"read-only prefix has no BASIS");return basis;}
    synchronized Decoded promise()throws IOException {check();require(promise!=null,"read-only prefix has no PROMISE");return promise;}
    synchronized MembershipIdentity sourceIdentity()throws IOException {check();return source;}
    /** Recheck a borrowed complete source without allocating another image map. */
    synchronized void recheck()throws IOException {
        packet();for(var file:files.values())file.checkVerified();
        for(var image:borrowedImages.entrySet())localImages.image(image.getKey(),image.getValue());check();
    }
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
