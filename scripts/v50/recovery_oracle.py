"""Independent proof-preservation and application-replay oracle for Phase 4 evidence."""

import struct
from scripts.v50 import storage_format as sf
from scripts.v50.replicated_history_model import APPLICATION_OPERATIONS
from scripts.v50.recovery_format import blob


def document(key, encoded):
    sf.check(len(key) == 4 and len(encoded) >= 4, "invalid fixture document/key")
    identity = struct.unpack(">i", key)[0]
    sf.check(encoded[:4] == key, "fixture document changed its key")
    return identity, encoded[4:].decode("utf-8", errors="strict")


def replay(report, through):
    sf.check(report["codecId"] == "leader-fixture", "application oracle requires its explicit fixture codec")
    sf.check(report["snapshotIndex"] <= through <= report["commitIndex"], "application cut lacks committed authority")
    documents, indexes = {}, {"value": "equality"}
    snapshot = report["snapshotApplication"]
    if snapshot is not None:
        indexes = {index["field"]: index["kind"] for index in snapshot["indexes"]}
        for item in snapshot["documents"]:
            identity, value = document(bytes.fromhex(item["keyHex"]), bytes.fromhex(item["documentHex"]))
            sf.check(identity not in documents, "duplicate snapshot document")
            documents[identity] = value
    for entry in report["retainedApplicationEntries"]:
        if entry["index"] > through:
            break
        operation = entry["operation"]
        payload = bytes.fromhex(entry["payloadHex"])
        if operation == "NO_OP":
            sf.check(payload == b"", "nonempty NO_OP")
            continue
        reader = sf.Reader(payload)
        sf.check(reader.number("H") == 1, "unsupported fixture payload")
        if operation in {"ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL", "REMOVE_ALL"}:
            count = reader.number("i")
            sf.check(0 <= count <= sf.MAX_ENTRIES and count <= (len(payload) - reader.offset) // 4, "invalid application count")
            sf.check(operation.endswith("_ALL") or count == 1, "invalid single operation count")
            for _ in range(count):
                key = blob(reader, 1024 * 1024)
                sf.check(len(key) == 4, "invalid fixture key")
                identity = struct.unpack(">i", key)[0]
                if operation.startswith("REMOVE"):
                    documents.pop(identity, None)
                else:
                    identity, value = document(key, blob(reader, 1024 * 1024))
                    sf.check((identity not in documents) if operation.startswith("ADD") else (identity in documents), "application history violates key semantics")
                    documents[identity] = value
        elif operation == "INDEX_DROP":
            indexes.pop(reader.string(1024), None)
        elif operation == "INDEX_CREATE":
            import json
            index = json.loads(reader.string(8192))
            sf.check(index["field"] not in indexes, "duplicate application index")
            indexes[index["field"]] = index["kind"]
        else:
            raise ValueError("unsupported application oracle operation")
        reader.end()
    return {"documents": [{"id": key, "value": value} for key, value in documents.items()],
            "queryIds": [key for key, value in documents.items() if value == "shared"], "indexCount": len(indexes)}


def validate(before, reports, observed, control, acknowledged_index=0):
    sf.check(set(reports) == set(observed) == set(sf.VOTERS), "recovery requires three distinct reports")
    for node, report in reports.items():
        sf.check(report["voter"], "recovered disk is still non-voting")
        sf.check(report["commitIndex"] >= acknowledged_index, "successful response lost during recovery")
        state = observed[node]
        sf.check(state["appliedIndex"] <= report["commitIndex"], "application exceeded committed proof")
        sequence = sum(entry["operation"] in APPLICATION_OPERATIONS for entry in report["entries"][:state["appliedIndex"]])
        sf.check(sequence == state["applicationSequence"], "recovery application sequence drift")
        replayed = replay(report, state["appliedIndex"])
        sf.check(replayed == control, "independent replay differs from published V4.4 control")
        sf.check({key: state[key] for key in control} == control, "observed application differs from published V4.4 control")
        for old in before.values():
            index = old["commitIndex"]
            sf.check(report["commitIndex"] >= index and report["entries"][:index] == old["entries"][:index], "recovery discarded or changed a valid surviving proof prefix")
        floor = report["recoveryFloor"]
        if floor:
            sources = [other for other in reports.values() if other["commitIndex"] >= floor and other["entries"][:floor] == report["entries"][:floor]]
            sf.check(len(sources) >= 2 and report["snapshotIndex"] >= floor, "floor lacks two complete recovery representations")
    committed = min(report["commitIndex"] for report in reports.values())
    sf.check(all(report["entries"][:committed] == reports["node-1"]["entries"][:committed] for report in reports.values()), "recovered histories conflict")
    return {"status": "PASS", "committedThrough": committed, "applicationSequence": observed["node-1"]["applicationSequence"], "control": "published-v4.4"}
