package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionConfiguration.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Codec-free closed 1.1 authority inspection, including retained recovery ancestry. */
final class AdmissionNode {
    record View(AdmissionPlan plan, ReplicationNodeId node, boolean replacement, byte[] genesis, List<Member> inventory) { }
    record Chain(List<ReplicaSnapshot.Anchor> anchors, long committed) {
        String digest(Manifest manifest, long index) { return index == 0 ? manifest.digest() : anchors.get(Math.toIntExact(index - 1)).digest(); }
    }
    private AdmissionNode() { }

    static View read(Path directory, long maximum) throws IOException {
        var inventory = AdmissionPaths.inventory(directory, maximum);
        byte[] manifestBytes = AdmissionPaths.read(directory.resolve("manifest.gsr"), META); var manifest = Manifest.read(manifestBytes);
        byte[] genesisBytes = AdmissionPaths.read(directory.resolve("genesis.gsr"), IMAGE); var genesis = Genesis.read(genesisBytes, manifest);
        var identity = decode(AdmissionPaths.read(directory.resolve("node.gsr"), META), 2, META);
        require(hash(identity).equals(manifest.digest()), INTEGRITY_FAILURE, "local manifest mismatch");
        var node = new ReplicationNodeId(text(identity, 64)); int origin = identity.readUnsignedByte(); end(identity);
        require(origin <= 1 && manifest.group().contains(node), INTEGRITY_FAILURE, "invalid node origin or membership");
        var seal = decode(AdmissionPaths.read(directory.resolve("bootstrap-seal.gsr"), META), 20, META);
        require(text(seal, 64).equals(node.value()), INTEGRITY_FAILURE, "local completion seal belongs to another node");
        var plan = AdmissionPlan.receipt(blob(seal, META)); end(seal);
        require(Arrays.equals(plan.manifest().encode(), manifestBytes) && Arrays.equals(plan.source().encode(), genesis.source().encode())
                        && plan.genesisLength() == genesisBytes.length, INTEGRITY_FAILURE, "completion receipt differs from local genesis");
        int localIndex = -1; for (int i = 0; i < 3; i++) if (manifest.group().members().get(i).nodeId().equals(node)) localIndex = i;
        AdmissionPaths.exact(directory.resolve("bootstrap-prepared.gsr"), plan.preparation(localIndex));
        var initial = payloads(manifest, genesisBytes, node, origin == 1);
        for (String file : List.of("node.gsr", "storage-ready.gsr")) AdmissionPaths.exact(directory.resolve(file), initial.get(file));
        require(Files.size(directory.resolve("replica.lock")) == 0, INTEGRITY_FAILURE, "nonempty replica lock");
        if (origin == 1) AdmissionPaths.exact(directory.resolve("rebuilding.gsr"), initial.get("rebuilding.gsr"));
        Set<String> root = new java.util.HashSet<>(initial.keySet()); root.addAll(List.of("bootstrap-prepared.gsr", "bootstrap-seal.gsr",
                "current.gsr", "generation-started.gsr", "recovery-floor.gsr", "generation-a", "generation-b"));
        for (var member : inventory) {
            String[] parts = member.name().split("/");
            require(root.contains(parts[0]) && (parts.length == 1 || parts.length == 2
                            && ReplicaGeneration.SLOTS.contains(parts[0]) && ReplicaGeneration.MEMBERS.contains(parts[1])),
                    INTEGRITY_FAILURE, "closed source has unknown or incomplete operation members");
        }
        var promises = records(directory.resolve("promises.gsr"), 4, manifest, node, META);
        require(!promises.isEmpty() && promises.size() <= MAX_PROMISES, INTEGRITY_FAILURE, "initial promise missing");
        var epochs = new HashMap<Long, UUID>(); long lastEpoch = 0;
        for (byte[] record : promises) {
            var in = decode(record, 4, META);
            require(hash(in).equals(manifest.digest()) && text(in, 64).equals(manifest.group().leader().value()), INTEGRITY_FAILURE, "promise identity mismatch");
            long epoch = in.readLong(); UUID incarnation = uuid(in); end(in);
            require(epoch > lastEpoch && (epoch == 1 ? incarnation.equals(NO_INCARNATION) : epoch >= 2 && !incarnation.equals(NO_INCARNATION)),
                    INTEGRITY_FAILURE, "conflicting promise ledger"); epochs.put(epoch, incarnation); lastEpoch = epoch;
        }
        require(epochs.containsKey(1L), INTEGRITY_FAILURE, "genesis promise missing");
        Chain chain = chain(directory, manifest, node, new Chain(List.of(), 0), epochs);
        Map<String, Chain> generations = new HashMap<>();
        for (String slot : ReplicaGeneration.SLOTS) if (Files.exists(directory.resolve(slot), LinkOption.NOFOLLOW_LINKS)) {
            Path path = directory.resolve(slot);
            var members = AdmissionPaths.inventory(path, maximum);
            require(members.stream().allMatch(m -> m.kind() == 1) && members.stream().map(Member::name).collect(java.util.stream.Collectors.toSet()).equals(ReplicaGeneration.MEMBERS),
                    INTEGRITY_FAILURE, "incomplete retained generation");
            byte[] snapshot = AdmissionPaths.read(path.resolve("snapshot.gsr"), IMAGE);
            var generationSeal = decode(AdmissionPaths.read(path.resolve("generation.gsr"), META), 11, META);
            require(hash(generationSeal).equals(manifest.digest()) && text(generationSeal, 64).equals(node.value()), INTEGRITY_FAILURE, "generation identity mismatch");
            require(!uuid(generationSeal).equals(NO_INCARNATION) && hash(generationSeal).equals(frameDigest(snapshot)), INTEGRITY_FAILURE, "generation snapshot mismatch");
            for (String journal : List.of("entries.gsr", "proofs.gsr")) {
                byte[] bytes = AdmissionPaths.read(path.resolve(journal), (int) Math.min(Integer.MAX_VALUE - 8L, maximum));
                require(bytes.length >= HEADER_BYTES && hash(generationSeal).equals(frameDigest(bytes)), INTEGRITY_FAILURE, "generation journal header mismatch");
            }
            end(generationSeal);
            var recovered = chain(path, manifest, node, snapshot(snapshot, manifest, genesis.application()), epochs);
            for (var anchor : recovered.anchors()) require(anchor.epoch() <= lastEpoch
                            && (anchor.incarnation().equals(epochs.get(anchor.epoch())) || !epochs.containsKey(anchor.epoch()) && anchor.epoch() < lastEpoch),
                    INTEGRITY_FAILURE, "recovery ancestry is newer than its durable promise");
            agree(chain, recovered); generations.put(slot, recovered);
        }
        Path selected = directory.resolve("current.gsr");
        if (Files.exists(selected, LinkOption.NOFOLLOW_LINKS)) {
            var in = decode(AdmissionPaths.read(selected, META), 10, META);
            require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()), INTEGRITY_FAILURE, "generation pointer identity mismatch");
            String slot = text(in, 32); UUID generation = uuid(in); String digest = hash(in); int admitted = in.readUnsignedByte(); end(in);
            require(generations.containsKey(slot) && admitted <= 1, INTEGRITY_FAILURE, "generation pointer target missing");
            byte[] bytes = AdmissionPaths.read(directory.resolve(slot).resolve("generation.gsr"), META);
            var generationSeal = decode(bytes, 11, META); hash(generationSeal); text(generationSeal, 64);
            require(frameDigest(bytes).equals(digest) && uuid(generationSeal).equals(generation), INTEGRITY_FAILURE, "generation pointer seal mismatch");
            chain = generations.get(slot);
        } else require(!Files.exists(directory.resolve("generation-started.gsr"), LinkOption.NOFOLLOW_LINKS)
                        && !Files.exists(directory.resolve("recovery-floor.gsr"), LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "installed generation selector lost");
        if (Files.exists(directory.resolve("generation-started.gsr"), LinkOption.NOFOLLOW_LINKS)) {
            var in = decode(AdmissionPaths.read(directory.resolve("generation-started.gsr"), META), 15, META);
            require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()), INTEGRITY_FAILURE, "started marker mismatch"); end(in);
        }
        if (Files.exists(directory.resolve("recovery-floor.gsr"), LinkOption.NOFOLLOW_LINKS)) {
            var in = decode(AdmissionPaths.read(directory.resolve("recovery-floor.gsr"), META), 12, META);
            require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()), INTEGRITY_FAILURE, "recovery floor identity mismatch");
            long floor = in.readLong(); String digest = hash(in); int count = in.readInt();
            require(floor >= 0 && floor <= chain.committed() && digest.equals(chain.digest(manifest, floor)) && count >= 2 && count <= 3,
                    INTEGRITY_FAILURE, "invalid recovery floor");
            String previous = null;
            for (int i = 0; i < count; i++) { String voter = text(in, 64); require(manifest.group().contains(new ReplicationNodeId(voter))
                    && (previous == null || previous.compareTo(voter) < 0), INTEGRITY_FAILURE, "invalid floor voters"); previous = voter; } end(in);
        }
        return new View(plan, node, origin == 1, genesisBytes, inventory);
    }

    private static void agree(Chain a, Chain b) {
        int common = (int) Math.min(a.committed(), b.committed());
        for (int i = 0; i < common; i++) require(a.anchors().get(i).equals(b.anchors().get(i)), CONFLICTING_HISTORY, "conflicting proven recovery sources");
    }

    private static List<byte[]> records(Path path, int kind, Manifest manifest, ReplicationNodeId node, int maximum) throws IOException {
        AdmissionPaths.regular(path);
        var rows = new ArrayList<byte[]>();
        try (var channel = java.nio.channels.FileChannel.open(path, java.nio.file.StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            long offset = 0;
            while (offset < channel.size()) {
                require(rows.size() <= MAX_ENTRIES, CAPACITY_EXCEEDED, "journal record count exceeds bound");
                var header = ByteBuffer.allocate(HEADER_BYTES);
                while (header.hasRemaining()) require(channel.read(header) > 0, INTEGRITY_FAILURE, "incomplete journal header");
                int size = ByteBuffer.wrap(header.array(), 12, 4).getInt();
                require(size > 0 && size <= maximum - HEADER_BYTES && size <= channel.size() - offset - HEADER_BYTES,
                        INTEGRITY_FAILURE, "invalid journal record length");
                var payload = ByteBuffer.allocate(size);
                while (payload.hasRemaining()) require(channel.read(payload) > 0, INTEGRITY_FAILURE, "incomplete journal body");
                byte[] bytes = join(header.array(), payload.array());
                var in = decode(bytes, offset == 0 ? 3 : kind, maximum);
                if (offset == 0) { require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()) && in.readUnsignedShort() == kind,
                        INTEGRITY_FAILURE, "journal header identity mismatch"); end(in); }
                else rows.add(bytes);
                offset = channel.position();
            }
            require(offset > 0, INTEGRITY_FAILURE, "missing journal header");
        }
        return rows;
    }

    private static Chain chain(Path directory, Manifest manifest, ReplicationNodeId node, Chain base, Map<Long, UUID> epochs) throws IOException {
        var anchors = new ArrayList<>(base.anchors());
        for (byte[] bytes : records(directory.resolve("entries.gsr"), 5, manifest, node, IMAGE)) {
            var in = decode(bytes, 5, IMAGE); var entry = ReplicaEntry.decode(in.readAllBytes());
            long lastEpoch = anchors.isEmpty() ? 1 : anchors.getLast().epoch();
            String previous = anchors.isEmpty() ? manifest.digest() : anchors.getLast().digest();
            require(entry.manifestDigest().equals(manifest.digest()) && entry.index() == anchors.size() + 1L
                            && entry.previousDigest().equals(previous) && entry.previousEpoch() == lastEpoch
                            && entry.epoch() >= lastEpoch && entry.incarnation().equals(epochs.get(entry.epoch())),
                    INTEGRITY_FAILURE, "entry chain/promise mismatch");
            anchors.add(new ReplicaSnapshot.Anchor(entry.epoch(), entry.incarnation(), entry.operation(), frameDigest(bytes), sha256(entry.payload())));
        }
        long committed = base.committed();
        for (byte[] bytes : records(directory.resolve("proofs.gsr"), 6, manifest, node, META)) {
            var proof = ReplicaProof.decode(decode(bytes, 6, META).readAllBytes());
            require(proof.index() > committed && proof.index() <= anchors.size(), INTEGRITY_FAILURE, "proof ledger index mismatch");
            proof(manifest, proof, anchors); committed = proof.index();
        }
        return new Chain(List.copyOf(anchors), committed);
    }

    private static Chain snapshot(byte[] bytes, Manifest manifest, byte[] genesis) throws IOException {
        var in = decode(bytes, 8, IMAGE);
        require(hash(in).equals(manifest.digest()) && in.readLong() == manifest.base(), INTEGRITY_FAILURE, "snapshot base/manifest mismatch");
        long claimed = in.readLong(); int count = in.readInt();
        require(count >= 0 && count <= MAX_ENTRIES && count <= in.available() / 89, CAPACITY_EXCEEDED, "invalid ancestry count");
        var anchors = new ArrayList<ReplicaSnapshot.Anchor>(); long sequence = manifest.base(), epoch = 1; UUID incarnation = NO_INCARNATION;
        for (int i = 0; i < count; i++) {
            long nextEpoch = in.readLong(); UUID nextIncarnation = uuid(in); int operation = in.readUnsignedByte();
            require(operation >= 1 && operation <= 10 && nextEpoch >= epoch && (nextEpoch > epoch || nextIncarnation.equals(incarnation)), INTEGRITY_FAILURE, "invalid snapshot epoch/operation");
            anchors.add(new ReplicaSnapshot.Anchor(nextEpoch, nextIncarnation, ReplicaEntry.OPERATIONS.get(operation - 1), hash(in), hash(in)));
            if (operation <= 8) sequence = Math.addExact(sequence, 1); epoch = nextEpoch; incarnation = nextIncarnation;
        }
        byte[] proof = blob(in, META), application = blob(in, IMAGE); end(in);
        validateApplication(application, false);
        require(sequence == claimed && (count == 0 ? proof.length == 0 && Arrays.equals(application, genesis) : proof.length > 0), INTEGRITY_FAILURE, "snapshot sequence/application mismatch");
        if (count > 0) { var terminal = ReplicaProof.decode(decode(proof, 6, META).readAllBytes());
            require(terminal.index() == count, INTEGRITY_FAILURE, "snapshot lacks terminal proof"); proof(manifest, terminal, anchors); }
        return new Chain(List.copyOf(anchors), count);
    }

    private static void proof(Manifest manifest, ReplicaProof proof, List<ReplicaSnapshot.Anchor> anchors) {
        var anchor = anchors.get(Math.toIntExact(proof.index() - 1));
        require(proof.manifestDigest().equals(manifest.digest()) && proof.epoch() == anchor.epoch() && proof.incarnation().equals(anchor.incarnation())
                        && proof.entryDigest().equals(anchor.digest()) && proof.previousDigest().equals(proof.index() == 1 ? manifest.digest() : anchors.get(Math.toIntExact(proof.index() - 2)).digest()),
                CONFLICTING_HISTORY, "proof disagrees with ancestry");
        for (var receipt : proof.receipts()) {
            String expected = sha256(body(out -> { text(out, "gse-replication/1.1/DURABLE_ACK"); hash(out, manifest.digest()); text(out, receipt.voter().value());
                out.writeLong(anchor.epoch()); uuid(out, anchor.incarnation()); out.writeLong(proof.index()); hash(out, anchor.digest()); }));
            require(manifest.group().contains(receipt.voter()) && receipt.digest().equals(expected), INTEGRITY_FAILURE, "invalid 1.1 voter receipt");
        }
    }
}
