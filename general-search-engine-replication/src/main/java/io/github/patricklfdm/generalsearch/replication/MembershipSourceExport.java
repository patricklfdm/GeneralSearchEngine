package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A bounded read-only borrow of one actual retained original source. No disk mutation,
 * extra physical source copy, remote ownership receipt or voting authorization. */
final class MembershipSourceExport implements MembershipTransferExport,MembershipImageBorrow {
    record Content(String digest,long bytes,MembershipTransfer.Kind kind) {}
    private record Member(Content content,Path path,byte[] record,Object fileKey) {}
    private final MembershipGrantJournal owner;
    private final MembershipResources.Lease control;
    private final LongSupplier clock;
    private final long started,budget;
    private final Map<String,Member> members;
    private final Map<String,Member> borrowedImages=new HashMap<>();
    private final Set<String> imageSources=new HashSet<>();
    private final MembershipSelection.Source source;
    private final Decoded promise;
    private boolean closed;

    MembershipSourceExport(MembershipGrantJournal owner,Path directory,MembershipSelection.Source source,
            Decoded promise,MembershipResources resources,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"source export time budget");
        this.owner=Objects.requireNonNull(owner);this.source=Objects.requireNonNull(source);this.promise=Objects.requireNonNull(promise);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;this.started=started;
        var lease=resources.reserve(MembershipResources.Unit.CONTROL,"source-export-"+UUID.randomUUID(),promise.size()+(long)source.basis.size());
        try {
            var entries=new TreeMap<String,Member>();record(entries,promise);record(entries,source.basis);
            byte[] packet=source.capsule.packet.bytes();file(entries,directory.resolve(MembershipBasisSources.PACKET),hash(packet),packet.length,MembershipTransfer.Kind.CAPSULE);
            for(var image:source.capsule.packet.images().entrySet())file(entries,directory.resolve(image.getKey()+".image"),image.getKey(),image.getValue(),MembershipTransfer.Kind.APPLICATION);
            members=Map.copyOf(entries);control=lease;
        }catch(IOException|RuntimeException|Error error){lease.close();throw error;}
    }
    private static void record(Map<String,Member> entries,Decoded value) {
        var member=new Member(new Content(value.digest(),value.size(),MembershipTransfer.Kind.RECORD),null,value.bytes(),null);
        require(entries.putIfAbsent(value.digest(),member)==null,"duplicate export content");
    }
    private static void file(Map<String,Member> entries,Path path,String digest,long bytes,MembershipTransfer.Kind kind)throws IOException {
        var identity=MembershipBasisSources.inspect(path,bytes,digest);
        require(entries.putIfAbsent(digest,new Member(new Content(digest,bytes,kind),path,null,identity.key()))==null,"duplicate export content");
    }
    String basisId(){return (String)source.basis.value().get("basisId");}
    boolean pinsSource(String id){return basisId().equals(id) || imageSources.contains(id);}
    /** Local image reuse only; these additional members never enter the wire inventory. */
    void pinImage(String id,Path path,String digest,long bytes)throws IOException {
        var image=new HashMap<String,Member>();file(image,path,digest,bytes,MembershipTransfer.Kind.APPLICATION);
        borrowedImages.put(digest,image.get(digest));imageSources.add(id);
    }
    boolean expired(){long elapsed=clock.getAsLong()-started;return closed || elapsed<0 || elapsed>=budget;}
    void revoke(){if(!closed){closed=true;control.close();}}
    MembershipSelection.Source source()throws IOException {synchronized(owner){owner.checkSourceExport(this);return source;}}
    Decoded promise()throws IOException {synchronized(owner){owner.checkSourceExport(this);return promise;}}
    @Override public MembershipContext context(){return source.capsule.context;}
    @Override public MembershipIdentity identity(){return source.owner;}
    @Override public Map<String,Object> ballot(){return object(source.basis.value().get("ballot"));}
    @Override public Map<String,Content> references()throws IOException {
        var result=new HashMap<String,Content>();for(var content:contents())result.put(content.digest(),content);
        var packet=result.values().stream().filter(v->v.kind()==MembershipTransfer.Kind.CAPSULE).findFirst().orElseThrow();
        require(result.putIfAbsent((String)source.basis.value().get("capsule"),packet)==null,"source capsule reference alias");
        return Map.copyOf(result);
    }
    List<Content> contents()throws IOException {
        synchronized(owner){owner.checkSourceExport(this);return members.values().stream().map(Member::content).sorted(Comparator.comparing(Content::digest)).toList();}
    }
    /** Reuse only an exact pinned physical application, never a packet's asserted hash. */
    @Override public String imageRoot()throws IOException {synchronized(owner){owner.checkSourceExport(this);return context().root;}}
    @Override public boolean hasImage(String digest,long bytes)throws IOException {
        synchronized(owner){
            owner.checkSourceExport(this);MembershipValidation.digest(digest);
            require(bytes>0 && bytes<=MembershipResources.Unit.APPLICATION.bytes,"borrowed image extent");
            var member=members.get(digest);if(member==null)member=borrowedImages.get(digest);
            if(member==null && owner.pinSourceImage(this,digest,bytes))member=borrowedImages.get(digest);
            return member!=null && member.content.kind()==MembershipTransfer.Kind.APPLICATION && member.content.bytes()==bytes;
        }
    }
    @Override public byte[] image(String digest,long size)throws IOException {
        synchronized(owner) {
            require(hasImage(digest,size),"pinned original image unavailable");byte[] bytes=new byte[Math.toIntExact(size)];int offset=0;
            var member=members.get(digest);if(member==null)member=borrowedImages.get(digest);
            while(offset<bytes.length){byte[] part=readMember(member,offset,4*1024*1024);System.arraycopy(part,0,bytes,offset,part.length);offset+=part.length;}
            require(hash(bytes).equals(digest),"pinned original image changed");owner.checkSourceExport(this);return bytes;
        }
    }
    /** No caller-controlled filesystem path; one bounded content-addressed chunk only.
     * The owning journal serializes this check/read/recheck against retirement. */
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner) {
            return readMember(members.get(digest),offset,maximum);
        }
    }
    private byte[] readMember(Member member,long offset,int maximum)throws IOException {
        owner.checkSourceExport(this);
        require(member!=null && maximum>0 && maximum<=4*1024*1024,"source export member/chunk bound");
        require(offset>=0 && offset<member.content.bytes,"source export offset");
        int count=(int)Math.min(maximum,member.content.bytes-offset);byte[] bytes;
        if(member.record!=null)bytes=Arrays.copyOfRange(member.record,Math.toIntExact(offset),Math.toIntExact(offset)+count);
        else {
            AdmissionPaths.regular(member.path);require(member.fileKey.equals(MembershipBasisSources.key(member.path)),"source export inode changed");
            var buffer=ByteBuffer.allocate(count);
            try(var channel=FileChannel.open(member.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
                require(channel.size()==member.content.bytes,"source export file length");channel.position(offset);
                while(buffer.hasRemaining())require(channel.read(buffer)>0,"source export incomplete read");
                require(channel.size()==member.content.bytes,"source export file length");
            }
            bytes=buffer.array();
        }
        owner.checkSourceExport(this);return bytes;
    }
    @Override public void close(){owner.releaseSourceExport(this);}
}
