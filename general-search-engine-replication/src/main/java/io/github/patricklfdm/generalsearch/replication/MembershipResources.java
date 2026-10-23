package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Process-local accounting. Reservations do not allocate files or establish durable ownership. */
final class MembershipResources {
    static final long MIB = 1024 * 1024L;
    static final long METADATA_LIMIT = 384 * MIB, QUEUE_LIMIT = 64 * MIB, HEADROOM = 36 * MIB;
    enum Unit {
        GENERATION(2,32*MIB,true,false), SOURCE(6,32*MIB,true,true), LEARNER(1,32*MIB,true,true),
        JOURNAL(1,32*MIB,true,false), CATALOG(1,2*MIB,true,false), MISC(1,2*MIB,true,false),
        APPLICATION(7,64*MIB,false,true), CONTROL(256,8*MIB,false,false), WAITER(64,0,false,false);
        final int count; final long bytes; final boolean metadata, staging;
        Unit(int count,long bytes,boolean metadata,boolean staging) {
            this.count=count;this.bytes=bytes;this.metadata=metadata;this.staging=staging;
        }
        boolean protectedSpace() { return this==JOURNAL || this==CATALOG || this==MISC; }
    }
    record Usage(long metadata,long staging,long queued,int leases,Map<Unit,Integer> counts) {}
    private record Key(Unit unit,String owner) {}
    private final Map<Key,Lease> leases=new HashMap<>();
    private final long metadataLimit, stagingLimit, queueLimit;
    private long metadata, staging, queued, protectedUsed;

    MembershipResources(long stagingLimit) { this(METADATA_LIMIT,stagingLimit,QUEUE_LIMIT); }
    MembershipResources(long metadataLimit,long stagingLimit,long queueLimit) {
        require(metadataLimit>=HEADROOM && metadataLimit<=METADATA_LIMIT && stagingLimit>0
                && queueLimit>0 && queueLimit<=QUEUE_LIMIT,"resource limit");
        this.metadataLimit=metadataLimit;this.stagingLimit=stagingLimit;this.queueLimit=queueLimit;
    }
    synchronized Lease reserve(Unit unit,String owner,long bytes) {
        Objects.requireNonNull(unit,"unit");Objects.requireNonNull(owner,"owner");
        require(!owner.isEmpty() && owner.length()<=128 && bytes>=0 && bytes<=unit.bytes,"reservation shape");
        require(unit==Unit.WAITER ? bytes==0 : bytes>0,"reservation bytes");
        var key=new Key(unit,owner);
        require(!leases.containsKey(key) && leases.keySet().stream().filter(k->k.unit==unit).count()<unit.count,"resource ownership/count");
        // Subtraction avoids overflow even when a caller supplies a very large staging limit.
        if(unit.metadata) {
            require(bytes<=metadataLimit-metadata,"metadata capacity");
            long afterProtected=protectedUsed+(unit.protectedSpace()?bytes:0);
            require(HEADROOM-afterProtected<=metadataLimit-metadata-bytes,"completion headroom");
        }
        if(unit.staging) require(bytes<=stagingLimit-staging,"shared staging capacity");
        if(unit==Unit.CONTROL) require(bytes<=queueLimit-queued,"global queued-byte capacity");
        var lease=new Lease(key,bytes);leases.put(key,lease);
        if(unit.metadata)metadata+=bytes;
        if(unit.staging)staging+=bytes;
        if(unit==Unit.CONTROL)queued+=bytes;
        if(unit.protectedSpace())protectedUsed+=bytes;
        return lease;
    }
    synchronized Usage usage() {
        var counts=new EnumMap<Unit,Integer>(Unit.class);
        for(var key:leases.keySet())counts.merge(key.unit,1,Integer::sum);
        return new Usage(metadata,staging,queued,leases.size(),Map.copyOf(counts));
    }
    synchronized void admitChange(long changes,long identities,long results,int joining) {
        require(changes>=0 && changes<256 && identities>=3 && identities<=512 && results>=0 && results<64
                && joining>=0 && joining<=1 && joining<=512-identities,"membership lifetime capacity");
        require(HEADROOM-protectedUsed<=metadataLimit-metadata,"completion headroom");
    }
    final class Lease implements AutoCloseable {
        private final Key key; private long bytes; private boolean released;
        private Lease(Key key,long bytes) { this.key=key;this.bytes=bytes; }
        /** Increase one existing image reservation in place; never alias two physical files. */
        void reserveApplicationMaximum() {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.APPLICATION,"publication image reservation owner");
                long additional=Unit.APPLICATION.bytes-bytes;
                require(additional<=stagingLimit-staging,"shared staging capacity");
                staging+=additional;bytes=Unit.APPLICATION.bytes;
            }
        }
        @Override public void close() {
            synchronized(MembershipResources.this) {
                if(released)return;
                require(leases.remove(key)==this,"foreign resource release");released=true;
                if(key.unit.metadata)metadata-=bytes;
                if(key.unit.staging)staging-=bytes;
                if(key.unit==Unit.CONTROL)queued-=bytes;
                if(key.unit.protectedSpace())protectedUsed-=bytes;
            }
        }
    }
}
