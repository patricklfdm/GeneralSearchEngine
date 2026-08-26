package io.github.patricklfdm.generalsearch.index.text;

import java.util.ArrayList;
import java.util.List;

/** Test-only bridge that keeps positional reads out of the production public API. */
public final class PostingPositionsTestAccess {
    private PostingPositionsTestAccess() {}

    public static List<Integer> positions(PostingList posting, int docId) {
        IntPositions positions = posting.positions(docId);
        List<Integer> values = new ArrayList<>(positions.size());
        for (int index = 0; index < positions.size(); index++) {
            values.add(positions.get(index));
        }
        return List.copyOf(values);
    }
}
