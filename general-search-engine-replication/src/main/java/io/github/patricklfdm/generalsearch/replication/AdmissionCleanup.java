package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionConfiguration.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Exact inventory deletion after a forced, irreversible pre-commit abort decision. */
final class AdmissionCleanup {
    private AdmissionCleanup() { }

    record Spec(String operationDigest, String tail, Map<String, Object> descriptor) {
        byte[] encode() { return record(22, out -> { hash(out, operationDigest); hash(out, tail); blob(out, ReplicaJson.encode(descriptor, META)); }); }
        String digest() { return frameDigest(encode()); }
        Path operation() { return path(descriptor.get("operation")); }
        List<Path> deletions() { return array(descriptor.get("deletePaths")).stream().map(value -> Path.of((String) value)).toList(); }
        List<Map<String, Object>> inventory() { return array(descriptor.get("inventory")).stream().map(AdmissionConfiguration::object).toList(); }
        ReplicationCleanupPlan summary() {
            String inventoryDigest = sha256(join("gse-v50-cleanup-inventory-v1\0".getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                    ReplicaJson.encode(descriptor.get("inventory"), META)));
            return new ReplicationCleanupPlan(operation(), operationDigest, deletions(), inventoryDigest, digest());
        }
        static Spec read(byte[] bytes) throws IOException {
            var in = decode(bytes, 22, META); String operation = hash(in), tail = hash(in);
            var descriptor = object(ReplicaJson.decode(blob(in, META), META)); end(in);
            keys(descriptor, "operation", "inventory", "deletePaths"); path(descriptor.get("operation"));
            var result = new Spec(operation, tail, descriptor); result.validate(); return result;
        }
        void validate() {
            String previous = null; var owned = new HashSet<Path>(); var all = new HashSet<Path>();
            require(inventory().size() > 0 && inventory().size() <= 10_000, CAPACITY_EXCEEDED, "invalid cleanup inventory count");
            for (var entry : inventory()) {
                keys(entry, "path", "kind", "size", "digest", "owner"); String name = string(entry, "path"); Path path = Path.of(name);
                require(path.isAbsolute() && path.normalize().equals(path) && all.add(path)
                        && (previous == null || UTF8.compare(previous, name) < 0), INTEGRITY_FAILURE, "noncanonical cleanup path/order"); previous = name;
                String owner = string(entry, "owner"), kind = string(entry, "kind"); long size = number(entry, "size", 0, 1L << 40);
                validHash(string(entry, "digest"));
                require(Set.of("file", "directory").contains(kind) && (!kind.equals("directory") || size == 0 && entry.get("digest").equals(ZERO)),
                        INTEGRITY_FAILURE, "invalid cleanup member");
                require(owner.equals(operationDigest) || owner.equals("source"), INTEGRITY_FAILURE, "invalid cleanup owner");
                if (owner.equals(operationDigest)) owned.add(path);
            }
            var delete = deletions();
            require(delete.size() == owned.size() && new HashSet<>(delete).equals(owned) && delete.getLast().equals(operation()),
                    INTEGRITY_FAILURE, "cleanup cannot omit owned members or delete protected source");
            for (int i = 0; i < delete.size(); i++) for (int j = i + 1; j < delete.size(); j++)
                require(!delete.get(j).startsWith(delete.get(i)), INTEGRITY_FAILURE, "cleanup parent precedes child");
        }
    }

    static ReplicationCleanupPlan plan(Path requested) {
        return AdmissionBootstrap.guarded(() -> {
            Path operation = AdmissionPaths.safe(requested);
            try (var owner = owner(operation)) {
                return inspect(operation).summary();
            }
        });
    }

    private static Spec inspect(Path operation) throws IOException {
        AdmissionBootstrap.operationInventory(operation);
        Path retained = operation.resolve("cleanup.gsr");
        if (Files.exists(retained, LinkOption.NOFOLLOW_LINKS)) {
            var spec = Spec.read(AdmissionPaths.read(retained, META));
            require(spec.operation().equals(operation), CONFLICTING_HISTORY, "cleanup coordinator relocated");
            validateScope(spec);
            verifyRemaining(spec, true); return spec;
        }
        var plan = AdmissionPlan.read(AdmissionPaths.read(operation.resolve("plan.gsr"), META));
        require(plan.operation().equals(operation), CONFLICTING_HISTORY, "operation relocated");
        AdmissionPaths.recheck(object(plan.descriptor().get("operation")));
        var tail = AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast();
        require(tail.phase() <= 2, CONFLICTING_HISTORY, "cleanup requires a proven pre-commit attempt");
        require(!Files.exists(operation.resolve("receipt.gsr"), LinkOption.NOFOLLOW_LINKS)
                && !Files.exists(operation.resolve("receipt.pending.gsr"), LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "decision evidence forbids cleanup");
        var owners = new ArrayList<AdmissionPaths.Owner>();
        try {
            var inventory = new ArrayList<Map<String, Object>>();
            addInventory(inventory, operation, plan.digest(), plan.maximum());
            for (int i = 0; i < 3; i++) {
                AdmissionPaths.recheck(object(plan.local(i).get("target")));
                Path target = plan.target(i);
                if (!Files.exists(target, LinkOption.NOFOLLOW_LINKS)) continue;
                owners.add(AdmissionPaths.own(target.resolve("replica.lock"), false));
                var expected = new HashMap<String, Member>(); for (var member : plan.payloads().get(i)) expected.put(member.name(), member);
                byte[] preparation = plan.preparation(i);
                expected.put("bootstrap-prepared.gsr", new Member("bootstrap-prepared.gsr", 1, preparation.length, sha256(preparation)));
                for (var member : AdmissionPaths.inventory(target, plan.maximum())) {
                    var wanted = expected.get(member.name());
                    require(wanted != null && member.kind() == 1 && member.size() <= wanted.size()
                                    && (member.size() != wanted.size() || member.digest().equals(wanted.digest())),
                            CONFLICTING_HISTORY, "unknown or changed uncommitted target member");
                }
                addInventory(inventory, target, plan.digest(), plan.maximum());
            }
            if (plan.sourcePath() != null) {
                require(AdmissionPaths.inventory(plan.sourcePath(), number(plan.descriptor(), "maxSourceBytes", 1, 1L << 40)).equals(plan.source().members()),
                        CONFLICTING_HISTORY, "protected source changed");
                addInventory(inventory, plan.sourcePath(), "source", number(plan.descriptor(), "maxSourceBytes", 1, 1L << 40));
            }
            inventory.sort(Comparator.comparing(value -> (String) value.get("path"), UTF8));
            var delete = inventory.stream().filter(value -> value.get("owner").equals(plan.digest()))
                    .map(value -> Path.of((String) value.get("path"))).sorted(deletionOrder(operation)).map(Path::toString).toList();
            var result = new Spec(plan.digest(), tail.digest(), Map.of("operation", plan.descriptor().get("operation"), "inventory", inventory, "deletePaths", delete));
            result.validate(); result.encode(); return result;
        } finally { closeOwners(owners); }
    }

    static void apply(ReplicationCleanupPlan summary) {
        AdmissionBootstrap.guarded(() -> {
            Path operation = AdmissionPaths.safe(summary.operationDirectory());
            try (var owner = owner(operation)) {
                var spec = inspect(operation);
                require(spec.summary().equals(summary), CONFLICTING_HISTORY, "caller cleanup plan is stale or forged");
                var owners = new ArrayList<AdmissionPaths.Owner>();
                try {
                    for (var entry : spec.inventory()) {
                        Path path = Path.of((String) entry.get("path"));
                        if (entry.get("owner").equals(spec.operationDigest()) && path.getFileName().toString().equals("replica.lock")
                                && Files.exists(path, LinkOption.NOFOLLOW_LINKS)) owners.add(AdmissionPaths.own(path, false));
                    }
                    Path retained = operation.resolve("cleanup.gsr");
                    if (!Files.exists(retained, LinkOption.NOFOLLOW_LINKS)) {
                        verifyRemaining(spec, false); AdmissionPaths.write(retained, spec.encode()); AdmissionIo.at("CLEANUP_PLAN_FORCED");
                    } else AdmissionPaths.exact(retained, spec.encode());
                    // Hold both owners before unlinking operation.lock. A resumed cleaner
                    // locks cleanup.gsr once that pathname is gone, including while this
                    // process still owns the original unlinked lock inode.
                    try (var retainedOwner = Files.exists(operation.resolve("operation.lock"), LinkOption.NOFOLLOW_LINKS)
                            ? AdmissionPaths.own(retained, false, false) : null) {
                        Path journal = operation.resolve("operation.gsr");
                        if (Files.exists(journal, LinkOption.NOFOLLOW_LINKS)) {
                            var rows = AdmissionJournal.parse(AdmissionPaths.read(journal, 5 * META)); var tail = rows.getLast();
                            if (tail.phase() <= 2) {
                                require(tail.digest().equals(spec.tail()), CONFLICTING_HISTORY, "cleanup observed journal changed");
                                AdmissionBootstrap.append(operation, tail.abort().encode()); AdmissionIo.at("CLEANUP_ABORTING_FORCED");
                            }
                        }
                        int prefix = verifyRemaining(spec, true);
                        var paths = spec.deletions();
                        for (int i = prefix; i < paths.size(); i++) {
                            Path path = paths.get(i);
                            if (path.equals(operation)) {
                                // The retained deletion authority survives removal of its original plan/journal.
                                Files.delete(retained); AdmissionPaths.forceDirectory(operation);
                            }
                            Files.delete(path); AdmissionPaths.forceDirectory(path.getParent());
                            AdmissionIo.at("CLEANUP_DELETE_" + i + "_FORCED");
                        }
                    }
                } finally { closeOwners(owners); }
            }
            return null;
        });
    }

    private static int verifyRemaining(Spec spec, boolean allowAborting) throws IOException {
        AdmissionPaths.recheck(object(spec.descriptor().get("operation")));
        var expected = new HashMap<Path, Map<String, Object>>(); for (var entry : spec.inventory()) expected.put(Path.of((String) entry.get("path")), entry);
        var delete = spec.deletions(); int prefix = 0;
        while (prefix < delete.size() && !Files.exists(delete.get(prefix), LinkOption.NOFOLLOW_LINKS)) prefix++;
        for (int i = prefix; i < delete.size(); i++) require(Files.exists(delete.get(i), LinkOption.NOFOLLOW_LINKS), CONFLICTING_HISTORY, "cleanup has a non-prefix deletion");
        var missing = Set.copyOf(delete.subList(0, prefix));
        for (var entry : spec.inventory()) {
            Path path = Path.of((String) entry.get("path")); if (missing.contains(path)) continue;
            AdmissionPaths.safe(path);
            if (entry.get("kind").equals("directory")) {
                require(Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS), CONFLICTING_HISTORY, "cleanup directory changed");
                try (var children = Files.newDirectoryStream(path)) {
                    for (var child : children) require(expected.containsKey(child) || child.equals(spec.operation().resolve("cleanup.gsr")),
                            CONFLICTING_HISTORY, "unknown member appeared after cleanup planning");
                }
                continue;
            }
            if (allowAborting && path.equals(spec.operation().resolve("operation.gsr"))) {
                byte[] bytes = AdmissionPaths.read(path, 5 * META); var rows = AdmissionJournal.parse(bytes); var last = rows.getLast();
                if (last.phase() == 5) {
                    require(rows.size() > 1 && rows.get(rows.size() - 2).phase() <= 2 && last.equals(rows.get(rows.size() - 2).abort())
                                    && rows.get(rows.size() - 2).digest().equals(spec.tail()) && last.plan().equals(spec.operationDigest())
                                    && sha256(Arrays.copyOf(bytes, bytes.length - last.encode().length)).equals(entry.get("digest")),
                            CONFLICTING_HISTORY, "cleanup abort authority changed");
                    continue;
                }
            }
            long size = number(entry, "size", 0, 1L << 40);
            AdmissionPaths.regular(path);
            require(Files.size(path) == size, CONFLICTING_HISTORY, "cleanup file size changed");
            var actual = AdmissionPaths.inventory(path.getParent(), 1L << 40).stream()
                    .filter(member -> member.name().equals(path.getFileName().toString())).findFirst().orElseThrow();
            require(actual.digest().equals(entry.get("digest")), CONFLICTING_HISTORY, "cleanup file changed");
        }
        if (prefix > 0) require(allowAborting && Files.exists(spec.operation().resolve("cleanup.gsr"), LinkOption.NOFOLLOW_LINKS),
                INTEGRITY_FAILURE, "missing retained cleanup authority");
        return prefix;
    }

    private static void validateScope(Spec spec) throws IOException {
        Path original = spec.operation().resolve("plan.gsr");
        var delete = spec.deletions();
        require(delete.equals(delete.stream().sorted(deletionOrder(spec.operation())).toList()), INTEGRITY_FAILURE,
                "cleanup authority markers must be retained until target deletion completes");
        if (!Files.exists(original, LinkOption.NOFOLLOW_LINKS)) {
            for (Path remaining : delete) if (Files.exists(remaining, LinkOption.NOFOLLOW_LINKS)) require(
                    remaining.equals(spec.operation()) || remaining.equals(spec.operation().resolve("operation.lock")),
                    INTEGRITY_FAILURE, "original plan missing before final coordinator cleanup");
            return;
        }
        var plan = AdmissionPlan.read(AdmissionPaths.read(original, META));
        require(plan.operation().equals(spec.operation()) && plan.digest().equals(spec.operationDigest()),
                CONFLICTING_HISTORY, "cleanup differs from original operation authority");
        for (var entry : spec.inventory()) {
            Path member = Path.of((String) entry.get("path"));
            if (entry.get("owner").equals("source")) {
                require(plan.sourcePath() != null && member.startsWith(plan.sourcePath()), INTEGRITY_FAILURE, "foreign protected-source binding");
            } else {
                boolean owned = member.equals(plan.operation()) || member.getParent().equals(plan.operation())
                        && Set.of("operation.lock", "plan.gsr", "operation.gsr").contains(member.getFileName().toString());
                for (int i = 0; i < 3; i++) owned |= member.equals(plan.target(i)) || member.getParent().equals(plan.target(i))
                        && (member.getFileName().toString().equals("bootstrap-prepared.gsr") || plan.payloads().get(i).stream()
                        .anyMatch(expected -> expected.name().equals(member.getFileName().toString())));
                require(owned, INTEGRITY_FAILURE, "cleanup names output outside original plan ownership");
            }
        }
    }

    private static Comparator<Path> deletionOrder(Path operation) {
        return Comparator.<Path>comparingInt(path -> path.equals(operation) ? 5
                : path.equals(operation.resolve("operation.lock")) ? 4
                : path.equals(operation.resolve("plan.gsr")) ? 3
                : path.equals(operation.resolve("operation.gsr")) ? 2
                : path.startsWith(operation) ? 1 : 0)
                .thenComparing(Comparator.comparingInt(Path::getNameCount).reversed()).thenComparing(Path::toString, UTF8);
    }

    private static AdmissionPaths.Owner owner(Path operation) throws IOException {
        Path lock = operation.resolve("operation.lock");
        // The exact retained plan remains lockable during the final deletion of the original markers.
        return Files.exists(lock, LinkOption.NOFOLLOW_LINKS) ? AdmissionPaths.own(lock, false)
                : AdmissionPaths.own(operation.resolve("cleanup.gsr"), false, false);
    }

    private static void addInventory(List<Map<String, Object>> result, Path directory, String owner, long maximum) throws IOException {
        result.add(Map.of("path", directory.toString(), "kind", "directory", "size", 0L, "digest", ZERO, "owner", owner));
        for (var member : AdmissionPaths.inventory(directory, maximum)) {
            if (directory.resolve(member.name()).equals(directory.resolve("cleanup.gsr"))) continue;
            result.add(Map.of("path", directory.resolve(member.name()).toString(), "kind", member.kind() == 0 ? "directory" : "file",
                    "size", member.size(), "digest", member.digest(), "owner", owner));
        }
    }
    private static void closeOwners(List<AdmissionPaths.Owner> owners) throws IOException {
        IOException failure = null;
        for (int i = owners.size() - 1; i >= 0; i--) try { owners.get(i).close(); }
        catch (IOException error) { if (failure == null) failure = error; else failure.addSuppressed(error); }
        if (failure != null) throw failure;
    }
}
