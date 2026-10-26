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
final class MembershipSourceExport implements AutoCloseable {
    record Content(String digest,long bytes,MembershipTransfer.Kind kind) {}
    private record Member(Content content,Path path,byte[] record,Object fileKey) {}
    private final MembershipGrantJournal owner;
    private final MembershipResources.Lease control;
    private final LongSupplier clock;
    private final long started,budget;
    private final Map<String,Member> members;
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
    boolean expired(){long elapsed=clock.getAsLong()-started;return closed || elapsed<0 || elapsed>=budget;}
    void revoke(){if(!closed){closed=true;control.close();}}
    MembershipSelection.Source source()throws IOException {synchronized(owner){owner.checkSourceExport(this);return source;}}
    Decoded promise()throws IOException {synchronized(owner){owner.checkSourceExport(this);return promise;}}
    List<Content> contents()throws IOException {
        synchronized(owner){owner.checkSourceExport(this);return members.values().stream().map(Member::content).sorted(Comparator.comparing(Content::digest)).toList();}
    }
    /** No caller-controlled filesystem path; one bounded content-addressed chunk only.
     * The owning journal serializes this check/read/recheck against retirement. */
    byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner) {
            owner.checkSourceExport(this);var member=members.get(digest);
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
    }
    @Override public void close(){owner.releaseSourceExport(this);}
}
