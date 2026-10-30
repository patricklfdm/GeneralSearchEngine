package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One original initialization decision under the native joining lock. The
 * journal reserves this entire transaction and blocks grants until completion.
 * No non-genesis ledger can be rebuilt from a current selector alone. */
final class MembershipJoiningRetentionFiles implements AutoCloseable {
    static final String FILE="joining-retention.gsjr",NEXT="joining-retention.next.gsjr",
            DONE="joining-retention.done.gsjr",DONE_NEXT="joining-retention.done.next.gsjr";
    static final Set<String> FILES=Set.of(FILE,NEXT,DONE,DONE_NEXT);
    static final int HEADER=44,METADATA=16384,DONE_MAXIMUM=16384;
    static final int MAXIMUM=HEADER+20+METADATA+MembershipJoiningRetentionSeed.MAXIMUM
            +MembershipPeerRetentionFiles.MAXIMUM+MembershipLearnerRetentionFiles.MAXIMUM+16384;
    private static final int MAGIC=0x47534a52,DONE_MAGIC=0x47534a44;
    private static final List<String> LEDGERS=List.of(MembershipPeerRetentionFiles.FILE,MembershipFutureRetentionFiles.FILE,MembershipLearnerRetentionFiles.FILE);
    private static final Map<String,String> CANDIDATES=Map.of(MembershipPeerRetentionFiles.FILE,MembershipPeerRetentionFiles.NEXT,
            MembershipFutureRetentionFiles.FILE,MembershipFutureRetentionFiles.NEXT,MembershipLearnerRetentionFiles.FILE,MembershipLearnerRetentionFiles.NEXT);
    private record Record(byte[] seed,Map<String,byte[]> initial) {}
    private final MembershipGrantJournal.HistoryRead owner;
    private final MembershipJoinedOwner joined;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Map<String,byte[]> contents=new HashMap<>();
    private final Map<String,FileIdentity> originals=new HashMap<>();
    private final long allowance;
    private Record record;
    private boolean ready,failed,closed;

    MembershipJoiningRetentionFiles(MembershipGrantJournal.HistoryRead owner,MembershipJoinedOwner joined,long allowance)throws IOException {
        this.owner=Objects.requireNonNull(owner);this.joined=Objects.requireNonNull(joined);owner.check();joined.check();
        directory=owner.directory();binding=joined.retentionBinding();this.allowance=allowance;
        require(allowance>=0 && allowance<=MembershipResources.Unit.JOURNAL.bytes,"joining retention journal allowance");
        for(String name:FILES)if(Files.exists(directory.resolve(name),LinkOption.NOFOLLOW_LINKS)) {
            byte[] raw=AdmissionPaths.read(directory.resolve(name),limit(name));remember(name,raw);
            require(extent(raw,magic(name),limit(name))>=0 || name.equals(NEXT) || name.equals(DONE_NEXT),"joining retention incomplete active header");
        }
        require(!(contents.containsKey(FILE) && contents.containsKey(NEXT)) && !(contents.containsKey(DONE) && contents.containsKey(DONE_NEXT)),
                "joining retention duplicate decision");
        require(!contents.containsKey(DONE) && !contents.containsKey(DONE_NEXT) || contents.containsKey(FILE),"joining retention completion without seed");
        String name=contents.containsKey(FILE)?FILE:contents.containsKey(NEXT)?NEXT:null;
        if(name!=null) {
            byte[] raw=contents.get(name);int size=extent(raw,MAGIC,MAXIMUM);
            if(size==raw.length)record=decodeRecord(name,raw);
            else require(name.equals(NEXT),"joining retention incomplete active decision");
        }
        if(contents.containsKey(DONE)) {completion(DONE,contents.get(DONE));ready=true;completedLedgers();}
        long retained=bytes();for(String ledger:LEDGERS)for(String member:List.of(ledger,CANDIDATES.get(ledger)))
            if(Files.exists(directory.resolve(member),LinkOption.NOFOLLOW_LINKS))retained=Math.addExact(retained,Files.size(directory.resolve(member)));
        require(retained<=allowance,"joining retention combined journal capacity");check();
    }
    static boolean present(Path directory){return FILES.stream().anyMatch(n->Files.exists(directory.resolve(n),LinkOption.NOFOLLOW_LINKS));}
    static boolean ledgersPresent(Path directory){return LEDGERS.stream().anyMatch(n->Files.exists(directory.resolve(n),LinkOption.NOFOLLOW_LINKS)
            || Files.exists(directory.resolve(CANDIDATES.get(n)),LinkOption.NOFOLLOW_LINKS));}
    private static int limit(String name){return name.equals(FILE)||name.equals(NEXT)?MAXIMUM:DONE_MAXIMUM;}
    private static int magic(String name){return name.equals(FILE)||name.equals(NEXT)?MAGIC:DONE_MAGIC;}
    private void live(){require(!failed && !closed,"joining retention closed or failed; reopen required");}
    long bytes(){live();long result=0;for(byte[] raw:contents.values())result=Math.addExact(result,raw.length);return result;}
    boolean ready(){live();return ready;}
    boolean hasSeed(){live();return record!=null;}
    private static int extent(byte[] raw,int magic,int maximum) {
        byte[] prefix=ByteBuffer.allocate(8).putInt(magic).putShort((short)1).putShort((short)3).array();
        for(int i=0;i<Math.min(raw.length,8);i++)require(raw[i]==prefix[i],"joining retention framing");
        if(raw.length<12)return -1;
        int size=ByteBuffer.wrap(raw).getInt(8);require(size>HEADER && size<=maximum && raw.length<=size,"joining retention extent");return size;
    }
    private static byte[] framed(int magic,byte[] body,int maximum) {
        require(HEADER+body.length<=maximum,"joining retention frame capacity");
        return ByteBuffer.allocate(HEADER+body.length).putInt(magic).putShort((short)1).putShort((short)3)
                .putInt(HEADER+body.length).put(sha(body)).put(body).array();
    }
    private static byte[] body(byte[] raw,int magic,int maximum) {
        require(extent(raw,magic,maximum)==raw.length,"joining retention incomplete frame");byte[] body=Arrays.copyOfRange(raw,HEADER,raw.length);
        require(Arrays.equals(Arrays.copyOfRange(raw,12,HEADER),sha(body)),"joining retention checksum");return body;
    }
    private Map<String,Object> metadata(String key,String schema) {
        return Map.of("schema",schema,"root",owner.root().manifestDigest(),"owner",MembershipPeerRetentionPlan.identity(owner.identity()),
                "native",binding,"fileKey",key);
    }
    private void metadata(Object value,String name,String schema)throws IOException {
        require(object(value).equals(metadata(key(directory.resolve(name)).toString(),schema)),"joining retention original metadata binding");
    }
    private static void part(ByteArrayOutputStream output,byte[] raw){output.writeBytes(ByteBuffer.allocate(4).putInt(raw.length).array());output.writeBytes(raw);}
    private static byte[] part(ByteBuffer input,int maximum) {
        require(input.remaining()>=4,"joining retention missing member extent");int n=input.getInt();
        require(n>0 && n<=maximum && n<=input.remaining(),"joining retention member extent");byte[] raw=new byte[n];input.get(raw);return raw;
    }
    private byte[] encodeRecord(MembershipJoiningRetentionSeed seed,Map<String,byte[]> initial,String key) {
        var output=new ByteArrayOutputStream();part(output,canonical(metadata(key,"gse-v53-joining-retention/1.3"),METADATA));part(output,seed.bytes());
        for(String name:LEDGERS)part(output,initial.get(name));return framed(MAGIC,output.toByteArray(),MAXIMUM);
    }
    private Record decodeRecord(String name,byte[] raw)throws IOException {
        var input=ByteBuffer.wrap(body(raw,MAGIC,MAXIMUM));byte[] meta=part(input,METADATA);var value=parse(meta,METADATA);
        require(Arrays.equals(meta,canonical(value,METADATA)),"joining retention canonical metadata");metadata(value,name,"gse-v53-joining-retention/1.3");
        byte[] seed=part(input,MembershipJoiningRetentionSeed.MAXIMUM);var initial=new LinkedHashMap<String,byte[]>();
        for(String ledger:LEDGERS)initial.put(ledger,part(input,ledger.equals(MembershipPeerRetentionFiles.FILE)?MembershipPeerRetentionFiles.MAXIMUM:
                ledger.equals(MembershipLearnerRetentionFiles.FILE)?MembershipLearnerRetentionFiles.MAXIMUM:16384));
        require(!input.hasRemaining(),"joining retention trailing members");String root=owner.root().manifestDigest();var identity=owner.identity();
        require(MembershipPeerRetentionFiles.decodeOwned(initial.get(MembershipPeerRetentionFiles.FILE),root,identity).revision()==0
                && MembershipLearnerRetentionFiles.decodeOwned(initial.get(MembershipLearnerRetentionFiles.FILE),root,identity).revision()==0,"joining retention initial revision");
        var future=MembershipFutureRetentionFiles.decodeOwned(initial.get(MembershipFutureRetentionFiles.FILE),root,identity);
        require(future.revision==0 && !future.pending(),"joining retention initial future must be empty");
        return new Record(seed,Collections.unmodifiableMap(initial));
    }
    private Map<String,byte[]> initial(MembershipJoiningRetentionSeed seed) {
        String root=owner.root().manifestDigest();var identity=owner.identity();return Map.of(
                MembershipPeerRetentionFiles.FILE,MembershipPeerRetentionFiles.initial(root,identity,seed.peers),
                MembershipLearnerRetentionFiles.FILE,MembershipLearnerRetentionFiles.initial(root,identity,seed.learner),
                MembershipFutureRetentionFiles.FILE,MembershipFutureRetentionFiles.encode(root,identity,0,null,null,List.of(),Map.of()));
    }
    MembershipJoiningRetentionSeed seed(MembershipCapsule current,byte[] ancestry)throws IOException {
        owner.check();check();require(record!=null,"joining retention original seed incomplete");joined.unused();
        var seed=MembershipJoiningRetentionSeed.read(record.seed,current,ancestry,owner.identity());var expected=initial(seed);
        for(String name:LEDGERS)require(Arrays.equals(record.initial.get(name),expected.get(name)),"joining retention derived initial ledger changed");
        joined.unused();return seed;
    }
    private void guard()throws IOException {owner.check();check();joined.unused();}
    private void absentLedgers() {require(!ledgersPresent(directory),"joining retention ledger without forced seed");}
    void prepare(MembershipJoiningRetentionSeed seed,MembershipBallotAllocator.Cut cut)throws IOException {
        guard();require(!ready,"joining retention already completed");var expected=initial(seed);
        long peak=encodeRecord(seed,expected,"x".repeat(4096)).length+2L*DONE_MAXIMUM;
        for(byte[] raw:expected.values())peak=Math.addExact(peak,2L*raw.length);
        require(peak<=allowance,"joining retention complete transaction capacity");
        if(contents.containsKey(FILE)) {
            require(record!=null && Arrays.equals(record.seed,seed.bytes()),"joining retention different original seed");
            for(String name:LEDGERS)require(Arrays.equals(record.initial.get(name),expected.get(name)),"joining retention different original ledger");
            reseal(FILE,"JOINING_RETENTION_SEED_RECOVERY",cut);return;
        }
        absentLedgers();try {
            create(NEXT,cut,"JOINING_RETENTION_SEED");byte[] bytes=encodeRecord(seed,expected,key(directory.resolve(NEXT)).toString());
            finish(NEXT,bytes,"JOINING_RETENTION_SEED",cut);move(NEXT,FILE,"JOINING_RETENTION_SEED",cut);record=decodeRecord(FILE,contents.get(FILE));
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Exact prefix completion never replaces an uncommitted original inode. */
    private void create(String name,MembershipBallotAllocator.Cut cut,String label)throws IOException {
        guard();if(contents.containsKey(name))return;
        try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(name,new byte[0]);event(label+"_CREATED",cut);
        }
    }
    private void finish(String name,byte[] expected,String label,MembershipBallotAllocator.Cut cut)throws IOException {
        guard();byte[] old=contents.get(name);require(old!=null && old.length<=expected.length && Arrays.equals(old,Arrays.copyOf(expected,old.length)),"joining retention changed original prefix");
        try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            channel.position(old.length);int half=expected.length/2;
            if(old.length<half){AdmissionPaths.write(channel,Arrays.copyOfRange(expected,old.length,half));remember(name,Arrays.copyOf(expected,half));event(label+"_PREFIX_WRITTEN",cut);}
            int at=contents.get(name).length;if(at<expected.length)AdmissionPaths.write(channel,Arrays.copyOfRange(expected,at,expected.length));
            remember(name,expected);event(label+"_WRITTEN",cut);channel.force(true);event(label+"_FORCED",cut);
        }
        AdmissionPaths.forceDirectory(directory);event(label+"_CANDIDATE_PARENT_FORCED",cut);
    }
    private void move(String from,String to,String label,MembershipBallotAllocator.Cut cut)throws IOException {
        guard();require(!Files.exists(directory.resolve(to),LinkOption.NOFOLLOW_LINKS),"joining retention active unexpectedly exists");
        Files.move(directory.resolve(from),directory.resolve(to),StandardCopyOption.ATOMIC_MOVE);
        contents.put(to,contents.remove(from));originals.put(to,originals.remove(from));event(label+"_RENAMED",cut);
        AdmissionPaths.forceDirectory(directory);event(label+"_PARENT_FORCED",cut);
    }
    private void reseal(String name,String label,MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();check();try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
        cut.at(label+"_FORCED");owner.check();check();AdmissionPaths.forceDirectory(directory);cut.at(label+"_PARENT_FORCED");owner.check();check();
    }
    private void ledger(String name,byte[] expected,MembershipBallotAllocator.Cut cut)throws IOException {
        guard();String next=CANDIDATES.get(name);String label=name.equals(MembershipPeerRetentionFiles.FILE)?"JOINING_RETENTION_PEERS":
                name.equals(MembershipFutureRetentionFiles.FILE)?"JOINING_RETENTION_FUTURE":"JOINING_RETENTION_LEARNER";
        if(Files.exists(directory.resolve(name),LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.exact(directory.resolve(name),expected);require(!Files.exists(directory.resolve(next),LinkOption.NOFOLLOW_LINKS),"joining retention active/candidate overlap");
            try(var channel=MembershipFileAccess.open(directory.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
            event(label+"_RECOVERY_FORCED",cut);AdmissionPaths.forceDirectory(directory);event(label+"_RECOVERY_PARENT_FORCED",cut);return;
        }
        // These ledger files become owned by their ordinary classes only after
        // the entire transaction is complete. Track each partial original here.
        if(Files.exists(directory.resolve(next),LinkOption.NOFOLLOW_LINKS))remember(next,AdmissionPaths.read(directory.resolve(next),expected.length));
        create(next,cut,label);finish(next,expected,label,cut);move(next,name,label,cut);
    }
    private byte[] completionBytes(String key) {
        return completionRecord(metadata(key,"gse-v53-joining-retention-done/1.3"),hash(contents.get(FILE)),originals.get(FILE).key().toString(),record.initial);
    }
    /** Pure encoding only. File names are values, never restricted JSON keys. */
    static byte[] completionRecord(Map<String,Object> metadata,String seed,String seedKey,Map<String,byte[]> initial) {
        require(initial.keySet().equals(Set.copyOf(LEDGERS)),"joining retention completion ledger inventory");
        var value=new TreeMap<>(metadata);value.put("seed",seed);value.put("seedKey",seedKey);
        value.put("files",LEDGERS.stream().map(name->Map.of("name",name,"sha256",hash(initial.get(name)))).toList());
        return framed(DONE_MAGIC,canonical(value,DONE_MAXIMUM-HEADER),DONE_MAXIMUM);
    }
    private void completion(String name,byte[] bytes)throws IOException {
        body(bytes,DONE_MAGIC,DONE_MAXIMUM);require(record!=null && contents.containsKey(FILE)
                && Arrays.equals(bytes,completionBytes(key(directory.resolve(name)).toString())),"joining retention completion binding");
    }
    void complete(MembershipBallotAllocator.Cut cut)throws IOException {
        guard();require(record!=null && contents.containsKey(FILE) && !ready,"joining retention forced seed required");
        try {
            for(String name:LEDGERS)ledger(name,record.initial.get(name),cut);
            for(String name:LEDGERS)AdmissionPaths.exact(directory.resolve(name),record.initial.get(name));
            create(DONE_NEXT,cut,"JOINING_RETENTION_DONE");finish(DONE_NEXT,completionBytes(key(directory.resolve(DONE_NEXT)).toString()),"JOINING_RETENTION_DONE",cut);
            move(DONE_NEXT,DONE,"JOINING_RETENTION_DONE",cut);completion(DONE,contents.get(DONE));ready=true;
            // Mutable ledgers now belong exclusively to their normal owners.
            for(String name:LEDGERS){contents.remove(name);originals.remove(name);contents.remove(CANDIDATES.get(name));originals.remove(CANDIDATES.get(name));}
            cut.at("JOINING_RETENTION_BEFORE_RETURN");owner.check();check();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void completedLedgers()throws IOException {
        require(record!=null,"joining retention completed without originals");String root=owner.root().manifestDigest();var identity=owner.identity();
        for(String name:LEDGERS) {
            byte[] raw=AdmissionPaths.read(directory.resolve(name),name.equals(MembershipPeerRetentionFiles.FILE)?MembershipPeerRetentionFiles.MAXIMUM:
                    name.equals(MembershipLearnerRetentionFiles.FILE)?MembershipLearnerRetentionFiles.MAXIMUM:MembershipFutureRetentionFiles.MAXIMUM);
            long revision=name.equals(MembershipPeerRetentionFiles.FILE)?MembershipPeerRetentionFiles.decodeOwned(raw,root,identity).revision():
                    name.equals(MembershipLearnerRetentionFiles.FILE)?MembershipLearnerRetentionFiles.decodeOwned(raw,root,identity).revision():MembershipFutureRetentionFiles.decodeOwned(raw,root,identity).revision;
            if(revision==0)require(Arrays.equals(raw,record.initial.get(name)),"joining retention initial ledger changed after completion");
        }
    }
    void resealCompleted(MembershipBallotAllocator.Cut cut)throws IOException {
        require(ready,"joining retention not complete");completedLedgers();reseal(FILE,"JOINING_RETENTION_SEED_RECOVERY",cut);reseal(DONE,"JOINING_RETENTION_DONE_RECOVERY",cut);
    }
    private void remember(String name,byte[] bytes)throws IOException {contents.put(name,bytes.clone());originals.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));}
    private void event(String point,MembershipBallotAllocator.Cut cut)throws IOException {cut.at(point);guard();}
    void check()throws IOException {
        live();for(var item:originals.entrySet()){var value=item.getValue();require(value.equals(inspect(directory.resolve(item.getKey()),value.bytes(),value.digest())),"joining retention original changed");}
        for(String name:FILES)require(contents.containsKey(name)==Files.exists(directory.resolve(name),LinkOption.NOFOLLOW_LINKS),"joining retention unexpected decision member");
    }
    @Override public void close(){closed=true;}
}
