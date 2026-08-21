package org.example.generalsearch.index;

import java.util.Optional;
import org.example.generalsearch.query.CandidateResult;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;

public interface IndexSnapshot<T> {
    Field<T, ?> field();

    Optional<CandidateResult> candidates(Query<T> query);

    IndexBuilder<T> toBuilder();
}
