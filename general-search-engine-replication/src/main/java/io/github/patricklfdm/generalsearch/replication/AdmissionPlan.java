package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionConfiguration.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Complete deterministic kind-17 authority and its nested publication records. */
record AdmissionPlan(Map<String, Object> descriptor, Manifest manifest, Source source,
                     long genesisLength, List<List<Member>> payloads) {
    AdmissionPlan {
        // Canonical encode/decode freezes nested caller-owned collections and numeric representation.
        descriptor = object(ReplicaJson.decode(ReplicaJson.encode(descriptor, META), META));
        payloads = payloads.stream().map(List::copyOf).toList();
        keys(descriptor, "operation", "source", "maxSourceBytes", "maxOperationBytes", "application", "replicas");
        Path operation = path(descriptor.get("operation"));
        require((descriptor.get("source") == null) == (source.kind() == 0), INTEGRITY_FAILURE, "source path/kind mismatch");
        var paths = new ArrayList<Path>(); paths.add(operation);
        if (source.kind() != 0) paths.add(path(descriptor.get("source")));
        long sourceMaximum = number(descriptor, "maxSourceBytes", 1, 1L << 40);
        number(descriptor, "maxOperationBytes", 1, 1L << 40);
        require(source.members().stream().mapToLong(Member::size).sum() <= sourceMaximum, CAPACITY_EXCEEDED, "source bytes exceed plan");
        require(source.sequence() == manifest.base() && !source.history().equals(manifest.history()), INTEGRITY_FAILURE, "source differs from genesis history/base");
        require(genesisLength >= HEADER_BYTES && genesisLength <= IMAGE && payloads.size() == 3, CAPACITY_EXCEEDED, "invalid genesis length or inventory count");
        validateApplication(object(descriptor.get("application")), manifest);
        var locals = array(descriptor.get("replicas")); require(locals.size() == 3, INTEGRITY_FAILURE, "plan requires three local descriptors");
        Object commonIdentity = null;
        for (int i = 0; i < 3; i++) {
            var local = object(locals.get(i)); validateLocal(local, manifest);
            require(string(local, "node").equals(manifest.group().members().get(i).nodeId().value()), PROTOCOL_MISMATCH, "local order differs from manifest");
            var core = object(local.get("materialization"));
            Object identity = List.of(core.get("storageIdentity"), core.get("schemaIdentity"), core.get("codecId"), core.get("codecVersion"), core.get("format"));
            require(commonIdentity == null || commonIdentity.equals(identity), PROTOCOL_MISMATCH, "local materialization identities disagree"); commonIdentity = identity;
            paths.add(path(local.get("target"))); paths.add(path(core.get("directory")));
            var inventory = payloads.get(i);
            require(inventory.stream().map(Member::name).toList().equals(List.of("entries.gsr", "genesis.gsr", "manifest.gsr", "node.gsr", "promises.gsr", "proofs.gsr", "replica.lock", "storage-ready.gsr"))
                            && inventory.stream().allMatch(member -> member.kind() == 1), INTEGRITY_FAILURE, "invalid bootstrap payload inventory");
            require(inventory.get(1).size() == genesisLength, INTEGRITY_FAILURE, "genesis length mismatch");
            var bounds = object(local.get("replicationBounds"));
            require(genesisLength <= number(bounds, "maxSnapshotStagingBytes", 1, 1L << 40), CAPACITY_EXCEEDED, "genesis exceeds local staging bound");
        }
        for (int i = 0; i < paths.size(); i++) for (int j = 0; j < i; j++) require(!paths.get(i).startsWith(paths.get(j))
                && !paths.get(j).startsWith(paths.get(i)), INTEGRITY_FAILURE, "overlapping descriptor paths");
    }

    byte[] encode() {
        return record(17, out -> {
            out.writeShort(1); blob(out, ReplicaJson.encode(descriptor, META)); blob(out, manifest.encode());
            blob(out, source.encode()); out.writeLong(genesisLength);
            for (var inventory : payloads) inventory(out, inventory);
        });
    }
    String digest() { return frameDigest(encode()); }
    Path operation() { return path(descriptor.get("operation")); }
    Path sourcePath() { return source.kind() == 0 ? null : path(descriptor.get("source")); }
    Map<String, Object> local(int index) { return object(array(descriptor.get("replicas")).get(index)); }
    Path target(int index) { return path(local(index).get("target")); }
    long maximum() { return number(descriptor, "maxOperationBytes", 1, 1L << 40); }

    ReplicationBootstrapPlan summary() {
        return new ReplicationBootstrapPlan(manifest.group().groupId(), manifest.group().configurationId(),
                source.kind() == 0 ? ReplicationBootstrapSource.EMPTY : ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                sourcePath(), java.util.stream.IntStream.range(0, 3).mapToObj(this::target).toList(), digest());
    }

    static AdmissionPlan read(byte[] bytes) throws IOException {
        var in = decode(bytes, 17, META);
        require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported plan projection");
        var descriptor = object(ReplicaJson.decode(blob(in, META), META));
        var manifest = Manifest.read(blob(in, META)); var source = Source.decode(blob(in, META)); long length = in.readLong();
        var inventories = new ArrayList<List<Member>>(); for (int i = 0; i < 3; i++) inventories.add(inventory(in)); end(in);
        var plan = new AdmissionPlan(descriptor, manifest, source, length, inventories);
        require(Arrays.equals(bytes, plan.encode()), INTEGRITY_FAILURE, "noncanonical plan"); plan.checkBudget();
        return plan;
    }

    byte[] preparation(int i) {
        return record(18, out -> { hash(out, digest()); hash(out, manifest.digest());
            text(out, manifest.group().members().get(i).nodeId().value()); hash(out, inventoryDigest(payloads.get(i))); });
    }
    byte[] receipt() {
        return record(19, out -> { blob(out, encode()); out.writeInt(3); for (int i = 0; i < 3; i++) blob(out, preparation(i)); });
    }
    byte[] seal(int i) {
        return record(20, out -> { text(out, manifest.group().members().get(i).nodeId().value()); blob(out, receipt()); });
    }
    ReplicationBootstrapResult result() {
        return new ReplicationBootstrapResult(operation(), summary(), manifest.digest(), manifest.genesisDigest(),
                manifest.history(), manifest.base(), frameDigest(receipt()));
    }
    static AdmissionPlan receipt(byte[] bytes) throws IOException {
        var in = decode(bytes, 19, META); var plan = read(blob(in, META));
        require(in.readInt() == 3, INTEGRITY_FAILURE, "receipt requires all three preparations");
        for (int i = 0; i < 3; i++) require(Arrays.equals(blob(in, META), plan.preparation(i)), INTEGRITY_FAILURE, "receipt preparation mismatch");
        end(in); return plan;
    }

    byte[] row(int phase, long sequence, String previous) {
        return record(21, out -> {
            hash(out, digest()); out.writeLong(sequence); hash(out, previous); out.writeByte(phase);
            for (int i = 0; i < 3; i++) hash(out, phase == 1 ? ZERO : frameDigest(preparation(i)));
            hash(out, phase == 4 ? frameDigest(receipt()) : ZERO);
        });
    }

    void checkBudget() {
        long total = encode().length;
        String previous = ZERO;
        for (int phase = 1; phase <= 4; phase++) { var row = row(phase, phase, previous); total = Math.addExact(total, row.length); previous = frameDigest(row); }
        total = Math.addExact(total, 2L * receipt().length); // pending and published decision, conservatively simultaneous
        long largestSeal = 0;
        for (int i = 0; i < 3; i++) {
            long bytes = payloads.get(i).stream().mapToLong(Member::size).reduce(0, Math::addExact);
            bytes = Math.addExact(bytes, preparation(i).length + (long) seal(i).length);
            var bounds = object(local(i).get("replicationBounds"));
            require(Math.addExact(bytes, seal(i).length) <= number(bounds, "maxRetainedLogBytes", 1, 1L << 40),
                    CAPACITY_EXCEEDED, "bootstrap exceeds local retained bound");
            require(seal(i).length <= number(bounds, "maxSnapshotStagingBytes", 1, 1L << 40), CAPACITY_EXCEEDED, "seal exceeds local staging bound");
            total = Math.addExact(total, bytes); largestSeal = Math.max(largestSeal, seal(i).length);
        }
        require(Math.addExact(total, largestSeal) <= maximum(), CAPACITY_EXCEEDED, "bootstrap exceeds aggregate operation bound");
    }

    private static void validateApplication(Map<String, Object> app, Manifest manifest) {
        keys(app, "documentType", "idField", "fields", "textFields", "indexes", "snapshot", "planner");
        string(app, "documentType"); var fields = new HashSet<String>(); String previous = null;
        for (Object value : array(app.get("fields"))) {
            var field = object(value); keys(field, "name", "type"); String name = string(field, "name"); string(field, "type");
            require((previous == null || previous.compareTo(name) < 0) && fields.add(name), INTEGRITY_FAILURE, "unsorted schema fields"); previous = name;
        }
        require(fields.contains(string(app, "idField")), INTEGRITY_FAILURE, "missing ID field"); previous = null;
        for (Object value : array(app.get("textFields"))) {
            var text = object(value); keys(text, "field", "analyzer"); String name = string(text, "field");
            require(fields.contains(name) && (previous == null || previous.compareTo(name) < 0)
                    && string(text, "analyzer").equals("gse-simple-v1"), INTEGRITY_FAILURE, "invalid text field"); previous = name;
        }
        var descriptions = new ArrayList<String>(); var indexFields = new HashSet<String>();
        for (Object value : array(app.get("indexes"))) {
            require(value instanceof String && ((String) value).getBytes(StandardCharsets.UTF_8).length <= 8192, INTEGRITY_FAILURE, "invalid index descriptor");
            String description = (String) value;
            var index = object(ReplicaJson.decode(description.getBytes(StandardCharsets.US_ASCII), 8192)); keys(index, "analyzer", "field", "kind");
            String field = string(index, "field"), kind = string(index, "kind");
            require(fields.contains(field) && indexFields.add(field) && Set.of("equality", "range", "prefix", "text").contains(kind)
                            && (kind.equals("text") ? "gse-simple-v1" : "").equals(index.get("analyzer")), INTEGRITY_FAILURE, "invalid genesis index");
            descriptions.add(description);
        }
        require(descriptions.size() <= 10_000 && sha256(ReplicaJson.encode(descriptions.stream().sorted().toList(), META))
                .equals(manifest.group().indexConfigurationDigest()), INTEGRITY_FAILURE, "genesis index identity mismatch");
        var snapshot = object(app.get("snapshot")); keys(snapshot, "queueCapacity", "maxBatchSize", "maxBatchWaitSeconds", "maxBatchWaitNanos");
        number(snapshot, "queueCapacity", 1, Integer.MAX_VALUE); number(snapshot, "maxBatchSize", 1, Integer.MAX_VALUE);
        number(snapshot, "maxBatchWaitSeconds", 0, Long.MAX_VALUE); number(snapshot, "maxBatchWaitNanos", 0, 999_999_999);
        require(Set.of("COST_AWARE", "FORCE_INDEX", "FORCE_SCAN").contains(string(app, "planner")), INTEGRITY_FAILURE, "unknown planner");
    }
}
