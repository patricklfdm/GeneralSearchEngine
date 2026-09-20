package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;

import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Local automatic authority. No transport, application publication or voter initialization. */
final class AutomaticStore implements AutoCloseable {
    static final int MAX_PROMISES = 10_000, MAX_ENTRIES = 1_000_000;
    interface Faults {
        Faults NONE = new Faults() { };
        default void at(String cut) throws IOException { }
        default int maximumWriteBytes() { return Integer.MAX_VALUE; }
    }
    private record Ref(long offset, int size, String digest, long epoch, String entryDigest) { }
    private final Path directory;
    private final String node;
    private final Record manifest;
    private final ReplicationBounds bounds;
    private final Faults faults;
    private final FileChannel lockChannel, promises;
    private FileChannel acceptances, proofs;
    private final AutomaticRecoveryFiles recovery;
    private Record baseSnapshot;
    private int baseIndex;
    private AutomaticRecovery.Selection selected;
    private final FileLock lock;
    private final Map<Long, Record> grants = new HashMap<>();
    private final List<List<Ref>> accepted = new ArrayList<>();
    private final List<Ref> proven = new ArrayList<>();
    private Record promise;
    private long retainedBytes, acceptanceRows, applicationSequence;
    private boolean failed, closed;

    private AutomaticStore(Path root, String node, Record manifest, ReplicationBounds bounds, Faults faults,
                           FileChannel owner, FileLock lock, FileChannel promises, FileChannel accepts, FileChannel proofs) {
        this.directory = root; this.node = node; this.manifest = manifest; this.bounds = bounds; this.faults = faults;
        this.lockChannel = owner; this.lock = lock; this.promises = promises; this.acceptances = accepts; this.proofs = proofs;
        this.applicationSequence = number(manifest.value(), "baseSequence");
        this.recovery = new AutomaticRecoveryFiles(root, manifest, node, bounds, faults);
    }

    static AutomaticStore open(Path path, byte[] expectedManifest, String node, ReplicationBounds bounds, Faults faults) {
        var channels = new ArrayList<FileChannel>(); FileLock lock = null; boolean success = false;
        try {
            var expected = decode(expectedManifest, "MANIFEST"); Path root = AutomaticAdmission.safe(path);
            need(Files.isRegularFile(root.resolve("replica.lock"), LinkOption.NOFOLLOW_LINKS), "missing ownership file");
            FileChannel owner = channel(root.resolve("replica.lock")); channels.add(owner);
            try { lock = owner.tryLock(); }
            catch (OverlappingFileLockException error) { throw failure(STORAGE_FAILURE, "automatic authority already owned", error); }
            if (lock == null) throw failure(STORAGE_FAILURE, "automatic authority already owned", null);
            var manifest = AutomaticAdmission.verify(root, expected, node, bounds);
            var recovery = new AutomaticRecoveryFiles(root, manifest, node, bounds, faults);
            var current = recovery.current();
            Path active = current == null ? root : root.resolve(text(current.selector().value(), "generation"));
            FileChannel promises = channel(root.resolve("promises.gsr")); channels.add(promises);
            FileChannel accepts = channel(active.resolve("accepted.gsr")); channels.add(accepts);
            FileChannel proofs = channel(active.resolve("proofs.gsr")); channels.add(proofs);
            var store = new AutomaticStore(root, node, manifest, bounds, faults, owner, lock, promises, accepts, proofs);
            store.retainedBytes = AutomaticRecoveryFiles.inventory(root, bounds);
            store.baseSnapshot = current == null ? store.genesisSnapshot() : current.snapshot();
            store.baseIndex = AutomaticRecovery.index(store.baseSnapshot);
            store.applicationSequence = number(store.baseSnapshot.value(), "applicationSequence");
            store.selected = recovery.selection();
            store.load(); store.checkRecovery(); success = true; return store;
        } catch (IOException error) { throw failure(STORAGE_FAILURE, "cannot open automatic authority", error); }
        finally {
            if (!success) {
                if (lock != null) try { lock.release(); } catch (IOException ignored) { }
                for (FileChannel channel : channels) try { channel.close(); } catch (IOException ignored) { }
            }
        }
    }
    private static FileChannel channel(Path path) throws IOException {
        return FileChannel.open(path, StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS);
    }
    private void load() throws IOException {
        var replacements = new ArrayList<Record>();
        long offset = header(promises, 4);
        while (offset < promises.size()) {
            Record row = read(promises, offset, "PROMISE"); context(row, manifest);
            long epoch = number(row.value(), "epoch");
            capacity(grants.size() < MAX_PROMISES, "promise count");
            need(promise == null ? epoch == 1 : epoch > number(promise.value(), "epoch"), "promise order/duplicate");
            grants.put(epoch, row); promise = row; offset += row.bytes().length;
        }
        need(promise != null, "missing genesis promise");
        offset = header(acceptances, 24);
        while (offset < acceptances.size()) {
            Record row = read(acceptances, offset, "ACCEPT"); context(row, manifest); granted(row);
            var entry = decode(unbase(row.value().get("entry")), "ENTRY"); long index = number(entry.value(), "index");
            capacity(index <= MAX_ENTRIES && ++acceptanceRows <= (long) MAX_ENTRIES + MAX_PROMISES, "acceptance count");
            need(index > baseIndex && (index == acceptedThrough() || index == acceptedThrough() + 1L), "acceptance slot order");
            predecessor(entry);
            if (index == acceptedThrough()) {
                var previous = latest((int) index);
                need(previous.epoch < number(row.value(), "epoch"), "changed accepted ballot retry");
                if (!previous.entryDigest.equals(entry.digest())) replacements.add(row);
            } else {
                predecessor(entry); accepted.add(new ArrayList<>());
            }
            accepted.get((int) index - baseIndex - 1).add(ref(offset, row, entry.digest())); offset += row.bytes().length;
        }
        offset = header(proofs, 6);
        while (offset < proofs.size()) {
            Record row = read(proofs, offset, "PROOF"); context(row, manifest);
            long index = number(row.value(), "index"); need(index == provenThrough() + 1L && index <= acceptedThrough(), "proof prefix/order");
            matchingAcceptance(row); advanceSequence(entry((int) index));
            proven.add(ref(offset, row, text(row.value(), "entryDigest"))); offset += row.bytes().length;
        }
        need(accepted.size() <= proven.size() + 1L, "more than one unresolved accepted slot");
        for (var row : replacements) {
            var value = decode(unbase(row.value().get("entry")), "ENTRY");
            int index = Math.toIntExact(number(value.value(), "index"));
            if (index <= provenThrough()) continue;
            var latest = acceptance(index);
            boolean frozen = selected != null && selected.bases().stream().anyMatch(b -> b.image().accepted() != null
                    && Arrays.equals(b.image().accepted().bytes(), latest.bytes()));
            need(frozen || selectedValue(latest, decode(unbase(latest.value().get("entry")), "ENTRY")), "unproven replacement lacks selected authority");
        }
    }
    private int acceptedThrough() { return baseIndex + accepted.size(); }
    private int provenThrough() { return baseIndex + proven.size(); }
    private String digestAt(int index) throws IOException { return index <= baseIndex ? AutomaticRecovery.digestAt(baseSnapshot,index) : entry(index).digest(); }
    private long epochAt(int index) throws IOException { return index <= baseIndex ? AutomaticRecovery.epochAt(baseSnapshot,index) : number(entry(index).value(),"originEpoch"); }
    private Record genesisSnapshot() throws IOException {
        var genesis=decode(AutomaticAdmission.read(directory.resolve("genesis.gsr"),IMAGE),"GENESIS");
        var value=new java.util.LinkedHashMap<String,Object>();value.put("manifestDigest",manifest.digest());value.put("baseSequence",manifest.value().get("baseSequence"));
        value.put("applicationSequence",manifest.value().get("baseSequence"));value.put("application",genesis.value().get("application"));value.put("anchors",List.of());value.put("terminalProof",null);
        return decode(encode("SNAPSHOT",value),"SNAPSHOT");
    }
    private boolean selectedValue(Record acceptance,Record entry) {
        if(selected==null||!selected.record().value().get("ballot").equals(AutomaticRecovery.ballotOf(acceptance))
                ||number(entry.value(),"index")!=number(selected.record().value(),"prefixIndex")+1)return false;
        Object next=selected.record().value().get("nextEntry");
        return next==null ? number(entry.value(),"originEpoch")==number(acceptance.value(),"epoch")
                &&entry.value().get("originIncarnation").equals(acceptance.value().get("incarnation"))&&number(entry.value(),"operation")==9
                : Arrays.equals(entry.bytes(),unbase(next));
    }
    private void checkRecovery() throws IOException {
        need(baseSnapshot.value().get("baseSequence").equals(manifest.value().get("baseSequence")),"snapshot genesis sequence");
        if(baseIndex==0)AutomaticRecovery.agrees(baseSnapshot,genesisSnapshot(),0);
        if(baseSnapshot.value().get("terminalProof")!=null)need(number(decode(unbase(baseSnapshot.value().get("terminalProof")),"PROOF").value(),"epoch")<=number(promise.value(),"epoch"),"snapshot exceeds retained promise");
        if(selected!=null){need(number(object(selected.record().value().get("ballot")),"epoch")<=number(promise.value(),"epoch"),"selection exceeds root promise");checkPrefix(selected.snapshot(),Math.min(provenThrough(),AutomaticRecovery.index(selected.snapshot())));}
        recovery.floor();
    }
    private void checkPrefix(Record snapshot,int through) throws IOException {
        need(through<=provenThrough()&&through<=AutomaticRecovery.index(snapshot),"prefix comparison range");
        for(int i=1;i<=through;i++)need(digestAt(i).equals(AutomaticRecovery.digestAt(snapshot,i))&&epochAt(i)==AutomaticRecovery.epochAt(snapshot,i),"recovery conflicts with local proven prefix");
        if(through==baseIndex&&through==AutomaticRecovery.index(snapshot))AutomaticRecovery.agrees(baseSnapshot,snapshot,through);
    }
    private Record snapshot(byte[] application) throws IOException {
        if(provenThrough()==baseIndex) {need(Arrays.equals(application,unbase(baseSnapshot.value().get("application"))),"changed checkpoint application at same cut");return baseSnapshot;}
        var anchors=new ArrayList<Object>(list(baseSnapshot.value().get("anchors")));
        for(int i=baseIndex+1;i<=provenThrough();i++){var e=entry(i);anchors.add(Map.of("entryDigest",e.digest(),"operation",e.value().get("operation"),"originEpoch",e.value().get("originEpoch"),"originIncarnation",e.value().get("originIncarnation"),"payloadDigest",e.value().get("payloadDigest")));}
        var value=new java.util.LinkedHashMap<String,Object>(baseSnapshot.value());value.put("anchors",anchors);value.put("application",b64(application));value.put("applicationSequence",applicationSequence);
        value.put("terminalProof",b64(read(proofs,proven.getLast().offset,"PROOF").bytes()));return decode(encode("SNAPSHOT",value),"SNAPSHOT");
    }
    private <T> T recoveryIo(java.util.concurrent.Callable<T> operation) {
        usable();
        try {T result=operation.call();retainedBytes=AutomaticRecoveryFiles.inventory(directory,bounds);return result;}
        catch(AutomaticReplicationException error){failed=true;throw error;}
        catch(Exception error){failed=true;throw failure(STORAGE_FAILURE,"ambiguous recovery I/O; voter quarantined",error);}
    }
    synchronized AutomaticRecovery.Basis prepare(byte[] grant,String requester,byte[] application) {
        usable();var ballot=decode(grant,"PROMISE");context(ballot,manifest);
        need(requester.equals(ballot.value().get("proposer")),"prepare requester");
        if(number(ballot.value(),"epoch")==number(promise.value(),"epoch"))return recoveryIo(()->{
            active(ballot);var basis=recovery.basis(requester);need(basis.record().value().get("ballot").equals(AutomaticRecovery.ballotOf(promise)),"frozen basis unavailable; use higher ballot");
            recovery.force(directory.resolve("basis").resolve(requester).resolve("image.gsr"));recovery.force(directory.resolve("basis").resolve(requester).resolve("basis.gsr"));return basis;
        });
        // Validate the image before granting. Once granted, an incomplete basis is never resampled at that ballot.
        return recoveryIo(()->{var image=snapshot(application);promise(grant);return recovery.freeze(requester,AutomaticRecovery.ballotOf(promise),image,acceptedThrough()>provenThrough()?acceptance(acceptedThrough()):null);});
    }
    synchronized byte[] basisChunk(String requester,String id,long offset,int length) {
        return recoveryIo(()->{var basis=recovery.basis(requester);need(basis.record().value().get("basisId").equals(id)&&basis.record().value().get("ballot").equals(AutomaticRecovery.ballotOf(promise)),"stale frozen basis");byte[] raw=basis.image().encoded().bytes();capacity(length>0&&length<=bounds.snapshotChunkBytes(),"basis chunk bound");need(offset>=0&&offset<=raw.length&&length<=raw.length-offset,"basis chunk offset");return Arrays.copyOfRange(raw,(int)offset,(int)offset+length);});
    }
    synchronized AutomaticRecovery.Selection select(List<AutomaticRecovery.Basis> bases) {
        return recoveryIo(()->{var decision=AutomaticRecovery.select(manifest,AutomaticRecovery.ballotOf(promise),bases);
            boolean retry=selected!=null&&Arrays.equals(selected.record().bytes(),decision.record().bytes());
            need(retry||AutomaticRecovery.index(decision.snapshot())>=provenThrough(),"selection would roll back local proof");
            checkPrefix(decision.snapshot(),Math.min(provenThrough(),AutomaticRecovery.index(decision.snapshot())));
            recovery.select(decision);selected=decision;return decision;});
    }
    synchronized void installSelected() {
        recoveryIo(()->{need(selected!=null&&selected.record().value().get("ballot").equals(AutomaticRecovery.ballotOf(promise)),"no current recovery selection");install(selected.snapshot(),selected.record());return null;});
    }
    synchronized void checkpoint(byte[] application) { recoveryIo(()->{install(snapshot(application),null);return null;}); }
    // Expected maintenance pressure is checked before entering the ambiguous-I/O path.
    synchronized boolean generationAvailable(Record snapshot) {
        usable();
        if(Arrays.equals(baseSnapshot.bytes(),snapshot.bytes()))return true;
        try {
            var current=recovery.current();
            String target=current==null||current.selector().value().get("generation").equals("generation-b")?"generation-a":"generation-b";
            return !Files.exists(directory.resolve(target));
        } catch(IOException error) {throw failure(STORAGE_FAILURE,"generation inventory",error);}
    }
    synchronized void installProven(Record snapshot) {
        usable();context(snapshot,manifest);
        need(snapshot.name().equals("SNAPSHOT"),"rejoin snapshot kind");
        int cut=AutomaticRecovery.index(snapshot);
        need(cut>=provenThrough(),"rejoin cannot roll back proof");
        capacity(acceptedThrough()<=cut,"rejoin waits for the retained next acceptance");
        if(snapshot.value().get("terminalProof")!=null)
            need(number(decode(unbase(snapshot.value().get("terminalProof")),"PROOF").value(),"epoch")<=number(promise.value(),"epoch"),"rejoin proof exceeds promise");
        capacity(generationAvailable(snapshot),"rejoin needs two-source retirement first");
        if(Arrays.equals(baseSnapshot.bytes(),snapshot.bytes()))return;
        recoveryIo(()->{install(snapshot,null);return null;});
    }
    synchronized AutomaticRecoveryFiles.Source currentSource() {return recoveryIo(recovery::current);}
    synchronized AutomaticRecoveryFiles.Source retainWitness(String requester,Record snapshot) {
        usable();context(snapshot,manifest);need(snapshot.name().equals("SNAPSHOT"),"witness snapshot kind");
        need(nodes(manifest.value()).contains(requester)&&!requester.equals(node),"witness requester");
        int cut=AutomaticRecovery.index(snapshot);
        if(cut>provenThrough())throw failure(AutomaticReplicationException.Reason.NOT_READY,"witness exceeds local proof",null);
        need(snapshot.value().get("baseSequence").equals(manifest.value().get("baseSequence")),"witness genesis sequence");
        if(snapshot.value().get("terminalProof")!=null)need(number(decode(unbase(snapshot.value().get("terminalProof")),"PROOF").value(),"epoch")<=number(promise.value(),"epoch"),"witness proof exceeds promise");
        return recoveryIo(()->{checkPrefix(snapshot,cut);if(cut==0)AutomaticRecovery.agrees(genesisSnapshot(),snapshot,0);return recovery.witness(requester,snapshot);});
    }
    private void install(Record image,Record decision) throws IOException {
        int cut=AutomaticRecovery.index(image);need(cut>=provenThrough(),"snapshot rolls back proven prefix");checkPrefix(image,provenThrough());
        Record tail=acceptedThrough()>cut?acceptance(acceptedThrough()):null;
        if(tail!=null)AutomaticRecovery.tail(image,decode(unbase(tail.value().get("entry")),"ENTRY"));
        var generation=recovery.install(image,tail,decision);
        acceptances.close();proofs.close();Path dir=directory.resolve(text(generation.selector().value(),"generation"));
        acceptances=channel(dir.resolve("accepted.gsr"));proofs=channel(dir.resolve("proofs.gsr"));
        grants.clear();accepted.clear();proven.clear();promise=null;acceptanceRows=0;baseSnapshot=image;baseIndex=cut;applicationSequence=number(image.value(),"applicationSequence");load();checkRecovery();
    }
    synchronized AutomaticRecoveryFiles.Source recoverySource() {return recoveryIo(()->{var source=recovery.current();need(source!=null,"source requires complete selected generation");Path dir=directory.resolve(text(source.selector().value(),"generation"));for(String name:AutomaticRecoveryFiles.GENERATION_FILES)recovery.force(dir.resolve(name));AutomaticRecoveryFiles.sync(dir);recovery.force(directory.resolve("current.gsr"));AutomaticRecoveryFiles.sync(directory);faults.at("SOURCE_BEFORE_ACK");return source;});}
    synchronized void establishRecoveryFloor(List<AutomaticRecoveryFiles.Source> sources) {recoveryIo(()->{recovery.establishFloor(sources);return null;});}
    synchronized void cleanup() {recoveryIo(()->{recovery.cleanup();return null;});}
    synchronized void beginTransfer(byte[] bytes) {recoveryIo(()->{var row=decode(bytes,"TRANSFER");need(row.value().get("ballot").equals(AutomaticRecovery.ballotOf(promise)),"transfer promise");recovery.beginTransfer(row);return null;});}
    synchronized long transferChunk(String id,long offset,byte[] bytes) {return recoveryIo(()->recovery.chunk(id,offset,bytes.clone(),AutomaticRecovery.ballotOf(promise)));}
    synchronized AutomaticRecovery.Image completeTransfer(String id) {return recoveryIo(()->recovery.completeTransfer(id,AutomaticRecovery.ballotOf(promise)));}
    private long header(FileChannel channel, int kind) throws IOException {
        Record row = read(channel, 0, "JOURNAL"); context(row, manifest);
        need(row.value().get("node").equals(node) && number(row.value(), "recordKind") == kind, "ledger header identity");
        return row.bytes().length;
    }
    private Record read(FileChannel channel, long offset, String name) throws IOException {
        need(offset >= 0 && channel.size() - offset >= HEADER, "torn authority header");
        channel.position(offset); var header = ByteBuffer.allocate(HEADER); AutomaticAdmission.readFully(channel, header);
        int length = ByteBuffer.wrap(header.array()).getInt(12);
        int maximum = (int) number(object(CATALOG.get(name)), "maximum");
        capacity(length > 0 && (long) length + HEADER <= Math.min(maximum, bounds.maxFrameBytes()), "authority record bound");
        need((long) length + HEADER <= channel.size() - offset, "torn authority body");
        var bytes = ByteBuffer.allocate(length + HEADER); bytes.put(header.array()); AutomaticAdmission.readFully(channel, bytes);
        return decode(bytes.array(), name);
    }
    private static Ref ref(long offset, Record row, String entryDigest) {
        return new Ref(offset, row.bytes().length, row.digest(), number(row.value(), "epoch"), entryDigest);
    }
    private Ref latest(int index) { var rows = accepted.get(index - baseIndex - 1); return rows.get(rows.size() - 1); }
    private Record acceptance(int index) throws IOException { return read(acceptances, latest(index).offset, "ACCEPT"); }
    private Record entry(int index) throws IOException { return decode(unbase(acceptance(index).value().get("entry")), "ENTRY"); }
    private void predecessor(Record entry) throws IOException {
        int index = Math.toIntExact(number(entry.value(), "index"));
        need(entry.value().get("previousDigest").equals(digestAt(index - 1))
                && number(entry.value(), "previousEpoch") == epochAt(index - 1), "entry prefix mismatch");
    }
    private static boolean sameBallot(Record a, Record b) {
        return List.of("epoch", "proposer", "incarnation").stream().allMatch(k -> java.util.Objects.equals(a.value().get(k), b.value().get(k)));
    }
    private void granted(Record row) {
        var grant = grants.get(number(row.value(), "epoch")); need(grant != null && sameBallot(row, grant), "acceptance without matching retained promise");
    }
    private void matchingAcceptance(Record proof) throws IOException {
        int index = Math.toIntExact(number(proof.value(), "index"));
        Ref match = accepted.get(index - baseIndex - 1).stream().filter(r -> r.epoch == number(proof.value(), "epoch")).findFirst().orElse(null);
        need(match != null && match.entryDigest.equals(proof.value().get("entryDigest")), "proof lacks matching local acceptance");
        var row = read(acceptances, match.offset, "ACCEPT"); need(sameBallot(row, proof), "proof ballot mismatch");
        need(latest(index).entryDigest.equals(proof.value().get("entryDigest")), "proof conflicts with latest accepted value");
        var entry = decode(unbase(row.value().get("entry")), "ENTRY");
        need(entry.value().get("previousDigest").equals(proof.value().get("previousDigest")), "proof predecessor mismatch");
    }
    private void active(Record row) {
        if (!sameBallot(row, promise)) throw failure(STALE_EPOCH, "record does not match the current promise", null);
    }
    private void usable() {
        if (closed) throw failure(CLOSED, "automatic store closed", null);
        if (failed) throw failure(STORAGE_FAILURE, "automatic authority quarantined after ambiguous I/O", null);
    }
    private void advanceSequence(Record entry) {
        if (number(entry.value(), "operation") <= 8) {
            capacity(applicationSequence < Long.MAX_VALUE, "application sequence exhausted"); applicationSequence++;
        }
    }
    synchronized Map<String, Object> status() {
        usable(); return Map.of("promisedEpoch", number(promise.value(), "epoch"), "promiseCount", grants.size(),
                "acceptedThrough", acceptedThrough(), "provenThrough", provenThrough(), "applicationSequence", applicationSequence,
                "retainedBytes", retainedBytes, "node", node, "manifestDigest", manifest.digest());
    }
    synchronized Record promised() { usable(); return promise; }
    synchronized boolean quarantined() { return failed||closed; }
    record Head(int index,long originEpoch,String digest) { }
    synchronized Head head() {
        usable();int index=provenThrough();
        try {return new Head(index,epochAt(index),digestAt(index));}
        catch(IOException error) {failed=true;throw failure(STORAGE_FAILURE,"cannot read proven head",error);}
    }
    synchronized Record manifest() { usable(); return manifest; }
    synchronized ReplicationBounds bounds() { usable(); return bounds; }
    synchronized AutomaticLeadershipPolicy leadershipPolicy() {
        usable();
        try {
            var seal=decode(Files.readAllBytes(directory.resolve("bootstrap-seal.gsr")),"SEAL");
            var receipt=decode(unbase(seal.value().get("receipt")),"RECEIPT");
            var plan=decode(unbase(receipt.value().get("plan")),"PLAN");
            var target=list(plan.value().get("targets")).stream().map(AutomaticRecords::object)
                    .filter(t->node.equals(t.get("node"))).findFirst().orElseThrow();
            var policy=object(target.get("policy"));
            return new AutomaticLeadershipPolicy(Math.toIntExact(number(policy,"heartbeatIntervalMillis")),
                    Math.toIntExact(number(policy,"minElectionTimeoutMillis")),Math.toIntExact(number(policy,"maxElectionTimeoutMillis")),
                    Math.toIntExact(number(policy,"operationTimeoutMillis")));
        } catch (IOException error) { failed=true;throw failure(STORAGE_FAILURE,"cannot read sealed leadership policy",error); }
    }
    /** Immutable bounded input for application reconstruction outside the control dispatcher. */
    record Replay(Record snapshot,List<Record> entries,int through,long sequence) {
        Replay { entries=List.copyOf(entries); }
    }
    synchronized Replay replay() {
        usable();
        try {
            long bytes=baseSnapshot.bytes().length;var entries=new ArrayList<Record>();
            for(int i=baseIndex+1;i<=provenThrough();i++) {
                var row=entry(i);bytes+=row.bytes().length;
                capacity(bytes<=IMAGE,"application reconstruction input bound");entries.add(row);
            }
            return new Replay(baseSnapshot,entries,provenThrough(),applicationSequence);
        } catch(IOException error) {failed=true;throw failure(STORAGE_FAILURE,"cannot read proven reconstruction input",error);}
    }
    synchronized Record provenSnapshot(byte[] application) {
        usable();
        try {return snapshot(application);}
        catch(IOException error) {failed=true;throw failure(STORAGE_FAILURE,"cannot read proven snapshot",error);}
    }
    synchronized byte[] acceptedEntry(int index) {
        usable(); need(index > baseIndex && index <= acceptedThrough(), "accepted index");
        try { return entry(index).bytes(); }
        catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "cannot read retained acceptance", error); }
    }
    synchronized List<String> authorityDigests() {
        return recoveryIo(()->{var result=new ArrayList<String>();for(int i=1;i<=acceptedThrough();i++)result.add(digestAt(i));return List.copyOf(result);});
    }
    synchronized void promise(byte[] bytes) {
        usable(); Record row = decode(bytes, "PROMISE"); bytes = row.bytes(); context(row, manifest);
        long epoch = number(row.value(), "epoch"), current = number(promise.value(), "epoch");
        if (epoch < current) throw failure(STALE_EPOCH, "lower promise", null);
        if (epoch == current) { need(Arrays.equals(bytes, promise.bytes()), "changed same-epoch promise"); force(promises, null, "PROMISE"); return; }
        capacity(grants.size() < MAX_PROMISES, "promise count exhausted");
        force(promises, bytes, "PROMISE"); grants.put(epoch, row); promise = row;
    }
    synchronized String accept(byte[] bytes) {
        usable(); Record row = decode(bytes, "ACCEPT"); bytes = row.bytes(); context(row, manifest); active(row);
        AutomaticRecovery.basisCapacity(manifest,node,row);
        var entry = decode(unbase(row.value().get("entry")), "ENTRY"); long index = number(entry.value(), "index");
        capacity(index <= MAX_ENTRIES && bytes.length <= bounds.maxFrameBytes(), "acceptance bounds");
        need(index == provenThrough() + 1L || index > baseIndex && index <= provenThrough(), "acceptance gap");
        if (selected != null && selected.record().value().get("ballot").equals(AutomaticRecovery.ballotOf(row))
                && index == number(selected.record().value(), "prefixIndex") + 1) need(selectedValue(row, entry), "accept differs from durable selection");
        boolean retry = false;
        try {
            predecessor(entry);
            if (index <= acceptedThrough()) {
                var previous = acceptance((int) index);
                retry = Arrays.equals(bytes, previous.bytes());
                need(retry || index == provenThrough() + 1L && index == acceptedThrough()
                        && number(row.value(), "epoch") > number(previous.value(), "epoch")
                        && (Arrays.equals(entry.bytes(), unbase(previous.value().get("entry"))) || selectedValue(row, entry)), "conflicting accepted value; selection recovery required");
            } else predecessor(entry);
        } catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "acceptance authority read failed", error); }
        if (!retry) capacity(acceptanceRows < (long) MAX_ENTRIES + MAX_PROMISES, "acceptance rows exhausted");
        recoveryIo(()->{recovery.ensureStarted();return null;});
        long offset = force(acceptances, retry ? null : bytes, "ACCEPT");
        if (!retry) {
            if (index > acceptedThrough()) accepted.add(new ArrayList<>());
            accepted.get((int) index - baseIndex - 1).add(ref(offset, row, entry.digest())); acceptanceRows++;
        }
        return receipt("ACCEPT_ACK", manifest.digest(), node, row.value(), index, entry.digest());
    }
    synchronized String prove(byte[] bytes) {
        usable(); Record row = decode(bytes, "PROOF"); bytes = row.bytes(); context(row, manifest); active(row);
        long index = number(row.value(), "index"); need(index > baseIndex && index <= acceptedThrough() && index <= provenThrough() + 1L, "proof gap");
        boolean retry = index <= provenThrough(); Record entry;
        try {
            if (retry) need(Arrays.equals(bytes, read(proofs, proven.get((int) index - baseIndex - 1).offset, "PROOF").bytes()), "changed proven certificate");
            matchingAcceptance(row); entry = entry((int) index);
        } catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "proof authority read failed", error); }
        if (!retry && number(entry.value(), "operation") <= 8) capacity(applicationSequence < Long.MAX_VALUE, "application sequence exhausted");
        recoveryIo(()->{recovery.ensureStarted();return null;});
        long offset = force(proofs, retry ? null : bytes, "PROOF");
        if (!retry) { proven.add(ref(offset, row, text(row.value(), "entryDigest"))); advanceSequence(entry); }
        return receipt("PROOF_ACK", manifest.digest(), node, row.value(), index, sha(bytes));
    }
    private long force(FileChannel channel, byte[] bytes, String name) {
        if (bytes != null) capacity(bytes.length <= bounds.maxRetainedLogBytes() - retainedBytes && bytes.length <= bounds.maxFrameBytes(), "retained authority capacity");
        try {
            if(bytes != null && channel != promises && Files.exists(directory.resolve("current.gsr")))
                capacity(bytes.length <= IMAGE - channel.size(), "complete generation source journal capacity");
        } catch(IOException error) {failed=true;throw failure(STORAGE_FAILURE,"cannot size generation journal",error);}
        try {
            long offset = channel.size();
            if (bytes != null) {
                faults.at(name + "_BEFORE_WRITE"); channel.position(offset);
                int limit = faults.maximumWriteBytes(); need(limit > 0, "write chunk bound");
                var remaining = ByteBuffer.wrap(bytes); int stalls = 0;
                while (remaining.hasRemaining()) {
                    int end = Math.min(bytes.length, remaining.position() + Math.min(limit, bytes.length - remaining.position()));
                    remaining.limit(end); int wrote = channel.write(remaining); remaining.limit(bytes.length);
                    if (wrote == 0 && ++stalls > 16) throw new IOException("authority write made no progress");
                    faults.at(name + "_WRITE_CHUNK");
                }
                faults.at(name + "_AFTER_WRITE");
            }
            channel.force(true); faults.at(name + "_AFTER_FORCE");
            faults.at(name + "_BEFORE_ACK");
            if (bytes != null) retainedBytes += bytes.length;
            return offset;
        } catch (IOException | RuntimeException error) {
            failed = true; throw failure(STORAGE_FAILURE, "ambiguous " + name + " I/O; voter quarantined", error);
        }
    }
    @Override public synchronized void close() {
        if (closed) return; closed = true; IOException failure = null;
        for (FileChannel channel : List.of(promises, acceptances, proofs, lockChannel)) {
            try { channel.close(); } catch (IOException error) { if (failure == null) failure = error; else failure.addSuppressed(error); }
        }
        if (failure != null) throw failure(STORAGE_FAILURE, "automatic authority close failed", failure);
    }
}
