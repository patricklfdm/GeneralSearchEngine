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

/** Local automatic authority. No transport, application publication or directory creation. */
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
    private final FileChannel lockChannel, promises, acceptances, proofs;
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
            FileChannel promises = channel(root.resolve("promises.gsr")); channels.add(promises);
            FileChannel accepts = channel(root.resolve("accepted.gsr")); channels.add(accepts);
            FileChannel proofs = channel(root.resolve("proofs.gsr")); channels.add(proofs);
            var store = new AutomaticStore(root, node, manifest, bounds, faults, owner, lock, promises, accepts, proofs);
            for (String name : AutomaticAdmission.ROOT_FILES) {
                long size = Files.size(root.resolve(name)); capacity(size <= bounds.maxRetainedLogBytes() - store.retainedBytes, "retained authority bytes");
                store.retainedBytes += size;
            }
            store.load(); success = true; return store;
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
            need(index == accepted.size() || index == accepted.size() + 1L, "acceptance slot order");
            if (index == accepted.size()) {
                var previous = latest((int) index);
                need(previous.epoch < number(row.value(), "epoch") && previous.entryDigest.equals(entry.digest()), "changed accepted value/ballot retry");
            } else {
                predecessor(entry); accepted.add(new ArrayList<>());
            }
            accepted.get((int) index - 1).add(ref(offset, row, entry.digest())); offset += row.bytes().length;
        }
        offset = header(proofs, 6);
        while (offset < proofs.size()) {
            Record row = read(proofs, offset, "PROOF"); context(row, manifest);
            long index = number(row.value(), "index"); need(index == proven.size() + 1L && index <= accepted.size(), "proof prefix/order");
            matchingAcceptance(row); advanceSequence(entry((int) index));
            proven.add(ref(offset, row, text(row.value(), "entryDigest"))); offset += row.bytes().length;
        }
        need(accepted.size() <= proven.size() + 1L, "more than one unresolved accepted slot");
    }
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
    private Ref latest(int index) { var rows = accepted.get(index - 1); return rows.get(rows.size() - 1); }
    private Record acceptance(int index) throws IOException { return read(acceptances, latest(index).offset, "ACCEPT"); }
    private Record entry(int index) throws IOException { return decode(unbase(acceptance(index).value().get("entry")), "ENTRY"); }
    private void predecessor(Record entry) throws IOException {
        int index = Math.toIntExact(number(entry.value(), "index"));
        Record previous = index == 1 ? null : entry(index - 1);
        need(entry.value().get("previousDigest").equals(previous == null ? manifest.digest() : previous.digest())
                && number(entry.value(), "previousEpoch") == (previous == null ? 1 : number(previous.value(), "originEpoch")), "entry prefix mismatch");
    }
    private static boolean sameBallot(Record a, Record b) {
        return List.of("epoch", "proposer", "incarnation").stream().allMatch(k -> java.util.Objects.equals(a.value().get(k), b.value().get(k)));
    }
    private void granted(Record row) {
        var grant = grants.get(number(row.value(), "epoch")); need(grant != null && sameBallot(row, grant), "acceptance without matching retained promise");
    }
    private void matchingAcceptance(Record proof) throws IOException {
        int index = Math.toIntExact(number(proof.value(), "index"));
        Ref match = accepted.get(index - 1).stream().filter(r -> r.epoch == number(proof.value(), "epoch")).findFirst().orElse(null);
        need(match != null && match.entryDigest.equals(proof.value().get("entryDigest")), "proof lacks matching local acceptance");
        var row = read(acceptances, match.offset, "ACCEPT"); need(sameBallot(row, proof), "proof ballot mismatch");
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
                "acceptedThrough", accepted.size(), "provenThrough", proven.size(), "applicationSequence", applicationSequence,
                "retainedBytes", retainedBytes, "node", node, "manifestDigest", manifest.digest());
    }
    synchronized byte[] acceptedEntry(int index) {
        usable(); need(index > 0 && index <= accepted.size(), "accepted index");
        try { return entry(index).bytes(); }
        catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "cannot read retained acceptance", error); }
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
        var entry = decode(unbase(row.value().get("entry")), "ENTRY"); long index = number(entry.value(), "index");
        capacity(index <= MAX_ENTRIES && bytes.length <= bounds.maxFrameBytes(), "acceptance bounds");
        need(index == proven.size() + 1L || index > 0 && index <= proven.size(), "acceptance gap");
        boolean retry = false;
        try {
            if (index <= accepted.size()) {
                var previous = acceptance((int) index);
                retry = Arrays.equals(bytes, previous.bytes());
                need(retry || index == proven.size() + 1L && index == accepted.size()
                        && number(row.value(), "epoch") > number(previous.value(), "epoch")
                        && Arrays.equals(entry.bytes(), unbase(previous.value().get("entry"))), "conflicting accepted value; selection recovery required");
            } else predecessor(entry);
        } catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "acceptance authority read failed", error); }
        if (!retry) capacity(acceptanceRows < (long) MAX_ENTRIES + MAX_PROMISES, "acceptance rows exhausted");
        long offset = force(acceptances, retry ? null : bytes, "ACCEPT");
        if (!retry) {
            if (index > accepted.size()) accepted.add(new ArrayList<>());
            accepted.get((int) index - 1).add(ref(offset, row, entry.digest())); acceptanceRows++;
        }
        return receipt("ACCEPT_ACK", manifest.digest(), node, row.value(), index, entry.digest());
    }
    synchronized String prove(byte[] bytes) {
        usable(); Record row = decode(bytes, "PROOF"); bytes = row.bytes(); context(row, manifest); active(row);
        long index = number(row.value(), "index"); need(index <= accepted.size() && index <= proven.size() + 1L, "proof gap");
        boolean retry = index <= proven.size(); Record entry;
        try {
            if (retry) need(Arrays.equals(bytes, read(proofs, proven.get((int) index - 1).offset, "PROOF").bytes()), "changed proven certificate");
            matchingAcceptance(row); entry = entry((int) index);
        } catch (IOException error) { failed = true; throw failure(STORAGE_FAILURE, "proof authority read failed", error); }
        if (!retry && number(entry.value(), "operation") <= 8) capacity(applicationSequence < Long.MAX_VALUE, "application sequence exhausted");
        long offset = force(proofs, retry ? null : bytes, "PROOF");
        if (!retry) { proven.add(ref(offset, row, text(row.value(), "entryDigest"))); advanceSequence(entry); }
        return receipt("PROOF_ACK", manifest.digest(), node, row.value(), index, sha(bytes));
    }
    private long force(FileChannel channel, byte[] bytes, String name) {
        if (bytes != null) capacity(bytes.length <= bounds.maxRetainedLogBytes() - retainedBytes && bytes.length <= bounds.maxFrameBytes(), "retained authority capacity");
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
