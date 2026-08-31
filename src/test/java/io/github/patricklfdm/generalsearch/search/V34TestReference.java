package io.github.patricklfdm.generalsearch.search;

import java.util.List;

/** Primitive-only V3.3 outcome oracle reserved for V3.4 pre-change tests. */
final class V34TestReference {
    private V34TestReference() {
    }

    static List<Integer> initialIds() {
        return List.of(0, 1, 3);
    }

    static List<Integer> afterAdd() {
        return List.of(0, 1, 3, 4);
    }

    static List<Integer> afterUpdate() {
        return List.of(0, 3, 4);
    }

    static List<Integer> afterRemove() {
        return List.of(0, 4);
    }

    static long orderedIdChecksum(List<Integer> ids) {
        long checksum = ids.size();
        for (int id : ids) {
            checksum = Math.addExact(Math.multiplyExact(checksum, 31L), id);
        }
        return checksum;
    }
}
