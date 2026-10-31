package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.stream.IntStream;

/** Test topology only. Quorum acceptance still comes from the actual protocol. */
record V53JoiningProfile(int size, MembershipChangeKind kind) {
    V53JoiningProfile {
        if (!((kind == MembershipChangeKind.ADD && (size == 3 || size == 4)) ||
                (kind == MembershipChangeKind.REPLACE && size >= 3 && size <= 5)))
            throw new IllegalArgumentException("joining profile");
    }
    static V53JoiningProfile parse(String value) {
        for (int size = 3; size <= 5; size++) for (var kind : List.of(MembershipChangeKind.ADD, MembershipChangeKind.REPLACE))
            if (value.equals(size + "-" + kind) && (kind != MembershipChangeKind.ADD || size < 5))
                return new V53JoiningProfile(size, kind);
        throw new IllegalArgumentException("joining profile");
    }
    String name() { return size + "-" + kind; }
    String joining() { return "node-" + (size + 1); }
    int majority() { return size / 2 + 1; }
    List<Integer> liveIndices() { return IntStream.range(0, majority()).boxed().toList(); }
    List<String> oldVoters() { return liveIndices().stream().map(i -> "node-" + (i + 1)).toList(); }
    List<String> targets() {
        var nodes = new ArrayList<String>();
        for (int i = 1; i <= size; i++) if (kind != MembershipChangeKind.REPLACE || i != size) nodes.add("node-" + i);
        nodes.add(joining()); return List.copyOf(nodes);
    }
    boolean requiresJoiningAck() {
        return oldVoters().stream().filter(targets()::contains).count() < targets().size() / 2 + 1;
    }
    int otherOld(int voter) {
        if (!liveIndices().contains(voter)) throw new IllegalArgumentException("joining live old voter");
        return voter == 0 ? 1 : 0;
    }
    Set<String> selected(Map<String,Object> view, MembershipFormat.Decoded record) {
        var voters=MembershipFormat.list(record.value().get("sources")).stream()
                .map(v->(String)MembershipFormat.object(v).get("voter")).toList();
        return selected(view,voters);
    }
    Set<String> selected(Map<String,Object> view, List<String> voters) {
        var available=new HashSet<>(oldVoters());available.add(joining());
        if (!voters.contains("node-1") || !available.containsAll(voters))
            throw new IllegalArgumentException("joining original available selection");
        MembershipContext.quorum(view,voters);
        return Set.copyOf(voters);
    }
}
