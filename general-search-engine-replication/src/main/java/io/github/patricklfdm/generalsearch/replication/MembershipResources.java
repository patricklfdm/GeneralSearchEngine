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
    private Map<Key,Lease> leases=new HashMap<>();
    private final Set<GenerationClaim> generationClaims=new HashSet<>();
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
        require(!leases.containsKey(key) && generationClaims.stream().noneMatch(c->c.target.equals(key))
                && leases.keySet().stream().filter(k->k.unit==unit).count()+(unit==Unit.GENERATION?generationClaims.size():0)<unit.count,"resource ownership/count");
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
        if(!generationClaims.isEmpty())counts.merge(Unit.GENERATION,generationClaims.size(),Integer::sum);
        return new Usage(metadata,staging,queued,leases.size()+generationClaims.size(),Map.copyOf(counts));
    }
    synchronized void admitChange(long changes,long identities,long results,int joining) {
        require(changes>=0 && changes<256 && identities>=3 && identities<=512 && results>=0 && results<64
                && joining>=0 && joining<=1 && joining<=512-identities,"membership lifetime capacity");
        require(HEADROOM-protectedUsed<=metadataLimit-metadata,"completion headroom");
    }
    synchronized void requireCompleteStorage(Set<Lease> expected) {
        require(generationClaims.isEmpty() && expected.equals(new HashSet<>(leases.values()))
                && leases.keySet().stream().noneMatch(k->k.unit==Unit.CONTROL || k.unit==Unit.WAITER),
                "learner custody requires every original storage lease and no pending work");
    }
    synchronized Map<Lease,Lease> transferCompleteStorage(Map<Lease,String> requested) {
        requireCompleteStorage(requested.keySet());return transferStorage(requested);
    }
    synchronized List<Map<String,Object>> describeCompleteStorage(Set<Lease> expected) {
        requireCompleteStorage(expected);var rows=new ArrayList<Map<String,Object>>();
        for(var lease:expected)rows.add(Map.of("unit",lease.key.unit.name(),"bytes",lease.bytes));
        rows.sort(Comparator.<Map<String,Object>,String>comparing(v->(String)v.get("unit")).thenComparingLong(v->(Long)v.get("bytes")));
        return List.copyOf(rows);
    }
    /** Transfer a quiesced owner's exact storage reservations without an
     * uncharged interval or a duplicate physical-copy allowance. The caller
     * must retain the matching files and move their ownership separately.
     * No category, extent, generation selection or deletion authority changes. */
    synchronized Map<Lease,Lease> transferStorage(Map<Lease,String> requested) {
        Objects.requireNonNull(requested);require(!requested.isEmpty() && requested.size()<=32,"storage transfer count");
        var original=new LinkedHashMap<>(requested);var sources=new HashSet<Key>();var targets=new HashSet<Key>();
        for(var row:original.entrySet()) {
            var lease=Objects.requireNonNull(row.getKey());String name=row.getValue();
            require(!lease.released && leases.get(lease.key)==lease && lease.key.unit!=Unit.CONTROL && lease.key.unit!=Unit.WAITER,
                    "storage transfer requires original storage lease");
            require(name!=null && !name.isEmpty() && name.length()<=128,"storage transfer owner name");
            require(sources.add(lease.key) && targets.add(new Key(lease.key.unit,name)),"storage transfer duplicate target");
            require(generationClaims.stream().noneMatch(c->c.source==lease),"storage transfer has pending generation claim");
        }
        for(var target:targets)require((!leases.containsKey(target) || sources.contains(target))
                && generationClaims.stream().noneMatch(c->c.target.equals(target)),"storage transfer target occupied");
        // Allocate all successor handles before revoking any predecessor.
        var result=new LinkedHashMap<Lease,Lease>();
        original.forEach((lease,name)->result.put(lease,new Lease(new Key(lease.key.unit,name),lease.bytes)));
        var immutable=Collections.unmodifiableMap(result);
        var nextLeases=new HashMap<>(leases);for(var lease:original.keySet())nextLeases.remove(lease.key);
        for(var next:result.values())nextLeases.put(next.key,next);
        leases=nextLeases;for(var lease:original.keySet())lease.released=true;
        return immutable;
    }
    final class Lease implements AutoCloseable {
        private Key key; private long bytes; private boolean released;
        private Lease(Key key,long bytes) { this.key=key;this.bytes=bytes; }
        /** Account a declared control body before allocating it, without releasing its header slot. */
        void reserveControl(long total) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.CONTROL,"control reservation owner");
                require(total>=bytes && total<=Unit.CONTROL.bytes,"control reservation extent");
                long additional=total-bytes;require(additional<=queueLimit-queued,"global queued-byte capacity");
                queued+=additional;bytes=total;
            }
        }
        /** Increase one existing image reservation in place; never alias two physical files. */
        void reserveApplicationMaximum() {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.APPLICATION,"publication image reservation owner");
                long additional=Unit.APPLICATION.bytes-bytes;
                require(additional<=stagingLimit-staging,"shared staging capacity");
                staging+=additional;bytes=Unit.APPLICATION.bytes;
            }
        }
        /** Grow one already-owned floor copy before completing its partial files.
         * This neither shares a reservation nor changes the physical copy count. */
        void reserveStorage(long total) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && (key.unit==Unit.SOURCE || key.unit==Unit.LEARNER || key.unit==Unit.APPLICATION),"storage reservation owner");
                require(total>=bytes && total<=key.unit.bytes,"storage reservation extent");
                long additional=total-bytes;
                if(key.unit.metadata) {
                    require(additional<=metadataLimit-metadata,"metadata capacity");
                    require(HEADROOM-protectedUsed<=metadataLimit-metadata-additional,"completion headroom");
                }
                require(additional<=stagingLimit-staging,"shared staging capacity");
                if(key.unit.metadata)metadata+=additional;
                staging+=additional;bytes=total;
            }
        }
        /** One admission owner expands its existing protected metadata slot;
         * completion headroom and the original per-unit ceiling remain fixed. */
        void reserveMisc(long total) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.MISC,"misc reservation owner");
                require(total>=bytes && total<=Unit.MISC.bytes,"misc reservation extent");
                long additional=total-bytes;require(additional<=metadataLimit-metadata,"metadata capacity");
                require(HEADROOM-protectedUsed-additional<=metadataLimit-metadata-additional,"completion headroom");
                metadata+=additional;protectedUsed+=additional;bytes=total;
            }
        }
        /** Reserve a future generation slot while the original learner still
         * owns every byte. Commit only after the caller forces its selector. */
        GenerationClaim prepareGeneration(String owner) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.LEARNER,"learner generation reservation owner");
                require(owner!=null && !owner.isEmpty() && owner.length()<=128,"generation reservation name");
                var target=new Key(Unit.GENERATION,owner);
                require(bytes<=Unit.GENERATION.bytes && !leases.containsKey(target)
                        && generationClaims.stream().noneMatch(c->c.source==this || c.target.equals(target))
                        && leases.keySet().stream().filter(k->k.unit==Unit.GENERATION).count()+generationClaims.size()<Unit.GENERATION.count,
                        "generation reservation capacity");
                var claim=new GenerationClaim(this,target);generationClaims.add(claim);return claim;
            }
        }
        @Override public void close() {
            synchronized(MembershipResources.this) {
                if(released)return;
                for(var claim:new ArrayList<>(generationClaims))if(claim.source==this)claim.close();
                require(leases.remove(key)==this,"foreign resource release");released=true;
                if(key.unit.metadata)metadata-=bytes;
                if(key.unit.staging)staging-=bytes;
                if(key.unit==Unit.CONTROL)queued-=bytes;
                if(key.unit.protectedSpace())protectedUsed-=bytes;
            }
        }
    }
    /** No duplicate byte reservation or release/reacquire gap. A pending claim
     * consumes a generation count, while its bytes remain charged as LEARNER. */
    final class GenerationClaim implements AutoCloseable {
        private final Lease source;private final Key target;private boolean closed;
        private GenerationClaim(Lease source,Key target){this.source=source;this.target=target;}
        void requireSource(Lease expected) {
            synchronized(MembershipResources.this) {
                require(!closed && generationClaims.contains(this) && source==expected,"generation claim foreign source");
            }
        }
        void commit() {
            synchronized(MembershipResources.this) {
                require(!closed && generationClaims.contains(this) && !source.released
                        && source.key.unit==Unit.LEARNER && leases.get(source.key)==source && !leases.containsKey(target),
                        "generation claim closed or foreign");
                leases.remove(source.key);source.key=target;leases.put(target,source);
                staging-=source.bytes; // Immutable local generation metadata is not receiving scratch.
                generationClaims.remove(this);closed=true;
            }
        }
        @Override public void close(){synchronized(MembershipResources.this){if(!closed){generationClaims.remove(this);closed=true;}}}
    }
}
