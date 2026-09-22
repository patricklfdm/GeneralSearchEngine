package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Bounded owned recovery files. All callers hold the store lock and serialize operations. */
final class AutomaticRecoveryFiles {
    static final Set<String> GENERATION_FILES = Set.of("snapshot.gsr", "accepted.gsr", "proofs.gsr", "generation.gsr");
    static final Set<String> OPTIONAL = Set.of("current.gsr", "current.pending.gsr", "generation-started.gsr",
            "selected.gsr", "recovery-floor.gsr", "recovery-floor.pending.gsr", "generation-a", "generation-b", "basis", "transfer", AutomaticBootstrapPlan.BINDING);
    final Path root;
    final Record manifest;
    final String node;
    final ReplicationBounds bounds;
    final AutomaticStore.Faults faults;
    AutomaticRecoveryFiles(Path root, Record manifest, String node, ReplicationBounds bounds, AutomaticStore.Faults faults) {
        this.root=root; this.manifest=manifest; this.node=node; this.bounds=bounds; this.faults=faults;
    }
    static long inventory(Path root, ReplicationBounds bounds) throws IOException {
        long total=0, staging=0;
        var voters=Set.copyOf(nodes(decode(AutomaticAdmission.read(root.resolve("manifest.gsr"),META),"MANIFEST").value()));
        try (var paths=Files.walk(root, 5)) {
            for (Path path : paths.toList()) {
                if (path.equals(root)) continue;
                String rel=root.relativize(path).toString();
                need(!Files.isSymbolicLink(path) && allowed(rel, Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS), voters), "unknown recovery path: " + rel);
                if (!Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS)) {
                    need(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS), "nonregular recovery file");
                    long bytes=Files.size(path); capacity(bytes<=bounds.maxRetainedLogBytes()-total,"retained recovery bytes"); total+=bytes;
                    if (rel.startsWith("basis/") || rel.startsWith("transfer/")) staging+=bytes;
                }
            }
        }
        capacity(staging<=bounds.maxSnapshotStagingBytes(),"recovery staging bytes"); return total;
    }
    private static boolean allowed(String path, boolean directory, Set<String> voters) {
        String[] p=path.split("/");
        if (p.length==1) return directory ? Set.of("generation-a","generation-b","basis","transfer").contains(path)
                : AutomaticAdmission.ROOT_FILES.contains(path) || OPTIONAL.contains(path) && !Set.of("generation-a","generation-b","basis","transfer").contains(path);
        if (p[0].startsWith("generation-")) return !directory && p.length==2 && GENERATION_FILES.contains(p[1]);
        if (p[0].equals("basis")) return voters.contains(p[1]) && (directory ? p.length==2 : p.length==3 && Set.of("basis.gsr","basis.pending.gsr","image.gsr").contains(p[2]));
        if (!p[0].equals("transfer")) return false;
        if (p.length==2 && !directory) return Set.of("selected.pending.gsr","started.pending.gsr","transfer.gsr","transfer.pending.gsr","image.gsr").contains(p[1]);
        if (!Set.of("selection-a","selection-b","floor-a","floor-b","retiring","witness").contains(p[1])) return false;
        if (directory) return p.length==2 || p.length==3 && (p[1].startsWith("floor-") || p[1].equals("witness")) && voters.contains(p[2]);
        if (p[1].startsWith("selection-")) return p.length==3 && voters.stream().anyMatch(n -> p[2].equals("basis-"+n+".gsr") || p[2].equals("image-"+n+".gsr"));
        if (p[1].equals("retiring")) return p.length==3 && (GENERATION_FILES.contains(p[2]) || p[2].equals("current.gsr"));
        return p.length==4 && voters.contains(p[2]) && (GENERATION_FILES.contains(p[3]) || p[3].equals("current.gsr"));
    }
    void mkdir(Path path) throws IOException {
        if (Files.exists(path, LinkOption.NOFOLLOW_LINKS)) { need(Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS),"recovery directory"); return; }
        if (!path.getParent().equals(root)) mkdir(path.getParent());
        Files.createDirectory(path); sync(path.getParent());
    }
    static void sync(Path dir) throws IOException { try (var c=FileChannel.open(dir,StandardOpenOption.READ)) { c.force(true); } }
    byte[] bytes(Path path) throws IOException { return AutomaticAdmission.read(path, IMAGE); }
    Record record(Path path,String name) throws IOException { var row=decode(bytes(path),name); context(row,manifest); return row; }
    private void reserve(String budget,long limit,long total,long old,long requested,String message) {
        if(requested>limit-total+old)faults.capacityRejected(budget,limit,total,old,requested);
        capacity(requested<=limit-total+old,message);
    }
    void write(Path path,byte[] value,String event) throws IOException {
        long total=inventory(root,bounds); long old=Files.exists(path)?Files.size(path):0;
        capacity(value.length<=IMAGE,"recovery write capacity");
        reserve("retained",bounds.maxRetainedLogBytes(),total,old,value.length,"recovery write capacity");
        // A conservative aggregate staging bound includes generations and root metadata as well.
        reserve("staging",bounds.maxSnapshotStagingBytes(),total,old,value.length,"recovery staging capacity");
        mkdir(path.getParent()); faults.at(event+"_BEFORE_WRITE");
        try (var c=FileChannel.open(path,StandardOpenOption.CREATE,StandardOpenOption.WRITE,StandardOpenOption.TRUNCATE_EXISTING,LinkOption.NOFOLLOW_LINKS)) {
            var b=ByteBuffer.wrap(value); int chunk=faults.maximumWriteBytes(); need(chunk>0,"recovery write chunk");
            while(b.hasRemaining()) { int end=Math.min(value.length,b.position()+Math.min(chunk,value.length-b.position())); b.limit(end); need(c.write(b)>0,"recovery write stalled"); b.limit(value.length); faults.at(event+"_WRITE_CHUNK"); }
            faults.at(event+"_AFTER_WRITE"); c.force(true); faults.at(event+"_AFTER_FORCE");
        }
        sync(path.getParent());
    }
    void publish(Path pending,Path target,byte[] bytes,String event) throws IOException {
        write(pending,bytes,event); Files.move(pending,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        faults.at(event+"_AFTER_RENAME"); sync(target.getParent()); faults.at(event+"_BEFORE_ACK");
    }
    void force(Path path) throws IOException { try(var c=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){c.force(true);} }
    void eraseStaging(Path path) throws IOException {
        inventory(root,bounds); if(!Files.exists(path))return;
        try(var paths=Files.walk(path)){for(Path p:paths.sorted(java.util.Comparator.reverseOrder()).toList())Files.delete(p);}
        sync(path.getParent());
    }
    AutomaticRecovery.Basis basis(String peer) throws IOException {
        need(nodes(manifest.value()).contains(peer),"basis requester"); Path dir=root.resolve("basis").resolve(peer);
        var basis=AutomaticRecovery.Basis.read(bytes(dir.resolve("basis.gsr")),bytes(dir.resolve("image.gsr")),manifest);
        need(basis.record().value().get("node").equals(node)&&object(basis.record().value().get("ballot")).get("proposer").equals(peer),"local basis owner/requester");
        return basis;
    }
    AutomaticRecovery.Basis freeze(String peer,Map<String,Object> ballot,Record snapshot,Record accepted) throws IOException {
        need(nodes(manifest.value()).contains(peer) && peer.equals(ballot.get("proposer")),"basis requesting proposer");
        Path dir=root.resolve("basis").resolve(peer); byte[] image=AutomaticRecovery.image(manifest,snapshot,accepted);
        var value=new LinkedHashMap<String,Object>(); value.put("manifestDigest",manifest.digest());value.put("node",node);value.put("ballot",ballot);
        value.put("basisId",java.util.UUID.randomUUID().toString());value.put("imageDigest",digest(image));value.put("imageBytes",(long)image.length);
        value.put("accepted",accepted==null?null:b64(accepted.bytes()));value.put("files",List.of(AutomaticRecovery.file("image.gsr",image)));
        byte[] descriptor=encode("BASIS",value);
        write(dir.resolve("image.gsr"),image,"BASIS_IMAGE");publish(dir.resolve("basis.pending.gsr"),dir.resolve("basis.gsr"),descriptor,"BASIS");
        return AutomaticRecovery.Basis.read(descriptor,image,manifest);
    }
    AutomaticRecovery.Selection selection() throws IOException {
        if(!Files.exists(root.resolve("selected.gsr")))return null;
        var selected=record(root.resolve("selected.gsr"),"SELECTED");
        for(String slot:List.of("selection-a","selection-b")) {
            Path dir=root.resolve("transfer").resolve(slot); var bases=new ArrayList<AutomaticRecovery.Basis>(); boolean found=true;
            for(Object o:list(selected.value().get("bases"))) {
                var b=object(o);String n=text(b,"node"); Path descriptor=dir.resolve("basis-"+n+".gsr");
                if(!Files.exists(descriptor)||!Files.exists(dir.resolve("image-"+n+".gsr"))){found=false;break;}
                // An interrupted inactive slot is not authority. Only matching exact hashes are decoded.
                byte[] raw=bytes(descriptor);if(!sha(raw).equals(shaForBasis(selected,n,raw))){found=false;break;}
                var basis=AutomaticRecovery.Basis.read(raw,bytes(dir.resolve("image-"+n+".gsr")),manifest);
                need(basis.record().value().get("basisId").equals(b.get("basisId")),"selected basis ID");bases.add(basis);
            }
            if(found){var computed=AutomaticRecovery.select(manifest,object(selected.value().get("ballot")),bases);need(Arrays.equals(selected.bytes(),computed.record().bytes()),"selected decision mismatch");return computed;}
        }
        need(false,"selected basis evidence unavailable");return null;
    }
    private static String shaForBasis(Record selected,String node,byte[] raw) {
        if(raw.length<HEADER)return "";
        return list(selected.value().get("bases")).stream().map(AutomaticRecords::object).anyMatch(b->b.get("node").equals(node)&&b.get("basisDigest").equals(digest(raw)))?sha(raw):"";
    }
    void select(AutomaticRecovery.Selection selection) throws IOException {
        var old=selection();
        if(old!=null && old.record().value().get("ballot").equals(selection.record().value().get("ballot"))) {
            need(Arrays.equals(old.record().bytes(),selection.record().bytes()),"changed same-ballot selection"); force(root.resolve("selected.gsr"));sync(root);return;
        }
        String active=old==null?"selection-b":selectionSlot(old.record());String next=active.equals("selection-a")?"selection-b":"selection-a";
        Path dir=root.resolve("transfer").resolve(next);eraseStaging(dir);
        for(var basis:selection.bases()) {String n=text(basis.record().value(),"node");write(dir.resolve("image-"+n+".gsr"),basis.image().encoded().bytes(),"SELECTED_IMAGE");write(dir.resolve("basis-"+n+".gsr"),basis.record().bytes(),"SELECTED_BASIS");}
        publish(root.resolve("transfer/selected.pending.gsr"),root.resolve("selected.gsr"),selection.record().bytes(),"SELECTED");
    }
    private String selectionSlot(Record selected) throws IOException {
        var b=object(list(selected.value().get("bases")).getFirst());
        for(String slot:List.of("selection-a","selection-b")){Path p=root.resolve("transfer").resolve(slot).resolve("basis-"+b.get("node")+".gsr");if(Files.exists(p)&&digest(bytes(p)).equals(b.get("basisDigest")))return slot;}
        throw new IOException("selected slot missing");
    }
    record Source(Record selector,Record seal,Record snapshot,Map<String,byte[]> files) {
        Source {var copy=new LinkedHashMap<String,byte[]>();files.forEach((k,v)->copy.put(k,v.clone()));files=java.util.Collections.unmodifiableMap(copy);}
        @Override public Map<String,byte[]> files(){var copy=new LinkedHashMap<String,byte[]>();files.forEach((k,v)->copy.put(k,v.clone()));return copy;}
        static Source read(Map<String,byte[]> files,Record manifest) {
            need(files.keySet().equals(Set.of("current.gsr","generation.gsr","snapshot.gsr","accepted.gsr","proofs.gsr")),"complete recovery source inventory");
            var selector=decode(files.get("current.gsr"),"SELECTOR");var seal=decode(files.get("generation.gsr"),"GENERATION");var snapshot=decode(files.get("snapshot.gsr"),"SNAPSHOT");
            for(var row:List.of(selector,seal,snapshot))context(row,manifest);
            need(snapshot.value().get("baseSequence").equals(manifest.value().get("baseSequence")),"source genesis sequence");
            need(selector.value().get("node").equals(seal.value().get("node"))&&selector.value().get("generationDigest").equals(seal.digest()),"source selector identity");
            need(seal.value().get("snapshotDigest").equals(snapshot.digest())&&number(seal.value(),"prefixIndex")==AutomaticRecovery.index(snapshot),"source snapshot identity");
            var names=new java.util.HashSet<String>();
            for(Object o:list(seal.value().get("files"))){var f=object(o);String n=text(f,"path");need(Set.of("snapshot.gsr","accepted.gsr","proofs.gsr").contains(n)&&names.add(n),"generation inventory path");byte[] raw=files.get(n);long size=number(f,"size");need(size<=raw.length&&(n.equals("snapshot.gsr")?size==raw.length:true)&&sha(Arrays.copyOf(raw,(int)size)).equals(f.get("sha256")),"generation inventory bytes");}
            need(names.size()==3,"generation inventory incomplete");
            validateSuffix(files, snapshot, text(seal.value(),"node"), manifest);
            return new Source(selector,seal,snapshot,files);
        }
    }
    private static List<Record> rows(byte[] raw,String kind,String node,Record manifest) {
        capacity(raw.length<=IMAGE,"recovery source journal size");int offset=0;var rows=new ArrayList<Record>();
        while(offset<raw.length){need(raw.length-offset>=HEADER,"torn source journal");long length=(long)ByteBuffer.wrap(raw,offset+12,4).getInt()+HEADER;
            need(length>HEADER&&length<=raw.length-offset,"source journal length");var row=decode(Arrays.copyOfRange(raw,offset,offset+(int)length),offset==0?"JOURNAL":kind);context(row,manifest);
            if(offset==0)need(row.value().get("node").equals(node)&&number(row.value(),"recordKind")== (kind.equals("ACCEPT")?24:6),"source journal identity");else rows.add(row);offset+=(int)length;
        }
        need(offset>0,"source journal missing");return rows;
    }
    private static void validateSuffix(Map<String,byte[]> files,Record snapshot,String node,Record manifest) {
        int base=AutomaticRecovery.index(snapshot),last=base,proven=base;var accepted=new LinkedHashMap<Long,Record>();var ballots=new LinkedHashMap<String,Record>();
        String previous=AutomaticRecovery.digestAt(snapshot,base);long previousEpoch=AutomaticRecovery.epochAt(snapshot,base);
        for(var row:rows(files.get("accepted.gsr"),"ACCEPT",node,manifest)) {
            var entry=decode(unbase(row.value().get("entry")),"ENTRY");long index=number(entry.value(),"index");need(index>base&&(index==last||index==last+1L),"source acceptance order");
            if(index==last)need(number(row.value(),"epoch")>number(accepted.get(index).value(),"epoch"),"source acceptance ballot order");
            else {need(entry.value().get("previousDigest").equals(previous)&&number(entry.value(),"previousEpoch")==previousEpoch,"source acceptance predecessor");last++;}
            previous=entry.digest();previousEpoch=number(entry.value(),"originEpoch");accepted.put(index,row);ballots.put(index+":"+number(row.value(),"epoch"),row);
        }
        for(var proof:rows(files.get("proofs.gsr"),"PROOF",node,manifest)) {
            long index=number(proof.value(),"index");need(index==proven+1L&&index<=last,"source proof prefix");var acceptedRow=ballots.get(index+":"+number(proof.value(),"epoch"));
            need(acceptedRow!=null&&AutomaticRecovery.ballotOf(acceptedRow).equals(AutomaticRecovery.ballotOf(proof))&&acceptedRow.value().get("entryDigest").equals(proof.value().get("entryDigest"))&&accepted.get(index).value().get("entryDigest").equals(proof.value().get("entryDigest")),"source proof acceptance");
            need(decode(unbase(acceptedRow.value().get("entry")),"ENTRY").value().get("previousDigest").equals(proof.value().get("previousDigest")),"source proof predecessor");proven++;
        }
        need(last<=proven+1,"source unresolved slots");
    }
    Source current() throws IOException {
        Path path=root.resolve("current.gsr");
        if(!Files.exists(path)){need(!Files.exists(root.resolve("generation-started.gsr"))&&!Files.exists(root.resolve("recovery-floor.gsr")),"lost generation selector");return null;}
        var selector=record(path,"SELECTOR");need(selector.value().get("node").equals(node),"selector voter");
        Path dir=root.resolve(text(selector.value(),"generation"));var files=new LinkedHashMap<String,byte[]>();files.put("current.gsr",selector.bytes());
        for(String n:GENERATION_FILES)files.put(n,bytes(dir.resolve(n)));
        if(Files.exists(root.resolve("generation-started.gsr")))need(record(root.resolve("generation-started.gsr"),"STARTED").value().get("node").equals(node),"started identity");
        var source=Source.read(files,manifest);
        if(source.seal.value().get("selectedDigest")!=null)need(Files.isRegularFile(root.resolve("selected.gsr"),LinkOption.NOFOLLOW_LINKS),"generation lost selected authority");
        return source;
    }
    // Auxiliary exact-cut copy, never selected as this voter's active authority on reopen.
    Source witness(String requester,Record snapshot) throws IOException {
        var files=new java.util.TreeMap<String,byte[]>();files.put("snapshot.gsr",snapshot.bytes());
        files.put("accepted.gsr",encode("JOURNAL",Map.of("manifestDigest",manifest.digest(),"node",node,"recordKind",24)));
        files.put("proofs.gsr",encode("JOURNAL",Map.of("manifestDigest",manifest.digest(),"node",node,"recordKind",6)));
        var value=new LinkedHashMap<String,Object>();value.put("manifestDigest",manifest.digest());value.put("node",node);value.put("snapshotDigest",snapshot.digest());
        value.put("prefixIndex",(long)AutomaticRecovery.index(snapshot));value.put("selectedDigest",null);
        value.put("files",files.entrySet().stream().map(e->AutomaticRecovery.file(e.getKey(),e.getValue())).toList());
        var seal=decode(encode("GENERATION",value),"GENERATION");files.put("generation.gsr",seal.bytes());
        files.put("current.gsr",encode("SELECTOR",Map.of("manifestDigest",manifest.digest(),"node",node,"generation","generation-a","generationDigest",seal.digest())));
        var source=Source.read(files,manifest);Path dir=root.resolve("transfer/witness").resolve(requester);
        saveSource(dir,source,"WITNESS");sync(dir);faults.at("WITNESS_BEFORE_ACK");faults.at("SOURCE_BEFORE_ACK");return source;
    }
    Source install(Record snapshot,Record localTail,Record selected) throws IOException {
        Source current=current();String target=current==null||current.selector.value().get("generation").equals("generation-b")?"generation-a":"generation-b";
        Path dir=root.resolve(target);var files=new java.util.TreeMap<String,byte[]>();files.put("snapshot.gsr",snapshot.bytes());
        byte[] accepts=encode("JOURNAL",Map.of("manifestDigest",manifest.digest(),"node",node,"recordKind",24));
        if(localTail!=null){var combined=new byte[accepts.length+localTail.bytes().length];System.arraycopy(accepts,0,combined,0,accepts.length);System.arraycopy(localTail.bytes(),0,combined,accepts.length,localTail.bytes().length);accepts=combined;}
        files.put("accepted.gsr",accepts);files.put("proofs.gsr",encode("JOURNAL",Map.of("manifestDigest",manifest.digest(),"node",node,"recordKind",6)));
        var value=new LinkedHashMap<String,Object>();value.put("manifestDigest",manifest.digest());value.put("node",node);value.put("snapshotDigest",snapshot.digest());value.put("prefixIndex",(long)AutomaticRecovery.index(snapshot));value.put("selectedDigest",selected==null?null:selected.digest());value.put("files",files.entrySet().stream().map(e->AutomaticRecovery.file(e.getKey(),e.getValue())).toList());
        Record seal=decode(encode("GENERATION",value),"GENERATION");
        Path sealPath=dir.resolve("generation.gsr"); boolean complete=false;
        if(Files.exists(sealPath)) {
            byte[] old=bytes(sealPath);
            if(old.length==seal.bytes().length && Arrays.equals(old,seal.bytes())) complete=true;
            else if(old.length<seal.bytes().length && Arrays.equals(old,Arrays.copyOf(seal.bytes(),old.length))) complete=false;
            else { seal=record(sealPath,"GENERATION");complete=true; }
        }
        if(complete) {
            for(var e:files.entrySet())need(Arrays.equals(bytes(dir.resolve(e.getKey())),e.getValue()),"inactive generation requires durable floor cleanup");
        } else {
            // Incomplete unpublished files can only resume the same exact byte prefix.
            for(var e:files.entrySet()){Path p=dir.resolve(e.getKey());if(Files.exists(p)){byte[] raw=bytes(p);need(raw.length<=e.getValue().length&&Arrays.equals(raw,Arrays.copyOf(e.getValue(),raw.length)),"changed incomplete generation");}write(p,e.getValue(),"GENERATION_"+e.getKey().split("\\.")[0].toUpperCase(java.util.Locale.ROOT));}
            write(sealPath,seal.bytes(),"GENERATION_SEAL");
        }
        sync(dir);byte[] selector=encode("SELECTOR",Map.of("manifestDigest",manifest.digest(),"node",node,"generation",target,"generationDigest",seal.digest()));
        publish(root.resolve("current.pending.gsr"),root.resolve("current.gsr"),selector,"SELECTOR");
        // The selector already names complete authority. The marker forbids future fallback.
        ensureStarted();
        return current();
    }
    void ensureStarted() throws IOException {
        if (Files.exists(root.resolve("current.gsr")) && !Files.exists(root.resolve("generation-started.gsr")))
            publish(root.resolve("transfer/started.pending.gsr"),root.resolve("generation-started.gsr"),encode("STARTED",Map.of("manifestDigest",manifest.digest(),"node",node)),"STARTED");
    }
    private Source source(Path dir) throws IOException {
        var files=new LinkedHashMap<String,byte[]>();for(String n:List.of("current.gsr","generation.gsr","snapshot.gsr","accepted.gsr","proofs.gsr"))files.put(n,bytes(dir.resolve(n)));
        return Source.read(files,manifest);
    }
    private void saveSource(Path dir,Source source,String event) throws IOException {
        // Seal last: an interrupted packet never qualifies as a complete durable source.
        for(String n:List.of("current.gsr","snapshot.gsr","accepted.gsr","proofs.gsr","generation.gsr"))write(dir.resolve(n),source.files().get(n),event);
    }
    private Record floorRecord(List<Source> sources) {
        need(sources.size()==2,"two complete recovery sources required");
        var checked=sources.stream().map(s->Source.read(s.files(),manifest)).sorted(java.util.Comparator.comparing(s->text(s.seal.value(),"node"))).toList();
        need(!checked.getFirst().seal.value().get("node").equals(checked.getLast().seal.value().get("node")),"distinct recovery sources required");
        int cut=AutomaticRecovery.index(checked.getFirst().snapshot);
        for(var s:checked){need(AutomaticRecovery.index(s.snapshot)==cut,"recovery source cut mismatch");AutomaticRecovery.agrees(checked.getFirst().snapshot,s.snapshot,cut);}
        var value=Map.of("manifestDigest",manifest.digest(),"node",node,"index",(long)cut,"entryDigest",AutomaticRecovery.digestAt(checked.getFirst().snapshot,cut),"sources",checked.stream().map(s->Map.of("node",s.seal.value().get("node"),"generationDigest",s.seal.digest(),"snapshotDigest",s.snapshot.digest())).toList());
        return decode(encode("FLOOR",value),"FLOOR");
    }
    private String floorSlot(Record floor) throws IOException {
        for(String slot:List.of("floor-a","floor-b")) {
            Path dir=root.resolve("transfer").resolve(slot);boolean match=true;
            for(Object o:list(floor.value().get("sources"))) {var s=object(o);Path p=dir.resolve(text(s,"node")).resolve("generation.gsr");if(!Files.exists(p)){match=false;break;}byte[] raw=bytes(p);if(raw.length<HEADER||!digest(raw).equals(s.get("generationDigest"))){match=false;break;}}
            if(match)return slot;
        }
        need(false,"floor complete source evidence missing");return null;
    }
    Record floor() throws IOException {
        if(!Files.exists(root.resolve("recovery-floor.gsr")))return null;
        var floor=record(root.resolve("recovery-floor.gsr"),"FLOOR");need(floor.value().get("node").equals(node),"floor voter");
        Path dir=root.resolve("transfer").resolve(floorSlot(floor));var sources=new ArrayList<Source>();
        for(Object o:list(floor.value().get("sources")))sources.add(source(dir.resolve(text(object(o),"node"))));
        need(Arrays.equals(floor.bytes(),floorRecord(sources).bytes()),"floor source binding");
        var current=current();need(current!=null&&AutomaticRecovery.index(current.snapshot)>=number(floor.value(),"index"),"floor exceeds current durable prefix");
        AutomaticRecovery.agrees(current.snapshot,sources.getFirst().snapshot,Math.toIntExact(number(floor.value(),"index")));
        return floor;
    }
    void establishFloor(List<Source> sources) throws IOException {
        var proposed=floorRecord(sources);var current=current();need(current!=null,"floor needs local generation");
        need(sources.stream().anyMatch(s->s.seal.value().get("node").equals(node)&&s.seal.digest().equals(current.seal.digest())),"floor lacks current local source");
        var old=floor();if(old!=null)need(number(proposed.value(),"index")>=number(old.value(),"index"),"recovery floor rollback");
        String slot=old==null||floorSlot(old).equals("floor-b")?"floor-a":"floor-b";Path dir=root.resolve("transfer").resolve(slot);eraseStaging(dir);
        for(var s:sources)saveSource(dir.resolve(text(s.seal.value(),"node")),s,"FLOOR_SOURCE");
        publish(root.resolve("recovery-floor.pending.gsr"),root.resolve("recovery-floor.gsr"),proposed.bytes(),"FLOOR");floor();
    }
    private void deletable(byte[] journal,String kind,Record floor,Record currentSnapshot) {
        int offset=0;boolean first=true;
        while(offset<journal.length){need(journal.length-offset>=HEADER,"torn retirement ledger");long size=(long)ByteBuffer.wrap(journal,offset+12,4).getInt()+HEADER;need(size>HEADER&&size<=journal.length-offset,"retirement row length");var row=decode(Arrays.copyOfRange(journal,offset,offset+(int)size),first?"JOURNAL":kind);context(row,manifest);offset+=(int)size;
            if(first){need(row.value().get("node").equals(node)&&number(row.value(),"recordKind")== (kind.equals("ACCEPT")?24:6),"retirement journal identity");first=false;continue;}
            long index=kind.equals("ACCEPT")?number(decode(unbase(row.value().get("entry")),"ENTRY").value(),"index"):number(row.value(),"index");
            need(index<=number(floor.value(),"index"),"retirement contains tail above durable floor");
            if(kind.equals("PROOF"))need(row.value().get("entryDigest").equals(AutomaticRecovery.digestAt(currentSnapshot,(int)index)),"retirement proof conflict");
        }
        need(!first,"missing retirement journal");
    }
    void cleanup() throws IOException {
        inventory(root,bounds);var floor=floor();need(floor!=null,"two-source durable recovery floor required before deletion");var active=current();
        String inactive=active.selector.value().get("generation").equals("generation-a")?"generation-b":"generation-a";
        Path dir=root.resolve(inactive), retired=root.resolve("transfer/retiring");
        if(Files.exists(dir)) {
            Source old;
            if(Files.exists(retired.resolve("generation.gsr"))) {old=source(retired);need(old.selector.value().get("generation").equals(inactive),"retirement generation mismatch");}
            else {
                var seal=record(dir.resolve("generation.gsr"),"GENERATION");var files=new LinkedHashMap<String,byte[]>();for(String n:GENERATION_FILES)files.put(n,bytes(dir.resolve(n)));
                files.put("current.gsr",encode("SELECTOR",Map.of("manifestDigest",manifest.digest(),"node",node,"generation",inactive,"generationDigest",seal.digest())));
                old=Source.read(files,manifest);
                need(AutomaticRecovery.index(old.snapshot)<=number(floor.value(),"index"),"retirement snapshot above floor");AutomaticRecovery.agrees(active.snapshot,old.snapshot,AutomaticRecovery.index(old.snapshot));
                deletable(old.files().get("accepted.gsr"),"ACCEPT",floor,active.snapshot);deletable(old.files().get("proofs.gsr"),"PROOF",floor,active.snapshot);
                eraseStaging(retired);saveSource(retired,old,"RETIREMENT");
            }
            need(AutomaticRecovery.index(old.snapshot)<=number(floor.value(),"index"),"retirement floor");AutomaticRecovery.agrees(active.snapshot,old.snapshot,AutomaticRecovery.index(old.snapshot));
            deletable(old.files().get("accepted.gsr"),"ACCEPT",floor,active.snapshot);deletable(old.files().get("proofs.gsr"),"PROOF",floor,active.snapshot);
            // Verify every remaining byte against the durable retirement inventory before deleting any.
            for(String n:GENERATION_FILES)if(Files.exists(dir.resolve(n)))need(Arrays.equals(bytes(dir.resolve(n)),old.files().get(n)),"retirement bytes changed");
            for(String n:List.of("accepted.gsr","proofs.gsr","snapshot.gsr","generation.gsr")){Files.deleteIfExists(dir.resolve(n));sync(dir);faults.at("DELETE_AFTER_FILE");}
            Files.delete(dir);sync(root);faults.at("DELETE_AFTER_DIRECTORY");
        }
        // Root metadata and promise history live forever. Only the sealed journal headers remain after retirement.
        for(String name:List.of("accepted.gsr","proofs.gsr")) {
            byte[] raw=bytes(root.resolve(name));deletable(raw,name.equals("accepted.gsr")?"ACCEPT":"PROOF",floor,active.snapshot);
            int header=ByteBuffer.wrap(raw).getInt(12)+HEADER;
            try(var c=FileChannel.open(root.resolve(name),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){c.truncate(header);c.force(true);}faults.at("DELETE_AFTER_ROOT_TRUNCATE");
        }
        eraseStaging(retired);
    }
    void beginTransfer(Record transfer) throws IOException {
        context(transfer,manifest);need(transfer.value().get("node").equals(node)&&number(transfer.value(),"receivedBytes")==0,"transfer initialization");
        Path meta=root.resolve("transfer/transfer.gsr");
        if(Files.exists(meta)){var old=record(meta,"TRANSFER");if(old.value().get("transferId").equals(transfer.value().get("transferId"))){var reset=new LinkedHashMap<>(old.value());reset.put("receivedBytes",0L);need(reset.equals(transfer.value()),"changed transfer identity");return;}}
        // Metadata first: after an interruption, prior image bytes cannot acquire a new received watermark.
        publish(root.resolve("transfer/transfer.pending.gsr"),meta,transfer.bytes(),"TRANSFER_BEGIN");write(root.resolve("transfer/image.gsr"),new byte[0],"TRANSFER_RESET");
    }
    long chunk(String id,long offset,byte[] chunk,Map<String,Object> ballot) throws IOException {
        var meta=record(root.resolve("transfer/transfer.gsr"),"TRANSFER");need(meta.value().get("transferId").equals(id)&&meta.value().get("ballot").equals(ballot),"stale transfer identity/ballot");
        long received=number(meta.value(),"receivedBytes"),total=number(meta.value(),"imageBytes");
        capacity(chunk.length>0&&chunk.length<=bounds.snapshotChunkBytes(),"transfer chunk capacity");need(offset>=0&&offset<=received&&chunk.length<=total-offset,"transfer chunk offset");
        Path image=root.resolve("transfer/image.gsr");long count=inventory(root,bounds),old=Files.exists(image)?Files.size(image):0;
        reserve("staging",bounds.maxSnapshotStagingBytes(),count,old,total,"transfer reservation");
        reserve("retained",bounds.maxRetainedLogBytes(),count,old,total,"transfer reservation");
        if(offset<received){need(chunk.length<=received-offset&&Files.exists(image),"overlapping transfer retry");byte[] raw=bytes(image);need(raw.length>=received&&Arrays.equals(chunk,Arrays.copyOfRange(raw,(int)offset,(int)offset+chunk.length)),"changed transfer retry");force(image);return received;}
        try(var c=FileChannel.open(image,StandardOpenOption.CREATE,StandardOpenOption.READ,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            need(c.size()>=received,"lost acknowledged transfer bytes");c.truncate(received);c.position(received);var b=ByteBuffer.wrap(chunk);while(b.hasRemaining())need(c.write(b)>0,"transfer write stalled");faults.at("TRANSFER_DATA_AFTER_WRITE");c.force(true);faults.at("TRANSFER_DATA_AFTER_FORCE");
        }
        sync(image.getParent());var value=new LinkedHashMap<>(meta.value());value.put("receivedBytes",received+chunk.length);
        publish(root.resolve("transfer/transfer.pending.gsr"),root.resolve("transfer/transfer.gsr"),encode("TRANSFER",value),"TRANSFER_PROGRESS");return received+chunk.length;
    }
    AutomaticRecovery.Image completeTransfer(String id,Map<String,Object> ballot) throws IOException {
        var meta=record(root.resolve("transfer/transfer.gsr"),"TRANSFER");need(meta.value().get("transferId").equals(id)&&meta.value().get("ballot").equals(ballot),"stale transfer");byte[] raw=bytes(root.resolve("transfer/image.gsr"));
        need(number(meta.value(),"receivedBytes")==number(meta.value(),"imageBytes")&&raw.length==number(meta.value(),"imageBytes")&&digest(raw).equals(meta.value().get("imageDigest")),"incomplete/changed transfer image");
        return AutomaticRecovery.Image.read(raw,manifest);
    }
}
