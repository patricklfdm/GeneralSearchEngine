package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Verified immutable recovery values. Selection never samples mutable voter status. */
final class AutomaticRecovery {
    private AutomaticRecovery() { }
    static Map<String, Object> ballotOf(Record row) {
        var value = new LinkedHashMap<String, Object>();
        for (String k : List.of("epoch", "proposer", "incarnation")) value.put(k, row.value().get(k));
        return value;
    }
    static int index(Record snapshot) { return list(snapshot.value().get("anchors")).size(); }
    static String digestAt(Record snapshot, int index) {
        need(index >= 0 && index <= index(snapshot), "snapshot ancestor unavailable");
        return index == 0 ? text(snapshot.value(), "manifestDigest") : text(object(list(snapshot.value().get("anchors")).get(index - 1)), "entryDigest");
    }
    static long epochAt(Record snapshot, int index) {
        return index == 0 ? 1 : number(object(list(snapshot.value().get("anchors")).get(index - 1)), "originEpoch");
    }
    static void agrees(Record left, Record right, int through) {
        need(through <= index(left) && through <= index(right), "incomplete comparison prefix");
        need(list(left.value().get("anchors")).subList(0, through).equals(list(right.value().get("anchors")).subList(0, through)), "conflicting proven ancestry");
        if (index(left) == index(right)) need(left.value().get("application").equals(right.value().get("application")), "same-cut application images differ");
    }
    static void snapshotSemantics(Map<String, Object> value) {
        var anchors = list(value.get("anchors")); long sequence = number(value, "baseSequence"), epoch = 1; Object incarnation = ZERO;
        for (Object item : anchors) {
            var a = object(item); long next = number(a, "originEpoch");
            need(next >= 2 && !a.get("originIncarnation").equals(ZERO) && next >= epoch
                    && (next != epoch || incarnation.equals(a.get("originIncarnation"))), "snapshot origin ancestry");
            epoch = next; incarnation = a.get("originIncarnation");
            if (number(a, "operation") <= 8) { capacity(sequence < Long.MAX_VALUE, "snapshot sequence overflow"); sequence++; }
        }
        need(sequence == number(value, "applicationSequence") && anchors.isEmpty() == (value.get("terminalProof") == null), "snapshot sequence/proof");
        if (!anchors.isEmpty()) {
            var proof = decode(unbase(value.get("terminalProof")), "PROOF").value(); var last = object(anchors.getLast());
            need(proof.get("manifestDigest").equals(value.get("manifestDigest")) && number(proof, "index") == anchors.size()
                    && proof.get("entryDigest").equals(last.get("entryDigest")) && number(proof, "epoch") >= number(last, "originEpoch"), "snapshot terminal proof");
            need(proof.get("previousDigest").equals(anchors.size() == 1 ? value.get("manifestDigest") : object(anchors.get(anchors.size() - 2)).get("entryDigest")), "snapshot terminal predecessor");
        }
    }
    static void imageSemantics(Map<String, Object> value) {
        var snapshot = decode(unbase(value.get("snapshot")), "SNAPSHOT");
        need(value.get("manifestDigest").equals(snapshot.value().get("manifestDigest")), "image manifest");
        for (Object raw : list(value.get("acceptances"))) {
            var accepted = decode(unbase(raw), "ACCEPT"); var entry = decode(unbase(accepted.value().get("entry")), "ENTRY");
            need(accepted.value().get("manifestDigest").equals(value.get("manifestDigest")), "image acceptance manifest");
            tail(snapshot, entry);
        }
    }
    static void tail(Record snapshot, Record entry) {
        int cut = index(snapshot);
        need(number(entry.value(), "index") == cut + 1L && entry.value().get("previousDigest").equals(digestAt(snapshot, cut))
                && number(entry.value(), "previousEpoch") == epochAt(snapshot, cut), "accepted tail does not follow proven prefix");
    }
    record Image(Record encoded, Record snapshot, Record accepted) {
        static Image read(byte[] bytes, Record manifest) {
            var row = decode(bytes, "IMAGE"); context(row, manifest);
            var snapshot = decode(unbase(row.value().get("snapshot")), "SNAPSHOT");
            need(snapshot.value().get("baseSequence").equals(manifest.value().get("baseSequence")), "image genesis base");
            var tail = list(row.value().get("acceptances"));
            return new Image(row, snapshot, tail.isEmpty() ? null : decode(unbase(tail.getFirst()), "ACCEPT"));
        }
    }
    record Basis(Record record, Image image) {
        static Basis read(byte[] descriptor, byte[] bytes, Record manifest) {
            var basis = decode(descriptor, "BASIS"); context(basis, manifest); var image = Image.read(bytes, manifest);
            need(basis.value().get("imageDigest").equals(image.encoded.digest()) && number(basis.value(), "imageBytes") == bytes.length, "frozen basis image identity");
            need(Arrays.equals(basis.value().get("accepted") == null ? null : unbase(basis.value().get("accepted")), image.accepted == null ? null : image.accepted.bytes()), "frozen basis accepted identity");
            need(list(basis.value().get("files")).equals(List.of(file("image.gsr", bytes))), "frozen basis exact inventory");
            if (image.accepted != null) need(number(image.accepted.value(), "epoch") <= number(object(basis.value().get("ballot")), "epoch"), "basis acceptance exceeds promise");
            return new Basis(basis, image);
        }
    }
    record Selection(Record record, Record snapshot, List<Basis> bases, Record sourceAcceptance) {
        Selection { bases = List.copyOf(bases); }
    }
    static Selection select(Record manifest, Map<String, Object> ballot, List<Basis> inputs) {
        need(inputs.size() == 2, "exact prepare quorum required");
        var bases = inputs.stream().map(b -> Basis.read(b.record.bytes(), b.image.encoded.bytes(), manifest))
                .sorted(java.util.Comparator.comparing(b -> text(b.record.value(), "node"))).toList();
        need(!bases.getFirst().record.value().get("node").equals(bases.getLast().record.value().get("node"))
                && bases.stream().anyMatch(b -> b.record.value().get("node").equals(ballot.get("proposer"))), "prepare quorum must include proposer");
        for (Basis b : bases) need(b.record.value().get("ballot").equals(ballot), "mixed prepare ballots");
        Record prefix = bases.stream().map(b -> b.image.snapshot).max(java.util.Comparator.comparingInt(AutomaticRecovery::index)).orElseThrow();
        int cut = index(prefix); Record chosen = null;
        for (Basis b : bases) {
            agrees(prefix, b.image.snapshot, index(b.image.snapshot));
            Record accepted = b.image.accepted;
            if (accepted == null) continue;
            var entry = decode(unbase(accepted.value().get("entry")), "ENTRY");
            if (number(entry.value(), "index") <= cut) continue;
            tail(prefix, entry);
            if (chosen == null || number(accepted.value(), "epoch") > number(chosen.value(), "epoch")) chosen = accepted;
            else if (number(accepted.value(), "epoch") == number(chosen.value(), "epoch"))
                need(ballotOf(accepted).equals(ballotOf(chosen)) && Arrays.equals(unbase(accepted.value().get("entry")), unbase(chosen.value().get("entry"))), "equal-ballot unequal accepted values");
        }
        var value = new LinkedHashMap<String, Object>(); value.put("manifestDigest", manifest.digest()); value.put("ballot", ballot);
        value.put("bases", bases.stream().map(b -> Map.of("node", b.record.value().get("node"), "basisId", b.record.value().get("basisId"), "basisDigest", b.record.digest())).toList());
        value.put("prefixIndex", (long) cut); value.put("prefixDigest", digestAt(prefix, cut));
        value.put("nextEntry", chosen == null ? null : chosen.value().get("entry")); value.put("sourceBallot", chosen == null ? null : ballotOf(chosen));
        var selected = decode(encode("SELECTED", value), "SELECTED"); context(selected, manifest);
        return new Selection(selected, prefix, bases, chosen);
    }
    static Map<String, Object> file(String name, byte[] bytes) { return Map.of("path", name, "size", (long) bytes.length, "sha256", sha(bytes)); }
    static byte[] image(Record manifest, Record snapshot, Record accepted) {
        return encode("IMAGE", Map.of("manifestDigest", manifest.digest(), "snapshot", b64(snapshot.bytes()), "acceptances", accepted == null ? List.of() : List.of(b64(accepted.bytes()))));
    }
    static void basisCapacity(Record manifest,String node,Record accepted) {
        // BASIS embeds the unresolved acceptance. Never force a vote that its mandatory
        // recovery descriptor could not carry at a future (longer decimal) ballot.
        String proposer=nodes(manifest.value()).stream().max(java.util.Comparator.comparingInt(String::length)).orElseThrow();
        var ballot=Map.of("epoch",Long.MAX_VALUE,"proposer",proposer,"incarnation","11111111-1111-1111-1111-111111111111");
        encode("BASIS",Map.of("manifestDigest",manifest.digest(),"node",node,"ballot",ballot,"basisId","11111111-1111-1111-1111-111111111111",
                "imageDigest","0".repeat(64),"imageBytes",(long)IMAGE,"accepted",b64(accepted.bytes()),
                "files",List.of(Map.of("path","image.gsr","size",(long)IMAGE,"sha256","0".repeat(64)))));
    }
}
