package fixture;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;

public final class V2StyleConsumer {
    private V2StyleConsumer() {}

    public static List<SearchHit<Article>> search() {
        TextField<Article> text = TextField.of(
                ArticleSearchFields.BODY, Analyzer.simple());
        try (SearchEngine<Long, Article> engine =
                     SearchEngine.builder(ArticleSearchFields.SCHEMA)
                             .indexes(ArticleSearchFields.INDEX_DEFINITIONS)
                             .index(IndexDefinition.text(text))
                             .build()) {
            engine.addAll(List.of(
                    new Article(1L, "guide", 20, "java search"),
                    new Article(2L, "guide", 30, "java java engine"))).join();
            return engine.searchTopK(RankedSearchRequest.filtered(
                    TextScoringQuery.of(text, "java"),
                    Query.eq(ArticleSearchFields.CATEGORY, "guide"),
                    10));
        }
    }
}

record Article(
        @SearchId long id,
        @SearchIndex(IndexType.EQUALITY) String category,
        @SearchIndex(IndexType.RANGE) int price,
        String body
) {}
