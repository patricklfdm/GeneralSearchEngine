package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionJson.require;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

/** Independent test-only 1.1 byte oracle. No replication implementation imports. */
final class AdmissionOracle {
    static final int META = 65536, IMAGE = 64 * 1024 * 1024;
    static final long LIMIT = 1L << 40;
    static final byte[] ZERO = new byte[32];
    static final List<String> NAMES = List.of("entries.gsr", "genesis.gsr", "manifest.gsr", "node.gsr", "promises.gsr", "proofs.gsr", "replica.lock", "storage-ready.gsr");
    static final List<String> TYPES = List.of("HANDSHAKE", "ACTIVATION_PROMISE", "APPEND", "DURABLE_ACK", "COMMIT_PROOF", "COMMIT_PROOF_ACK", "COMMIT_ADVANCE", "CONFLICT", "AUTHORITY_STATUS_PROBE", "SNAPSHOT_OFFER", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL", "ACTIVATE_EPOCH", "AUTHORITY_STATUS", "SNAPSHOT_ABORT", "REJECT");
    record Item(String name, int kind, long size, byte[] digest) { }
    record Source(int kind, byte[] history, long sequence, List<Item> inventory) { }
    record Application(List<String> indexes, List<String> keys) { }
    record Genesis(byte[] raw, byte[] group, byte[] source, byte[] history, long base, byte[] application, Application state) { }
    record Manifest(byte[] raw, List<String> nodes, String leader, String configuration, String codec, int codecVersion, String schema) { }
    record Plan(Map<String, Object> descriptor, List<List<Item>> inventories) { }

    static byte[] sha(byte[]... values) throws Exception {
        var digest = MessageDigest.getInstance("SHA-256");
        for (byte[] value : values) digest.update(value);
        return digest.digest();
    }
    static byte[] digest(byte[] value) { return Arrays.copyOfRange(value, 16, 48); }
    static String hex(byte[] value) { return HexFormat.of().formatHex(value); }
    static void equal(byte[] a, byte[] b, String reason) { require(Arrays.equals(a, b), reason); }
    static byte[] history(byte[] group) throws Exception {
        byte[] history = Arrays.copyOf(sha("gse-v50-application-history-v1\0".getBytes(StandardCharsets.US_ASCII), group), 16);
        require(!Arrays.equals(history, new byte[16]), "zero history"); return history;
    }
    static String uuid(byte[] value) { var b = ByteBuffer.wrap(value); return new UUID(b.getLong(), b.getLong()).toString(); }
    static byte[] text(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        return ByteBuffer.allocate(4 + bytes.length).putInt(bytes.length).put(bytes).array();
    }
    static String identity(String value, int max) {
        require(value.matches("[a-z0-9][a-z0-9._-]{0," + (max - 1) + "}"), "identity"); return value;
    }
    static byte[] file(Map<String, byte[]> files, String name) {
        require(files.containsKey(name), "missing " + name); return files.get(name);
    }
    @SuppressWarnings("unchecked")
    static Map<String, Object> object(Object value) {
        require(value instanceof Map<?, ?>, "object"); return (Map<String, Object>) value;
    }
    static List<?> list(Object value) { require(value instanceof List<?>, "array"); return (List<?>) value; }
    static long number(Object value) { require(value instanceof Long, "integer"); return (Long) value; }
    static String string(Object value) { require(value instanceof String, "string"); return (String) value; }
    static void exact(Map<String, Object> value, String names) { require(value.keySet().equals(Set.of(names.split(" "))), "descriptor fields"); }
    static Map<String, Object> json(byte[] bytes) {
        var value = object(AdmissionJson.parse(new String(bytes, StandardCharsets.UTF_8)));
        equal(bytes, AdmissionJson.canonical(value).getBytes(StandardCharsets.US_ASCII), "canonical JSON");
        jsonKeys(value); return value;
    }
    static void jsonKeys(Object value) {
        if (value instanceof Map<?, ?> map) map.forEach((k, v) -> {
            require(((String) k).matches("[A-Za-z][A-Za-z0-9_]*"), "JSON keys"); jsonKeys(v);
        });
        else if (value instanceof List<?> list) list.forEach(AdmissionOracle::jsonKeys);
    }

    static final class Reader {
        final ByteBuffer data;
        Reader(byte[] bytes) { data = ByteBuffer.wrap(bytes); }
        byte[] take(int count) {
            require(count >= 0 && count <= data.remaining(), "truncated field");
            byte[] value = new byte[count]; data.get(value); return value;
        }
        int u8() { return Byte.toUnsignedInt(take(1)[0]); }
        int u16() { return Short.toUnsignedInt(ByteBuffer.wrap(take(2)).getShort()); }
        int i32() { return ByteBuffer.wrap(take(4)).getInt(); }
        long i64() { return ByteBuffer.wrap(take(8)).getLong(); }
        byte[] blob(int maximum) { int n = i32(); require(n >= 0 && n <= maximum, "blob bound"); return take(n); }
        String text(int maximum) throws Exception {
            byte[] bytes = blob(maximum); require(bytes.length > 0, "empty text");
            return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
        }
        int count(int maximum, int minimum) { int n = i32(); require(n >= 0 && n <= maximum && n <= data.remaining() / minimum, "count bound"); return n; }
        void end() { require(data.remaining() == 0, "trailing fields"); }
    }
    static Reader record(byte[] raw, int kind, int maximum, int magic) throws Exception {
        require(raw.length > 48 && raw.length <= maximum, "frame size");
        var in = ByteBuffer.wrap(raw);
        require(in.getInt() == magic && in.getShort() == 1 && in.getShort() == 1, "version");
        require(Short.toUnsignedInt(in.getShort()) == kind && in.getShort() == 0, "kind/flags");
        require(in.getInt() == raw.length - 48, "frame length");
        equal(digest(raw), sha(Arrays.copyOf(raw, 16), Arrays.copyOfRange(raw, 48, raw.length)), "frame digest");
        return new Reader(Arrays.copyOfRange(raw, 48, raw.length));
    }
    static Reader record(byte[] raw, int kind, int maximum) throws Exception { return record(raw, kind, maximum, 0x47534552); }

    static List<Item> inventory(Reader r) throws Exception {
        int count = r.count(10000, 45);
        var entries = new ArrayList<Item>();
        var names = new ArrayList<String>();
        for (int i = 0; i < count; i++) {
            String name = r.text(4096); int kind = r.u8(); long size = r.i64(); byte[] digest = r.take(32);
            require(!name.startsWith("/") && !name.contains("\\") && !name.contains("\0")
                    && Arrays.stream(name.split("/", -1)).noneMatch(v -> v.isEmpty() || v.equals(".") || v.equals("..")), "inventory path");
            require((kind == 0 || kind == 1) && size >= 0 && size <= LIMIT, "inventory kind/size");
            require(kind != 0 || size == 0 && Arrays.equals(digest, ZERO), "directory inventory");
            entries.add(new Item(name, kind, size, digest)); names.add(name);
        }
        var sorted = names.stream().distinct().sorted((a, b) -> Arrays.compareUnsigned(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8))).toList();
        require(names.equals(sorted), "inventory order"); return entries;
    }
    static byte[] inventoryDigest(List<Item> items) throws Exception {
        var bytes = new ByteArrayOutputStream();
        try (var out = new DataOutputStream(bytes)) {
            out.write("gse-v50-payload-inventory-v1\0".getBytes(StandardCharsets.US_ASCII)); out.writeInt(items.size());
            for (var item : items) { out.write(text(item.name)); out.writeByte(item.kind); out.writeLong(item.size); out.write(item.digest); }
        }
        return sha(bytes.toByteArray());
    }
    static Source source(byte[] raw) throws Exception {
        var r = new Reader(raw);
        int kind = r.u8(); String family = r.text(32); int major = r.u16(), minor = r.u16(); String profile = r.text(32);
        byte[] history = r.take(16); long sequence = r.i64(); var inventory = inventory(r); r.end();
        require(kind == 0 || kind == 1, "source kind");
        if (kind == 0) require(family.equals("none") && major == 0 && minor == 0 && profile.equals("none")
                && Arrays.equals(history, new byte[16]) && sequence == 0 && inventory.isEmpty(), "empty source");
        else {
            require(family.equals("gse-backup") && major == 1 && minor <= 2, "source version");
            require(profile.equals(minor == 2 ? "canonical-only" : "full"), "source profile");
            require(!Arrays.equals(history, new byte[16]) && sequence >= 0 && sequence < Long.MAX_VALUE, "source history/sequence");
            require(inventory.stream().map(Item::name).toList().equals(List.of("gse-backup-checkpoint", "gse-backup-manifest", "gse-backup-metadata"))
                    && inventory.stream().allMatch(v -> v.kind == 1 && v.size > 0), "source inventory");
        }
        return new Source(kind, history, sequence, inventory);
    }
    static Application application(byte[] raw) throws Exception {
        var r = new Reader(raw); require(r.u16() == 1, "application version");
        var indexes = new ArrayList<String>(); var fields = new ArrayList<String>();
        int count = r.count(10000, 4);
        for (int i = 0; i < count; i++) {
            String encoded = r.text(8192); var d = json(encoded.getBytes(StandardCharsets.UTF_8));
            exact(d, "analyzer field kind"); String field = string(d.get("field")), kind = string(d.get("kind"));
            require(!field.isEmpty() && field.getBytes(StandardCharsets.UTF_8).length <= 1024, "index field");
            require(Set.of("equality", "range", "prefix", "text").contains(kind)
                    && d.get("analyzer").equals(kind.equals("text") ? "gse-simple-v1" : ""), "index kind/analyzer");
            indexes.add(encoded); fields.add(field);
        }
        require(fields.equals(new ArrayList<>(new TreeSet<>(fields))), "index order");
        count = r.count(100_000_000, 8); var keys = new ArrayList<String>();
        for (int i = 0; i < count; i++) { keys.add(hex(r.blob(IMAGE))); r.blob(IMAGE); }
        require(keys.stream().distinct().count() == keys.size(), "duplicate key"); r.end();
        return new Application(indexes, keys);
    }
    static Genesis genesis(byte[] raw) throws Exception {
        var r = record(raw, 16, IMAGE); require(r.u16() == 1, "genesis projection version");
        byte[] group = r.take(16), source = r.blob(META), history = r.take(16); long base = r.i64(); byte[] app = r.blob(IMAGE); r.end();
        require(!Arrays.equals(group, new byte[16]), "zero group");
        var src = source(source); equal(history, history(group), "application history");
        require(!Arrays.equals(history, src.history) && base >= 0 && base < Long.MAX_VALUE && base == src.sequence, "base/history");
        var state = application(app); require(src.kind != 0 || state.keys.isEmpty(), "empty genesis documents");
        return new Genesis(raw, group, source, history, base, app, state);
    }
    static Manifest manifest(byte[] raw, Genesis g) throws Exception {
        var r = record(raw, 1, META);
        require(r.text(32).equals("gse-replicated") && r.u16() == 1 && r.u16() == 1
                && r.text(32).equals("gse-replication") && r.u16() == 1 && r.u16() == 1, "manifest version");
        equal(r.take(16), g.group, "manifest group"); String configuration = identity(r.text(128), 128);
        require(r.i64() == 1, "genesis epoch"); String leader = identity(r.text(64), 64); require(r.i32() == 3, "voter count");
        var nodes = new ArrayList<String>(); var endpoints = new ArrayList<String>();
        for (int i = 0; i < 3; i++) {
            nodes.add(identity(r.text(64), 64)); String host = r.text(1012); int port = r.i32();
            require(!host.isBlank() && host.equals(host.strip()) && host.length() <= 253 && port > 0 && port <= 65535 && r.u8() == 1, "endpoint/voter");
            endpoints.add(host + ":" + port);
        }
        require(nodes.stream().distinct().count() == 3 && endpoints.stream().distinct().count() == 3 && nodes.contains(leader), "members");
        String codec = identity(r.text(128), 128); int cv = r.i32(); String schema = identity(r.text(128), 128); int sv = r.i32();
        require(cv > 0 && sv == 1, "codec/schema version");
        equal(r.take(32), sha(AdmissionJson.canonical(g.state.indexes.stream().sorted().toList()).getBytes(StandardCharsets.US_ASCII)), "index digest");
        equal(r.take(32), digest(g.raw), "manifest genesis"); equal(r.take(16), g.history, "manifest history");
        require(r.i64() == g.base, "manifest base"); r.end();
        return new Manifest(raw, nodes, leader, configuration, codec, cv, schema);
    }

    static void path(Map<String, Object> value) {
        exact(value, "path parentRealPath fileStoreName fileStoreType parentFileKey");
        for (var e : value.entrySet()) {
            String v = string(e.getValue()); require(!v.isEmpty() && v.indexOf(0) < 0 && v.getBytes(StandardCharsets.UTF_8).length <= 4096, "path binding");
            if (e.getKey().equals("path") || e.getKey().equals("parentRealPath")) require(v.startsWith("/") && (v.equals("/")
                    || Arrays.stream(v.substring(1).split("/", -1)).noneMatch(p -> p.isEmpty() || p.equals(".") || p.equals(".."))), "normalized path");
        }
    }
    static void positive(Map<String, Object> values, String keys, long... maxima) {
        exact(values, keys); String[] names = keys.split(" ");
        for (int i = 0; i < names.length; i++) { long v = number(values.get(names[i])); require(v > 0 && v <= maxima[i], "configuration bound"); }
    }
    static Plan plan(byte[] raw, Manifest m, Genesis g) throws Exception {
        var r = record(raw, 17, META); require(r.u16() == 1, "plan version");
        var d = json(r.blob(META)); equal(r.blob(META), m.raw, "plan manifest"); equal(r.blob(META), g.source, "plan source");
        require(r.i64() == g.raw.length, "plan genesis length"); exact(d, "operation source maxSourceBytes maxOperationBytes application replicas");
        path(object(d.get("operation"))); if (d.get("source") != null) path(object(d.get("source")));
        require((d.get("source") == null) == (g.source[0] == 0), "source path kind");
        require(number(d.get("maxSourceBytes")) > 0 && number(d.get("maxSourceBytes")) <= LIMIT
                && number(d.get("maxOperationBytes")) > 0 && number(d.get("maxOperationBytes")) <= LIMIT, "operation bound");
        var app = object(d.get("application")); exact(app, "documentType idField fields textFields indexes snapshot planner");
        var indexes = list(app.get("indexes"));
        require(indexes.size() == g.state.indexes.size() && new java.util.HashSet<>(indexes).equals(new java.util.HashSet<>(g.state.indexes)), "builder index configuration");
        require(!string(app.get("documentType")).isEmpty(), "document type");
        var names = new ArrayList<String>();
        require(!list(app.get("fields")).isEmpty() && list(app.get("fields")).size() <= 10000, "schema count");
        for (Object value : list(app.get("fields"))) {
            var field = object(value); exact(field, "name type");
            require(!string(field.get("name")).isEmpty() && !string(field.get("type")).isEmpty(), "schema field"); names.add(string(field.get("name")));
        }
        require(names.equals(new ArrayList<>(new TreeSet<>(names))) && names.contains(string(app.get("idField"))), "schema order/id");
        var textNames = new ArrayList<String>(); require(list(app.get("textFields")).size() <= 10000, "text fields");
        for (Object value : list(app.get("textFields"))) {
            var field = object(value); exact(field, "field analyzer");
            require(names.contains(field.get("field")) && field.get("analyzer").equals("gse-simple-v1"), "text field"); textNames.add(string(field.get("field")));
        }
        require(textNames.equals(new ArrayList<>(new TreeSet<>(textNames))), "text field order");
        var snapshot = object(app.get("snapshot")); exact(snapshot, "queueCapacity maxBatchSize maxBatchWaitSeconds maxBatchWaitNanos");
        require(number(snapshot.get("queueCapacity")) > 0 && number(snapshot.get("queueCapacity")) <= Integer.MAX_VALUE
                && number(snapshot.get("maxBatchSize")) > 0 && number(snapshot.get("maxBatchSize")) <= Integer.MAX_VALUE
                && number(snapshot.get("maxBatchWaitSeconds")) >= 0 && number(snapshot.get("maxBatchWaitNanos")) >= 0
                && number(snapshot.get("maxBatchWaitNanos")) <= 999999999, "snapshot config");
        require(Set.of("COST_AWARE", "FORCE_INDEX", "FORCE_SCAN").contains(app.get("planner")), "planner config");
        var locals = list(d.get("replicas")); require(locals.size() == 3, "configuration count");
        var paths = new ArrayList<String>(); paths.add(string(object(d.get("operation")).get("path")));
        if (d.get("source") != null) paths.add(string(object(d.get("source")).get("path")));
        var inventories = new ArrayList<List<Item>>(); Object store = null, format = null;
        for (int i = 0; i < 3; i++) {
            var local = object(locals.get(i)); exact(local, "node target materialization replicationBounds");
            require(local.get("node").equals(m.nodes.get(i)), "local configuration order"); path(object(local.get("target")));
            var mat = object(local.get("materialization")); exact(mat, "directory format storageIdentity schemaIdentity codecId codecVersion bounds");
            path(object(mat.get("directory"))); var fmt = object(mat.get("format")); exact(fmt, "family major minor");
            require(fmt.get("family").equals("gse-durable") && number(fmt.get("major")) == 1 && number(fmt.get("minor")) >= 0 && number(fmt.get("minor")) <= 2, "materialization format");
            identity(string(mat.get("storageIdentity")), 128);
            require(mat.get("schemaIdentity").equals(m.schema) && mat.get("codecId").equals(m.codec) && number(mat.get("codecVersion")) == m.codecVersion, "local application identity");
            var b = object(mat.get("bounds")); positive(b, "maxEncodedKeyBytes maxEncodedDocumentBytes maxBulkElements maxDocuments checkpointWalBytes maxRetainedBytes maxDerivedStateBytes",
                    IMAGE, 4L * IMAGE, 1000000, 100000000, LIMIT, 16 * LIMIT, 8 * LIMIT);
            require(number(b.get("maxRetainedBytes")) > number(b.get("checkpointWalBytes")), "retained bound");
            require(number(fmt.get("minor")) != 2 || number(b.get("maxDerivedStateBytes")) <= number(b.get("maxRetainedBytes")), "derived bound");
            b = object(local.get("replicationBounds")); positive(b, "maxFrameBytes maxEntriesPerAppend maxInFlightPerPeer maxPendingClientOperations maxRetryAttempts requestTimeoutMillis retryBackoffMillis snapshotChunkBytes maxRetainedLogBytes maxSnapshotStagingBytes",
                    IMAGE, 10000, 4096, 100000, 100, 300000, 60000, IMAGE, LIMIT, LIMIT);
            require(g.raw.length <= number(b.get("maxSnapshotStagingBytes")), "genesis bound");
            paths.add(string(object(local.get("target")).get("path"))); paths.add(string(object(mat.get("directory")).get("path")));
            if (i == 0) { store = mat.get("storageIdentity"); format = fmt; }
            else require(store.equals(mat.get("storageIdentity")) && format.equals(fmt), "materialization agreement");
            var inv = inventory(r); require(inv.stream().map(Item::name).toList().equals(NAMES) && inv.stream().allMatch(v -> v.kind == 1), "planned inventory"); inventories.add(inv);
        }
        r.end();
        for (int i = 0; i < paths.size(); i++) for (int j = i + 1; j < paths.size(); j++) {
            String a = paths.get(i), b = paths.get(j); require(!a.equals(b) && !a.startsWith(b.endsWith("/") ? b : b + "/")
                    && !b.startsWith(a.endsWith("/") ? a : a + "/"), "path overlap");
        }
        return new Plan(d, inventories);
    }

    static List<byte[]> receipt(byte[] raw, byte[] plan, Manifest m, Plan p) throws Exception {
        var r = record(raw, 19, META); equal(r.blob(META), plan, "receipt plan"); require(r.i32() == 3, "receipt count");
        var result = new ArrayList<byte[]>();
        for (int i = 0; i < 3; i++) {
            byte[] prepared = r.blob(META); var s = record(prepared, 18, META);
            equal(s.take(32), digest(plan), "prepared plan"); equal(s.take(32), digest(m.raw), "prepared manifest");
            require(s.text(64).equals(m.nodes.get(i)), "prepared node"); equal(s.take(32), inventoryDigest(p.inventories.get(i)), "prepared inventory");
            s.end(); result.add(prepared);
        }
        r.end(); return result;
    }
    static void journal(byte[] raw, byte[] plan, byte[] receipt, List<byte[]> preparations) throws Exception {
        int offset = 0, phase = 0; byte[] previous = ZERO;
        while (offset < raw.length) {
            require(raw.length - offset >= 48, "journal tail"); long size = 48L + ByteBuffer.wrap(raw).getInt(offset + 12);
            require(size > 48 && size <= META && size <= raw.length - offset, "journal record bound");
            byte[] frame = Arrays.copyOfRange(raw, offset, offset + (int) size); var r = record(frame, 21, META);
            equal(r.take(32), digest(plan), "journal plan"); require(r.i64() == ++phase && phase <= 4, "journal sequence");
            equal(r.take(32), previous, "journal chain"); require(r.u8() == phase, "journal phase");
            for (byte[] p : preparations) equal(r.take(32), phase == 1 ? ZERO : digest(p), "journal preparations");
            equal(r.take(32), phase == 4 ? digest(receipt) : ZERO, "journal decision"); r.end();
            previous = digest(frame); offset += (int) size;
        }
        require(phase == 4, "seal before committed decision");
    }
    static long snapshot(byte[] raw, Manifest m, Genesis g) throws Exception {
        var r = record(raw, 8, IMAGE); equal(r.take(32), digest(m.raw), "snapshot manifest"); require(r.i64() == g.base, "snapshot base");
        long sequence = r.i64(), computed = g.base, epoch = 1; byte[] incarnation = new byte[16], digest = digest(m.raw), previous = digest;
        int count = r.count(1000000, 89);
        for (int i = 0; i < count; i++) {
            long nextEpoch = r.i64(); byte[] nextIncarnation = r.take(16); int op = r.u8();
            require(nextEpoch >= Math.max(2, epoch) && !Arrays.equals(nextIncarnation, new byte[16])
                    && (nextEpoch > epoch || Arrays.equals(nextIncarnation, incarnation)) && op >= 1 && op <= 10, "snapshot ancestry");
            previous = digest; digest = r.take(32); r.take(32); epoch = nextEpoch; incarnation = nextIncarnation;
            if (op <= 8) {
                require(computed < Long.MAX_VALUE, "snapshot sequence overflow"); computed++;
            }
        }
        require(sequence == computed, "snapshot sequence"); byte[] proof = r.blob(META), app = r.blob(IMAGE); r.end();
        require((count == 0) == (proof.length == 0), "proof presence");
        if (count > 0) {
            var p = record(proof, 6, META); equal(p.take(32), digest(m.raw), "proof manifest"); require(p.i64() == epoch, "proof epoch");
            equal(p.take(16), incarnation, "proof incarnation"); require(p.i64() == count, "proof index");
            equal(p.take(32), digest, "proof entry"); equal(p.take(32), previous, "proof predecessor"); int n = p.i32(); require(n == 2 || n == 3, "proof quorum");
            var voters = new ArrayList<String>();
            for (int i = 0; i < n; i++) {
                String node = p.text(64); require(m.nodes.contains(node), "proof voter"); voters.add(node);
                byte[] expected = sha(text("gse-replication/1.1/DURABLE_ACK"), digest(m.raw), text(node), ByteBuffer.allocate(8).putLong(epoch).array(),
                        incarnation, ByteBuffer.allocate(8).putLong(count).array(), digest);
                equal(p.take(32), expected, "proof receipt");
            }
            require(voters.equals(new ArrayList<>(new TreeSet<>(voters))), "proof voter order"); p.end();
        } else equal(app, g.application, "index-zero genesis state");
        application(app); return sequence;
    }
    static Map<String, Object> wire(byte[] raw, Manifest m, Genesis g) throws Exception {
        require(raw.length >= 48, "wire header"); int kind = Short.toUnsignedInt(ByteBuffer.wrap(raw).getShort(8)); require(kind >= 1 && kind <= 16, "wire kind");
        var r = record(raw, kind, IMAGE, 0x47535250); var v = json(r.take(r.data.remaining()));
        exact(v, "protocol manifestDigest groupId configurationId sender recipient epoch incarnationId traceId eventSequence type payload");
        require(v.get("protocol").equals("gse-replication/1.1") && v.get("type").equals(TYPES.get(kind - 1)), "wire version/type");
        require(v.get("manifestDigest").equals(hex(digest(m.raw))) && v.get("groupId").equals(uuid(g.group))
                && v.get("configurationId").equals(m.configuration), "wire manifest binding");
        require(m.nodes.contains(v.get("sender")) && m.nodes.contains(v.get("recipient")) && !v.get("sender").equals(v.get("recipient")), "wire members");
        for (String name : List.of("groupId", "incarnationId", "traceId")) require(UUID.fromString(string(v.get(name))).toString().equals(v.get(name)), "wire UUID");
        require(number(v.get("epoch")) >= 0 && number(v.get("eventSequence")) >= 0 && (number(v.get("epoch")) > 0 || kind == 1 || kind == 16), "wire counters");
        var payload = object(v.get("payload"));
        require(!payload.containsKey("manifestDigest"), "wire payload identity location");
        String status = "promisedEpoch lastLogIndex commitIndex lastDigest commitDigest appliedIndex snapshotIndex recoveryFloor voter damagedTail";
        List<String> shapes = switch (kind) {
            case 1, 15 -> List.of("");
            case 2 -> List.of(status);
            case 3 -> List.of("entry");
            case 4 -> List.of("index entryDigest receiptDigest");
            case 5 -> List.of("proof");
            case 6 -> List.of("index proofDigest");
            case 7 -> List.of("action index digest", "action index digest voters", "action entries proofs", status);
            case 8, 16 -> List.of("reason");
            case 9 -> List.of("", "action", "action transferId offset length");
            case 10 -> List.of("transferId length digest", "transferId");
            case 11 -> List.of("transferId offset data", "transferId offset");
            case 12 -> List.of("transferId admit", "transferId imageDigest index digest snapshotIndex");
            case 13 -> List.of("recovery");
            case 14 -> List.of(status, "transferId length digest", "transferId offset data");
            default -> throw new IllegalArgumentException("wire kind");
        };
        require(shapes.stream().anyMatch(s -> payload.keySet().equals(s.isEmpty() ? Set.of() : Set.of(s.split(" ")))), "wire payload fields");
        for (String key : List.of("index", "offset", "length", "promisedEpoch", "lastLogIndex", "commitIndex", "appliedIndex", "snapshotIndex", "recoveryFloor"))
            if (payload.containsKey(key)) require(number(payload.get(key)) >= 0, "wire payload counter");
        for (String key : List.of("digest", "entryDigest", "receiptDigest", "proofDigest", "imageDigest", "lastDigest", "commitDigest"))
            if (payload.containsKey(key)) require(string(payload.get(key)).matches("[0-9a-f]{64}"), "wire payload digest");
        for (String key : List.of("admit", "voter", "damagedTail", "recovery"))
            if (payload.containsKey(key)) require(payload.get(key) instanceof Boolean, "wire payload boolean");
        if (payload.containsKey("transferId")) require(UUID.fromString(string(payload.get("transferId"))).toString().equals(payload.get("transferId")), "transfer UUID");
        if (kind == 13) require(Boolean.TRUE.equals(payload.get("recovery")), "activation recovery");
        if (payload.containsKey("action")) {
            var actions = kind == 7 ? Map.of("ready", "action index digest", "floor", "action index digest voters", "batch", "action entries proofs")
                    : Map.of("export", "action", "chunk", "action transferId offset length");
            require(actions.containsKey(payload.get("action")), "wire action"); exact(payload, actions.get(payload.get("action")));
        }
        for (String key : List.of("entry", "proof", "data")) if (payload.containsKey(key)) {
            byte[] decoded = java.util.Base64.getDecoder().decode(string(payload.get(key)));
            require(java.util.Base64.getEncoder().encodeToString(decoded).equals(payload.get(key)), "canonical base64");
            if (!key.equals("data")) {
                var embedded = record(decoded, key.equals("entry") ? 5 : 6, key.equals("entry") ? IMAGE : META);
                equal(embedded.take(32), digest(m.raw), "embedded manifest"); require(embedded.i64() == number(v.get("epoch")), "embedded epoch");
                require(uuid(embedded.take(16)).equals(v.get("incarnationId")), "embedded incarnation");
            }
        }
        return v;
    }

    static void initialRoot(Map<String, byte[]> files, String node, Manifest m) throws Exception {
        var n = record(file(files, node + "/node.gsr"), 2, META);
        equal(n.take(32), digest(m.raw), "node manifest"); require(n.text(64).equals(node) && n.u8() == 0, "node identity"); n.end();
        var hashes = new ArrayList<byte[]>(); hashes.add(digest(m.raw)); hashes.add(digest(file(files, node + "/node.gsr")));
        int kind = 4;
        for (String name : List.of("promises.gsr", "entries.gsr", "proofs.gsr")) {
            byte[] raw = file(files, node + "/" + name); require(raw.length >= 48, "journal header");
            long size = 48L + ByteBuffer.wrap(raw).getInt(12); require(size > 48 && size <= raw.length && size <= META, "journal header bound");
            var r = record(Arrays.copyOf(raw, (int) size), 3, META);
            equal(r.take(32), digest(m.raw), "journal manifest"); require(r.text(64).equals(node) && r.u16() == kind, "journal identity"); r.end(); hashes.add(digest(raw));
            if (kind == 4) {
                var p = record(Arrays.copyOfRange(raw, (int) size, raw.length), 4, META);
                equal(p.take(32), digest(m.raw), "promise manifest"); require(p.text(64).equals(m.leader) && p.i64() == 1, "initial promise");
                equal(p.take(16), new byte[16], "genesis incarnation"); p.end();
            } else require(size == raw.length, "initial journal tail");
            kind++;
        }
        var ready = record(file(files, node + "/storage-ready.gsr"), 7, META);
        for (byte[] hash : hashes) equal(ready.take(32), hash, "ready binding"); ready.end();
        require(file(files, node + "/replica.lock").length == 0, "lock bytes");
    }
    static void administrativeRecords(Map<String, byte[]> files, Manifest m, Genesis g, Plan p) throws Exception {
        byte[] plan = file(files, "plan.gsr"), receipt = file(files, "receipt.gsr"), operation = file(files, "operation.gsr");
        int size = 48 + ByteBuffer.wrap(operation).getInt(12);
        byte[] previous = Arrays.copyOfRange(operation, size, size * 2);
        var abort = record(file(files, "admin-aborting.gsr"), 21, META);
        equal(abort.take(32), digest(plan), "abort plan"); require(abort.i64() == 3, "abort sequence");
        equal(abort.take(32), digest(previous), "abort pre-commit tail"); require(abort.u8() == 5, "abort phase");
        equal(abort.take(96), Arrays.copyOfRange(previous, 121, 217), "abort preparations"); equal(abort.take(32), ZERO, "abort decision"); abort.end();
        var cleanup = record(file(files, "admin-cleanup.gsr"), 22, META);
        equal(cleanup.take(32), digest(plan), "cleanup plan"); equal(cleanup.take(32), digest(previous), "cleanup observed tail");
        var c = json(cleanup.blob(META)); cleanup.end(); exact(c, "operation inventory deletePaths");
        require(c.get("operation").equals(p.descriptor.get("operation")), "cleanup operation");
        var entries = list(c.get("inventory")); require(!entries.isEmpty() && entries.size() <= 10000, "cleanup inventory count");
        var names = new ArrayList<String>(); var owned = new java.util.HashSet<String>();
        for (Object value : entries) {
            var e = object(value); exact(e, "path kind size digest owner"); String name = string(e.get("path"));
            require(name.startsWith("/") && name.getBytes(StandardCharsets.UTF_8).length <= 4096 && Arrays.stream(name.substring(1).split("/", -1))
                    .noneMatch(v -> v.isEmpty() || v.equals(".") || v.equals("..")), "cleanup path");
            require(Set.of("file", "directory").contains(e.get("kind")) && number(e.get("size")) >= 0 && number(e.get("size")) <= LIMIT
                    && string(e.get("digest")).matches("[0-9a-f]{64}") && Set.of("source", hex(digest(plan))).contains(e.get("owner")), "cleanup inventory fields");
            require(!e.get("kind").equals("directory") || number(e.get("size")) == 0 && e.get("digest").equals(hex(ZERO)), "cleanup directory");
            names.add(name); if (!e.get("owner").equals("source")) owned.add(name);
        }
        require(names.equals(names.stream().distinct().sorted((a, b) -> Arrays.compareUnsigned(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8))).toList()), "cleanup inventory order");
        var delete = list(c.get("deletePaths")).stream().map(AdmissionOracle::string).toList();
        require(delete.size() == new java.util.HashSet<>(delete).size() && new java.util.HashSet<>(delete).equals(owned), "cleanup protected/incomplete deletion");
        for (int i = 0; i < delete.size(); i++) for (int j = i + 1; j < delete.size(); j++)
            require(!delete.get(j).startsWith(delete.get(i) + "/"), "cleanup dependency order");
        require(delete.getLast().equals(object(c.get("operation")).get("path")), "cleanup marker last");
        byte[] replacement = file(files, "admin-replacement-plan.gsr"); var r = record(replacement, 23, META);
        require(r.u16() == 1, "replacement version"); equal(r.blob(META), receipt, "replacement original receipt");
        var d = json(r.blob(META)); var inv = inventory(r); r.end(); exact(d, "operation source configuration manifestDigest genesisDigest sourceInventoryDigest");
        path(object(d.get("operation"))); path(object(d.get("source")));
        require(d.get("manifestDigest").equals(hex(digest(m.raw))) && d.get("genesisDigest").equals(hex(digest(g.raw)))
                && d.get("sourceInventoryDigest").equals(hex(inventoryDigest(inv))), "replacement identity/inventory");
        var local = object(d.get("configuration")); exact(local, "node target materialization replicationBounds");
        String node = string(local.get("node")); require(m.nodes.contains(node), "replacement node");
        var original = object(list(p.descriptor.get("replicas")).get(m.nodes.indexOf(node)));
        for (String key : List.of("node", "materialization", "replicationBounds")) require(local.get(key).equals(original.get(key)), "replacement configuration");
        path(object(local.get("target")));
        require(java.util.stream.Stream.of(object(d.get("operation")).get("path"), object(d.get("source")).get("path"), object(local.get("target")).get("path"))
                .distinct().count() == 3, "replacement paths");
        String source = string(object(d.get("source")).get("path")); source = source.substring(source.lastIndexOf('/') + 1) + "/";
        var expected = new ArrayList<Item>();
        for (String name : new TreeSet<>(files.keySet())) if (name.startsWith(source))
            expected.add(new Item(name.substring(source.length()), 1, files.get(name).length, sha(files.get(name))));
        equal(inventoryDigest(inv), inventoryDigest(expected), "replacement source bytes");
        var identity = record(file(files, "admin-replacement-node.gsr"), 2, META);
        equal(identity.take(32), digest(m.raw), "replacement node manifest"); require(identity.text(64).equals(node) && identity.u8() == 1, "replacement nonvoter"); identity.end();
        var rebuilding = record(file(files, "admin-rebuilding.gsr"), 13, META);
        equal(rebuilding.take(32), digest(m.raw), "rebuilding manifest"); require(rebuilding.text(64).equals(node), "rebuilding node"); rebuilding.end();
        byte[] raw = file(files, "admin-replacement-journal.gsr"), previousHash = ZERO; int offset = 0;
        for (int phase = 1; phase <= 2; phase++) {
            require(raw.length - offset >= 48, "replacement journal header"); long length = 48L + ByteBuffer.wrap(raw).getInt(offset + 12);
            require(length > 48 && length <= META && length <= raw.length - offset, "replacement journal bound");
            byte[] row = Arrays.copyOfRange(raw, offset, offset + (int) length); r = record(row, 21, META);
            equal(r.take(32), digest(replacement), "replacement plan digest"); require(r.i64() == phase, "replacement row sequence");
            equal(r.take(32), previousHash, "replacement chain"); require(r.u8() == phase, "replacement preparation only");
            equal(r.take(128), new byte[128], "replacement no group decision"); r.end();
            previousHash = digest(row); offset += (int) length;
        }
        require(offset == raw.length, "replacement journal tail");
    }

    static Map<String, Object> validate(Map<String, byte[]> files) throws Exception {
        var g = genesis(file(files, "genesis.gsr")); var m = manifest(file(files, "manifest.gsr"), g);
        byte[] plan = file(files, "plan.gsr"), receipt = file(files, "receipt.gsr"); var p = plan(plan, m, g);
        var preparations = receipt(receipt, plan, m, p);
        for (int i = 0; i < 3; i++) {
            String node = m.nodes.get(i); equal(file(files, node + "/bootstrap-prepared.gsr"), preparations.get(i), "local preparation");
            for (Item item : p.inventories.get(i)) {
                byte[] raw = file(files, node + "/" + item.name); require(raw.length == item.size, "payload size"); equal(sha(raw), item.digest, "payload inventory binding");
            }
            equal(file(files, node + "/genesis.gsr"), g.raw, "local genesis"); equal(file(files, node + "/manifest.gsr"), m.raw, "local manifest");
            initialRoot(files, node, m);
            var seal = record(file(files, node + "/bootstrap-seal.gsr"), 20, META); require(seal.text(64).equals(node), "seal node");
            equal(seal.blob(META), receipt, "seal receipt"); seal.end();
        }
        journal(file(files, "operation.gsr"), plan, receipt, preparations);
        var source = source(g.source); long bytes = 0;
        for (Item item : source.inventory) {
            byte[] raw = file(files, "source/" + item.name); require(raw.length == item.size, "source bytes length"); equal(sha(raw), item.digest, "source bytes binding"); bytes = Math.addExact(bytes, item.size);
        }
        require(bytes <= number(p.descriptor.get("maxSourceBytes")), "source bytes capacity");
        long projected = plan.length + file(files, "operation.gsr").length + 2L * receipt.length, pendingSeal = 0;
        var locals = list(p.descriptor.get("replicas"));
        for (int i = 0; i < 3; i++) {
            long payload = 0;
            for (Item item : p.inventories.get(i)) payload = Math.addExact(payload, item.size);
            long seal = file(files, m.nodes.get(i) + "/bootstrap-seal.gsr").length;
            long retained = Math.addExact(payload, preparations.get(i).length + 2 * seal);
            require(retained <= number(object(object(locals.get(i)).get("replicationBounds")).get("maxRetainedLogBytes")), "local retained capacity");
            projected = Math.addExact(projected, payload + preparations.get(i).length + seal); pendingSeal = Math.max(pendingSeal, seal);
        }
        require(Math.addExact(projected, pendingSeal) <= number(p.descriptor.get("maxOperationBytes")), "operation bytes capacity");
        administrativeRecords(files, m, g, p);
        var sequences = new ArrayList<Long>();
        for (String name : new TreeSet<>(files.keySet())) {
            if (name.startsWith("snapshot-")) sequences.add(snapshot(files.get(name), m, g));
            if (name.startsWith("wire-")) wire(files.get(name), m, g);
        }
        require(!sequences.isEmpty(), "snapshot evidence");
        return Map.of("baseSequence", g.base, "applicationHistory", uuid(g.history), "snapshotSequences", sequences,
                "manifestDigest", hex(digest(m.raw)), "genesisDigest", hex(digest(g.raw)));
    }
}
