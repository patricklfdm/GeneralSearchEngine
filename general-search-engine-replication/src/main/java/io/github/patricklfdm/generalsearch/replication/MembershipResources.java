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
    private final Set<SourceClaim> sourceClaims=new HashSet<>();
    private final long metadataLimit, stagingLimit, queueLimit;
    private long metadata, staging, queued, protectedUsed;
    private final MembershipResourceObservations observations;
    private final MembershipControlCloseObservations controlCloses;

    MembershipResources(long stagingLimit) { this(METADATA_LIMIT,stagingLimit,QUEUE_LIMIT); }
    MembershipResources(long metadataLimit,long stagingLimit,long queueLimit) {
        this(metadataLimit,stagingLimit,queueLimit,0);
    }
    MembershipResources(long metadataLimit,long stagingLimit,long queueLimit,int observationLimit) {
        this(metadataLimit,stagingLimit,queueLimit,observationLimit,0);
    }
    MembershipResources(long metadataLimit,long stagingLimit,long queueLimit,int observationLimit,int closeLimit) {
        require(metadataLimit>=HEADROOM && metadataLimit<=METADATA_LIMIT && stagingLimit>0
                && queueLimit>0 && queueLimit<=QUEUE_LIMIT,"resource limit");
        this.metadataLimit=metadataLimit;this.stagingLimit=stagingLimit;this.queueLimit=queueLimit;
        require(observationLimit>=0 && observationLimit<=MembershipResourceObservations.MAXIMUM,"resource observation bound");
        observations=observationLimit==0?null:new MembershipResourceObservations(observationLimit,metadataLimit,stagingLimit,queueLimit);
        require(closeLimit>=0 && closeLimit<=MembershipControlCloseObservations.MAXIMUM && (closeLimit==0 || observations!=null),
                "control close requires resource observations");
        controlCloses=closeLimit==0?null:new MembershipControlCloseObservations(closeLimit);
        observe("START");
    }
    private void observe(String event) {
        if(observations==null)return;
        if(!observations.accepting()){observations.skipped();return;}
        try {
            var charges=new ArrayList<MembershipResourceObservations.Charge>();
            for(var lease:leases.values())charges.add(new MembershipResourceObservations.Charge(lease.key.unit,lease.key.owner,lease.bytes,""));
            for(var claim:generationClaims)charges.add(new MembershipResourceObservations.Charge(claim.target.unit,claim.target.owner,0,claim.source.key.owner));
            for(var claim:sourceClaims)charges.add(new MembershipResourceObservations.Charge(claim.target.unit,claim.target.owner,0,claim.source.key.owner));
            observations.record(event,charges,usage());
        } catch(RuntimeException | OutOfMemoryError error) {
            // Observation must not enter an owning operation's rollback path
            // after its atomic switch. An incomplete trace cannot qualify.
            observations.failed();
        }
    }
    synchronized MembershipResourceObservations.Snapshot observations() {
        require(observations!=null,"resource observations disabled");return observations.snapshot(usage());
    }
    synchronized MembershipResourceObservations.Checkpoint observationCheckpoint() {
        require(observations!=null,"resource observations disabled");return observations.checkpoint(usage());
    }
    synchronized MembershipControlCloseObservations.Snapshot controlCloseObservations() {
        require(controlCloses!=null,"control close observations disabled");return controlCloses.snapshot();
    }
    synchronized Lease reserve(Unit unit,String owner,long bytes) {
        Objects.requireNonNull(unit,"unit");Objects.requireNonNull(owner,"owner");
        require(!owner.isEmpty() && owner.length()<=128 && bytes>=0 && bytes<=unit.bytes,"reservation shape");
        require(unit==Unit.WAITER ? bytes==0 : bytes>0,"reservation bytes");
        var key=new Key(unit,owner);
        require(!leases.containsKey(key) && generationClaims.stream().noneMatch(c->c.target.equals(key))
                && sourceClaims.stream().noneMatch(c->c.target.equals(key))
                && leases.keySet().stream().filter(k->k.unit==unit).count()
                    +(unit==Unit.GENERATION?generationClaims.size():unit==Unit.SOURCE?sourceClaims.size():0)<unit.count,"resource ownership/count");
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
        observe("RESERVE");
        return lease;
    }
    synchronized Usage usage() {
        var counts=new EnumMap<Unit,Integer>(Unit.class);
        for(var key:leases.keySet())counts.merge(key.unit,1,Integer::sum);
        if(!generationClaims.isEmpty())counts.merge(Unit.GENERATION,generationClaims.size(),Integer::sum);
        if(!sourceClaims.isEmpty())counts.merge(Unit.SOURCE,sourceClaims.size(),Integer::sum);
        return new Usage(metadata,staging,queued,leases.size()+generationClaims.size()+sourceClaims.size(),Map.copyOf(counts));
    }
    synchronized void admitChange(long changes,long identities,long results,int joining) {
        require(changes>=0 && changes<256 && identities>=3 && identities<=512 && results>=0 && results<64
                && joining>=0 && joining<=1 && joining<=512-identities,"membership lifetime capacity");
        require(HEADROOM-protectedUsed<=metadataLimit-metadata,"completion headroom");
    }
    synchronized void requireCompleteStorage(Set<Lease> expected) {
        require(generationClaims.isEmpty() && sourceClaims.isEmpty() && expected.equals(new HashSet<>(leases.values()))
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
    record StorageReservation(Unit unit,String owner,long bytes) {}
    private static boolean generationOwner(Key key) {
        return key.unit==Unit.GENERATION || key.unit==Unit.MISC && key.owner.equals("current-authority")
                || key.unit==Unit.APPLICATION && (key.owner.startsWith("generation-a:") || key.owner.startsWith("generation-b:"));
    }
    /** Validate replacement readers while the complete original generation group
     * stays charged. Pending handles cannot allocate, grow or release storage. */
    synchronized GenerationReload prepareGenerationReload(Set<Lease> expected) {
        var actual=new HashSet<Lease>();for(var lease:leases.values())if(generationOwner(lease.key))actual.add(lease);
        require(!expected.isEmpty() && expected.size()<=10 && expected.equals(actual),"generation reload original group");
        require(expected.stream().anyMatch(l->l.key.unit==Unit.MISC) && expected.stream().anyMatch(l->l.key.unit==Unit.GENERATION),
                "generation reload current owner");
        var original=new LinkedHashMap<Key,StorageReservation>();
        var owners=new LinkedHashMap<Key,Lease>();
        for(var lease:expected) {
            require(!lease.released && leases.get(lease.key)==lease
                    && generationClaims.stream().noneMatch(c->c.source==lease)
                    && sourceClaims.stream().noneMatch(c->c.source==lease),"generation reload original handle");
            original.put(lease.key,new StorageReservation(lease.key.unit,lease.key.owner,lease.bytes));owners.put(lease.key,lease);
        }
        return new GenerationReload(original,owners);
    }
    final class GenerationReload implements AutoCloseable {
        private final Map<Key,StorageReservation> originals;
        private final Map<Key,Lease> owners;
        private final Map<Key,Lease> issued=new LinkedHashMap<>();
        private boolean closed;
        private GenerationReload(Map<Key,StorageReservation> originals,Map<Key,Lease> owners){this.originals=originals;this.owners=owners;}
        Lease claim(Unit unit,String owner,long bytes) {
            synchronized(MembershipResources.this) {
                var key=new Key(unit,owner);var original=originals.get(key);var old=owners.get(key);
                require(!closed && original!=null && !old.released && leases.get(key)==old && old.bytes==original.bytes
                        && bytes>0 && bytes<=original.bytes && !issued.containsKey(key),"generation reload claim differs or repeated");
                var lease=new Lease(key,bytes);lease.reload=this;issued.put(key,lease);return lease;
            }
        }
        void commit() {
            synchronized(MembershipResources.this) {
                require(!closed && issued.keySet().equals(originals.keySet()),"generation reload incomplete or closed");
                long lessMetadata=0,lessStaging=0,lessProtected=0;
                for(var row:originals.entrySet()) {
                    var key=row.getKey();var old=owners.get(key);var original=row.getValue();
                    require(!old.released && leases.get(key)==old && key.equals(old.key) && old.bytes==original.bytes,
                            "generation reload original changed");
                    long less=old.bytes-issued.get(key).bytes;
                    if(key.unit.metadata)lessMetadata+=less;if(key.unit.staging)lessStaging+=less;
                    if(key.unit.protectedSpace())lessProtected+=less;
                }
                var next=new HashMap<>(leases);next.putAll(issued);
                var oldHandles=owners.values().toArray(Lease[]::new);var newHandles=issued.values().toArray(Lease[]::new);
                // Everything that can refuse or allocate precedes this switch.
                leases=next;metadata-=lessMetadata;staging-=lessStaging;protectedUsed-=lessProtected;
                for(int n=0;n<oldHandles.length;n++)oldHandles[n].released=true;
                for(int n=0;n<newHandles.length;n++)newHandles[n].reload=null;closed=true;
                observe("GENERATION_RELOAD");
            }
        }
        @Override public void close() {
            synchronized(MembershipResources.this) {
                if(!closed){issued.values().forEach(l->{l.released=true;l.reload=null;});closed=true;}
            }
        }
    }
    /** Extend one inactive generation without releasing its original handles.
     * Other receivers see either the original charges or the complete reservation.
     * A failed extent/count admission leaves every original charge unchanged. */
    synchronized List<Lease> extendGeneration(Map<Lease,Long> growth,List<StorageReservation> additions) {
        return extendStorage(growth,additions,Unit.GENERATION,8);
    }
    /** Consume an already-admitted publication slot as one exact candidate image.
     * The old handle is revoked only after the complete generation reservation
     * succeeds. The maximum image extent remains charged throughout the handoff. */
    synchronized List<Lease> extendGeneration(Map<Lease,Long> growth,List<StorageReservation> additions,
            Lease publication,StorageReservation image) {
        Objects.requireNonNull(publication);Objects.requireNonNull(image);
        require(!publication.released && leases.get(publication.key)==publication && publication.key.unit==Unit.APPLICATION
                && publication.bytes==Unit.APPLICATION.bytes && !growth.containsKey(publication),"generation completion original reservation");
        require(image.unit==Unit.APPLICATION && image.bytes>0 && image.bytes<=publication.bytes
                && image.owner!=null && !image.owner.isEmpty() && image.owner.length()<=128
                && Collections.frequency(additions,image)==1,"generation completion image reservation");
        var target=new Key(Unit.APPLICATION,image.owner);
        require(!leases.containsKey(target) && generationClaims.stream().noneMatch(c->c.target.equals(target))
                && sourceClaims.stream().noneMatch(c->c.target.equals(target)),"generation completion target occupied");
        return extendStorage(growth,additions,Unit.GENERATION,8,publication,image);
    }
    /** Extend retained source copies without giving up charges for partial files.
     * A floor handoff calls this per copy, before releasing its receiving owner. */
    synchronized List<Lease> extendSources(Map<Lease,Long> growth,List<StorageReservation> additions) {
        return extendStorage(growth,additions,Unit.SOURCE,Unit.SOURCE.count+Unit.APPLICATION.count);
    }
    private List<Lease> extendStorage(Map<Lease,Long> growth,List<StorageReservation> additions,Unit metadataUnit,int bound) {
        return extendStorage(growth,additions,metadataUnit,bound,null,null);
    }
    private List<Lease> extendStorage(Map<Lease,Long> growth,List<StorageReservation> additions,Unit metadataUnit,int bound,
            Lease publication,StorageReservation image) {
        require(growth.size()+additions.size()<=bound,"storage reservation group bound");
        var originals=new LinkedHashMap<Lease,Long>();
        for(var row:growth.entrySet()) {
            var lease=Objects.requireNonNull(row.getKey());long total=row.getValue();
            require(!lease.released && leases.get(lease.key)==lease
                    && (lease.key.unit==metadataUnit || lease.key.unit==Unit.APPLICATION),"storage reservation original owner");
            require(total>0 && total<=lease.key.unit.bytes,"storage reservation extent");
            originals.put(lease,lease.bytes);
        }
        for(var row:additions)require(row.unit==metadataUnit || row.unit==Unit.APPLICATION,"storage reservation category");
        long originalMetadata=metadata,originalStaging=staging;
        var acquired=new ArrayList<Lease>(additions.size());
        var ordered=new ArrayList<Lease>(additions.size());
        var successor=publication==null?null:new Lease(new Key(Unit.APPLICATION,image.owner),publication.bytes);
        observe("EXTEND_BEGIN");
        try {
            for(var row:growth.entrySet())row.getKey().reserveStorage(Math.max(row.getKey().bytes,row.getValue()));
            for(var row:additions) {
                if(row.equals(image))ordered.add(successor);
                else {var lease=reserve(row.unit,row.owner,row.bytes);acquired.add(lease);ordered.add(lease);}
            }
            var result=List.copyOf(ordered);
            if(publication!=null) {
                // Allocate the replacement map before revoking the original. Any
                // refusal or allocation failure above leaves the old slot usable.
                require(!leases.containsKey(successor.key),"generation completion target occupied");
                var next=new HashMap<>(leases);next.remove(publication.key);next.put(successor.key,successor);
                leases=next;publication.released=true;
            }
            observe("EXTEND_COMMIT");
            return result;
        }catch(RuntimeException | Error error) {
            acquired.forEach(Lease::close);
            originals.forEach((lease,bytes)->lease.bytes=bytes);
            metadata=originalMetadata;staging=originalStaging;
            observe("EXTEND_ROLLBACK");
            throw error;
        }
    }
    /** Preflight a complete quiescent group replacement without changing charges.
     * The commit repeats the exact-handle/extent check under this monitor. */
    synchronized StorageReplacement prepareCompleteReplacement(Set<Lease> expected,List<StorageReservation> requested) {
        requireCompleteStorage(expected);var originals=new LinkedHashMap<Lease,StorageReservation>();
        for(var lease:expected)originals.put(lease,new StorageReservation(lease.key.unit,lease.key.owner,lease.bytes));
        validateReplacement(requested);return new StorageReplacement(originals,List.copyOf(requested));
    }
    private MembershipResources validateReplacement(List<StorageReservation> requested) {
        require(!requested.isEmpty() && requested.size()<=32,"storage replacement count");
        var trial=new MembershipResources(metadataLimit,stagingLimit,queueLimit);
        for(var row:requested) {
            require(row.unit!=Unit.CONTROL && row.unit!=Unit.WAITER,"storage replacement work category");
            trial.reserve(row.unit,row.owner,row.bytes);
        }
        return trial;
    }
    final class StorageReplacement {
        private final Map<Lease,StorageReservation> originals;
        private final List<StorageReservation> requested;
        private boolean committed;
        private StorageReplacement(Map<Lease,StorageReservation> originals,List<StorageReservation> requested){this.originals=originals;this.requested=requested;}
        StorageBatch commit() {
            synchronized(MembershipResources.this) {
                require(!committed,"storage replacement already committed");requireCompleteStorage(originals.keySet());
                for(var row:originals.entrySet()){var lease=row.getKey();var old=row.getValue();
                    require(!lease.released && leases.get(lease.key)==lease && old.equals(new StorageReservation(lease.key.unit,lease.key.owner,lease.bytes)),"storage replacement original changed");}
                var trial=validateReplacement(requested);var next=new HashMap<Key,Lease>();var issued=new LinkedHashMap<StorageReservation,Lease>();
                for(var row:requested){var key=new Key(row.unit,row.owner);var lease=new Lease(key,row.bytes);next.put(key,lease);issued.put(row,lease);}
                var result=new StorageBatch(issued);
                leases=next;metadata=trial.metadata;staging=trial.staging;queued=trial.queued;protectedUsed=trial.protectedUsed;
                for(var lease:originals.keySet())lease.released=true;committed=true;observe("REPLACE");return result;
            }
        }
    }
    final class StorageBatch implements AutoCloseable {
        private final Map<StorageReservation,Lease> issued;
        private final Set<StorageReservation> claimed=new HashSet<>();
        private boolean closed;
        private StorageBatch(Map<StorageReservation,Lease> issued){this.issued=Map.copyOf(issued);}
        Lease claim(Unit unit,String owner,long bytes) {
            synchronized(MembershipResources.this){var row=new StorageReservation(unit,owner,bytes);var lease=issued.get(row);
                require(!closed && lease!=null && !lease.released && leases.get(lease.key)==lease && claimed.add(row),"storage replacement claim differs or repeated");return lease;}
        }
        void complete(){synchronized(MembershipResources.this){require(!closed && claimed.equals(issued.keySet()),"storage replacement unclaimed member");}}
        @Override public void close(){synchronized(MembershipResources.this){if(!closed){issued.values().forEach(Lease::close);closed=true;}}}
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
            require(generationClaims.stream().noneMatch(c->c.source==lease) && sourceClaims.stream().noneMatch(c->c.source==lease),"storage transfer has pending retention claim");
        }
        for(var target:targets)require((!leases.containsKey(target) || sources.contains(target))
                && generationClaims.stream().noneMatch(c->c.target.equals(target))
                && sourceClaims.stream().noneMatch(c->c.target.equals(target)),"storage transfer target occupied");
        // Allocate all successor handles before revoking any predecessor.
        var result=new LinkedHashMap<Lease,Lease>();
        original.forEach((lease,name)->result.put(lease,new Lease(new Key(lease.key.unit,name),lease.bytes)));
        var immutable=Collections.unmodifiableMap(result);
        var nextLeases=new HashMap<>(leases);for(var lease:original.keySet())nextLeases.remove(lease.key);
        for(var next:result.values())nextLeases.put(next.key,next);
        leases=nextLeases;for(var lease:original.keySet())lease.released=true;
        observe("TRANSFER");
        return immutable;
    }
    final class Lease implements AutoCloseable {
        private Key key; private long bytes; private boolean released;
        private GenerationReload reload;
        private Lease(Key key,long bytes) { this.key=key;this.bytes=bytes; }
        boolean observesClose(){return controlCloses!=null;}
        void closeObservationFailed(){synchronized(MembershipResources.this){if(controlCloses!=null)controlCloses.failed();}}
        long observeCloseBegin(Lease child) {
            if(controlCloses==null)return -1;
            try{return observeCloseBegin(child==null?List.of():List.of(child));}
            catch(RuntimeException|OutOfMemoryError error){closeObservationFailed();return -1;}
        }
        long observeCloseBegin(Collection<Lease> children) {
            if(controlCloses==null)return -1;
            synchronized(MembershipResources.this) {
                try {
                    require(!released && leases.get(key)==this && key.unit==Unit.CONTROL,"control close original owner");
                    var names=new TreeSet<String>();
                    for(var child:children) {
                        require(child!=this && !child.released && leases.get(child.key)==child && child.key.unit==Unit.CONTROL
                                && names.add(child.key.owner),"control close original child");
                    }
                    var point=observations.checkpoint(usage());require(point.complete(),"control close incomplete resources");
                    return controlCloses.record("BEGIN",-1,point.sequence(),key.owner,List.copyOf(names));
                } catch(RuntimeException|OutOfMemoryError error){controlCloses.failed();return -1;}
            }
        }
        void observeCloseReturned(long call) {
            if(controlCloses==null)return;
            synchronized(MembershipResources.this) {
                try {
                    var point=observations.checkpoint(usage());require(point.complete() && released && call>=0,"control close normal return");
                    controlCloses.record("RETURNED",call,point.sequence(),key.owner,List.of());
                } catch(RuntimeException|OutOfMemoryError error){controlCloses.failed();}
            }
        }
        /** Account a declared control body before allocating it, without releasing its header slot. */
        void reserveControl(long total) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.CONTROL,"control reservation owner");
                require(total>=bytes && total<=Unit.CONTROL.bytes,"control reservation extent");
                long additional=total-bytes;require(additional<=queueLimit-queued,"global queued-byte capacity");
                queued+=additional;bytes=total;
                observe("CONTROL_GROW");
            }
        }
        /** Increase one existing image reservation in place; never alias two physical files. */
        void reserveApplicationMaximum() {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.APPLICATION,"publication image reservation owner");
                long additional=Unit.APPLICATION.bytes-bytes;
                require(additional<=stagingLimit-staging,"shared staging capacity");
                staging+=additional;bytes=Unit.APPLICATION.bytes;
                observe("APPLICATION_MAXIMUM");
            }
        }
        /** Grow one already-owned floor copy before completing its partial files.
         * This neither shares a reservation nor changes the physical copy count. */
        void reserveStorage(long total) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && (key.unit==Unit.GENERATION || key.unit==Unit.SOURCE || key.unit==Unit.LEARNER || key.unit==Unit.APPLICATION),"storage reservation owner");
                require(total>=bytes && total<=key.unit.bytes,"storage reservation extent");
                long additional=total-bytes;
                if(key.unit.metadata) {
                    require(additional<=metadataLimit-metadata,"metadata capacity");
                    require(HEADROOM-protectedUsed<=metadataLimit-metadata-additional,"completion headroom");
                }
                if(key.unit.staging)require(additional<=stagingLimit-staging,"shared staging capacity");
                if(key.unit.metadata)metadata+=additional;
                if(key.unit.staging)staging+=additional;
                bytes=total;
                observe("STORAGE_GROW");
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
                observe("MISC_GROW");
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
                        && sourceClaims.stream().noneMatch(c->c.source==this)
                        && leases.keySet().stream().filter(k->k.unit==Unit.GENERATION).count()+generationClaims.size()<Unit.GENERATION.count,
                        "generation reservation capacity");
                var claim=new GenerationClaim(this,target);generationClaims.add(claim);observe("GENERATION_CLAIM");return claim;
            }
        }
        /** A pending joining history is a retained source, not another selected
         * generation. Reserve its existing source slot before forcing the owner
         * marker; keep every byte charged to the learner until commit. */
        SourceClaim prepareSource(String owner) {
            synchronized(MembershipResources.this) {
                require(!released && leases.get(key)==this && key.unit==Unit.LEARNER,"learner source reservation owner");
                require(owner!=null && !owner.isEmpty() && owner.length()<=128,"source reservation name");
                var target=new Key(Unit.SOURCE,owner);
                require(bytes<=Unit.SOURCE.bytes && !leases.containsKey(target)
                        && sourceClaims.stream().noneMatch(c->c.source==this || c.target.equals(target))
                        && generationClaims.stream().noneMatch(c->c.source==this)
                        && leases.keySet().stream().filter(k->k.unit==Unit.SOURCE).count()+sourceClaims.size()<Unit.SOURCE.count,
                        "source reservation capacity");
                var claim=new SourceClaim(this,target);sourceClaims.add(claim);observe("SOURCE_CLAIM");return claim;
            }
        }
        @Override public void close() {
            synchronized(MembershipResources.this) {
                if(released)return;
                if(reload!=null){reload.close();return;}
                for(var claim:new ArrayList<>(generationClaims))if(claim.source==this)claim.close();
                for(var claim:new ArrayList<>(sourceClaims))if(claim.source==this)claim.close();
                require(leases.remove(key)==this,"foreign resource release");released=true;
                if(key.unit.metadata)metadata-=bytes;
                if(key.unit.staging)staging-=bytes;
                if(key.unit==Unit.CONTROL)queued-=bytes;
                if(key.unit.protectedSpace())protectedUsed-=bytes;
                observe("RELEASE");
            }
        }
    }
    /** Ownership changes atomically; metadata and staging remain fully charged. */
    final class SourceClaim implements AutoCloseable {
        private final Lease source;private final Key target;private boolean closed;
        private SourceClaim(Lease source,Key target){this.source=source;this.target=target;}
        void requireSource(Lease expected) {
            synchronized(MembershipResources.this){require(!closed && sourceClaims.contains(this) && source==expected,"source claim foreign source");}
        }
        void commit() {
            synchronized(MembershipResources.this) {
                require(!closed && sourceClaims.contains(this) && !source.released
                        && source.key.unit==Unit.LEARNER && leases.get(source.key)==source && !leases.containsKey(target),"source claim closed or foreign");
                leases.remove(source.key);source.key=target;leases.put(target,source);
                sourceClaims.remove(this);closed=true;
                observe("SOURCE_COMMIT");
            }
        }
        @Override public void close(){synchronized(MembershipResources.this){if(!closed){sourceClaims.remove(this);closed=true;observe("SOURCE_CANCEL");}}}
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
                observe("GENERATION_COMMIT");
            }
        }
        @Override public void close(){synchronized(MembershipResources.this){if(!closed){generationClaims.remove(this);closed=true;observe("GENERATION_CANCEL");}}}
    }
}
