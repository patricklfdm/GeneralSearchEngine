package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;

import java.io.IOException;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;

/** Immutable group identity, byte-identical on all three voters. */
record ReplicaManifest(ReplicationGroupId groupId, String configurationId,
                       ReplicationNodeId leader, List<ReplicationMember> members,
                       String codecId, int codecVersion, String schemaId, int schemaVersion,
                       String indexConfigurationDigest) {
    ReplicaManifest {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(leader, "leader");
        members = List.copyOf(members);
        for (String identity : List.of(configurationId, codecId, schemaId)) {
            if (!identity.matches("[a-z0-9][a-z0-9._-]{0,127}")) {
                throw new IllegalArgumentException("invalid manifest identity");
            }
        }
        if (members.size() != 3 || codecVersion < 1 || schemaVersion < 1) {
            throw new IllegalArgumentException("manifest requires three voters and positive identity versions");
        }
        var nodes = new HashSet<ReplicationNodeId>();
        var endpoints = new HashSet<ReplicationEndpoint>();
        for (ReplicationMember member : members) {
            if (!nodes.add(member.nodeId()) || !endpoints.add(member.endpoint())) {
                throw new IllegalArgumentException("duplicate manifest member/endpoint");
            }
        }
        if (!nodes.contains(leader)) {
            throw new IllegalArgumentException("configured leader is not a voter");
        }
        validHash(indexConfigurationDigest);
    }

    boolean contains(ReplicationNodeId node) {
        return members.stream().anyMatch(member -> member.nodeId().equals(node));
    }

    byte[] encode() {
        return frame(MANIFEST, body(output -> {
            text(output, "gse-replicated");
            output.writeShort(1);
            output.writeShort(0);
            text(output, "gse-replication");
            output.writeShort(1);
            output.writeShort(0);
            uuid(output, groupId.value());
            text(output, configurationId);
            output.writeLong(1); // immutable genesis epoch
            text(output, leader.value());
            output.writeInt(members.size());
            for (ReplicationMember member : members) {
                text(output, member.nodeId().value());
                text(output, member.endpoint().host());
                output.writeInt(member.endpoint().port());
                output.writeByte(1); // voter
            }
            text(output, codecId);
            output.writeInt(codecVersion);
            text(output, schemaId);
            output.writeInt(schemaVersion);
            hash(output, indexConfigurationDigest);
        }), MAX_METADATA_BYTES);
    }

    String digest() {
        return frameDigest(encode());
    }

    static ReplicaManifest decode(byte[] bytes) throws IOException {
        var input = input(bytes);
        require(text(input, 32).equals("gse-replicated") && input.readUnsignedShort() == 1
                        && input.readUnsignedShort() == 0 && text(input, 32).equals("gse-replication")
                        && input.readUnsignedShort() == 1 && input.readUnsignedShort() == 0,
                ReplicationException.Reason.PROTOCOL_MISMATCH, "unsupported manifest format/protocol");
        var group = new ReplicationGroupId(uuid(input));
        String configuration = text(input, 128);
        require(input.readLong() == 1, ReplicationException.Reason.INTEGRITY_FAILURE, "invalid genesis epoch");
        var leader = new ReplicationNodeId(text(input, 64));
        require(input.readInt() == 3, ReplicationException.Reason.INTEGRITY_FAILURE, "invalid voter count");
        var members = new java.util.ArrayList<ReplicationMember>();
        for (int index = 0; index < 3; index++) {
            var node = new ReplicationNodeId(text(input, 64));
            var endpoint = new ReplicationEndpoint(text(input, 1012), input.readInt());
            require(input.readUnsignedByte() == 1, ReplicationException.Reason.INTEGRITY_FAILURE,
                    "non-voter in immutable manifest");
            members.add(new ReplicationMember(node, endpoint));
        }
        var manifest = new ReplicaManifest(group, configuration, leader, members,
                text(input, 128), input.readInt(), text(input, 128), input.readInt(), hash(input));
        end(input);
        return manifest;
    }
}
