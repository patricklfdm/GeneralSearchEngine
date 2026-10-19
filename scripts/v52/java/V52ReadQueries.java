package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.schema.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.*;

/** Identical seven-query program compiled independently against the published V4.4 core. */
public final class V52ReadQueries {
    public record Doc(int id,String value) { }
    public static final Field<Doc,Integer> ID=Field.of("id",Integer.class,Doc::id);
    public static final Field<Doc,String> VALUE=Field.of("value",String.class,Doc::value);
    public static final TextField<Doc> TEXT=TextField.of(VALUE,SimpleAnalyzer.INSTANCE);
    public static SearchEngineBuilder<Integer,Doc> builder() {
        return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.text(TEXT))
                .config(new SnapshotEngineConfig(64,16,java.time.Duration.ofMillis(1)));
    }
    public static DurableStorageConfig<Integer,Doc> storage(Path path) {
        return DurableStorageConfig.builder(path,new Codec()).format(new DurableStorageFormat("gse-durable",1,2))
                .storageIdentity("v52-read-store").schemaIdentity("v52-read-schema")
                .maxEncodedDocumentBytes(65536).maxDocuments(1000).maxBulkElements(100).build();
    }
    public static final class Codec implements DurableCodec<Integer,Doc> {
        public String codecId(){return "v52-read-codec";} public int codecVersion(){return 1;}
        public byte[] encodeKey(Integer key){return ByteBuffer.allocate(4).putInt(key).array();}
        public Integer decodeKey(byte[] bytes){return ByteBuffer.wrap(bytes).getInt();}
        public byte[] encodeDocument(Doc doc) {
            byte[] value=doc.value().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(4+value.length).putInt(doc.id()).put(value).array();
        }
        public Doc decodeDocument(byte[] bytes) {
            return new Doc(ByteBuffer.wrap(bytes).getInt(),new String(bytes,4,bytes.length-4,StandardCharsets.UTF_8));
        }
    }
    public interface View {
        Doc get(Integer id);
        List<Doc> search(Query<Doc> query);
        List<SearchHit<Doc>> searchTopK(RankedSearchRequest<Doc> request);
        SearchResult<Doc> search(SearchRequest<Doc> request);
        HighlightedSearchResult<Doc> search(HighlightedSearchRequest<Doc> request);
        Optional<SearchExplanation<Doc>> explain(SearchRequest<Doc> request,Integer id);
        long currentSequence();
    }
    public static View core(DurableSearchEngine<Integer,Doc> engine) {
        return new View() {
            public Doc get(Integer id){return engine.get(id);}
            public List<Doc> search(Query<Doc> query){return engine.search(query);}
            public List<SearchHit<Doc>> searchTopK(RankedSearchRequest<Doc> request){return engine.searchTopK(request);}
            public SearchResult<Doc> search(SearchRequest<Doc> request){return engine.search(request);}
            public HighlightedSearchResult<Doc> search(HighlightedSearchRequest<Doc> request){return engine.search(request);}
            public Optional<SearchExplanation<Doc>> explain(SearchRequest<Doc> request,Integer id){return engine.explain(request,id);}
            public long currentSequence(){return engine.currentSequence();}
        };
    }
    public static Map<String,Object> doc(Doc d){return Map.of("id",d.id(),"value",d.value());}
    private static Object hits(List<SearchHit<Doc>> hits) {
        return hits.stream().map(h->Map.of("document",doc(h.document()),"score",Double.toHexString(h.score()))).toList();
    }
    private static Object explanation(ExplanationNode n) {
        return Map.of("matched",n.matched(),"score",Double.toHexString(n.score()),"description",n.description(),
                "children",n.children().stream().map(V52ReadQueries::explanation).toList());
    }
    public static Map<String,Object> report(View view) {
        var report=new LinkedHashMap<String,Object>();var all=view.search(Query.matchAll());
        report.put("documents",all.stream().map(V52ReadQueries::doc).toList());
        var existing=view.get(1);report.put("get",existing==null?null:doc(existing));
        var missing=view.get(99999);report.put("missing",missing==null?null:doc(missing));
        report.put("sequence",view.currentSequence());
        var queries=List.of(Query.eq(VALUE,"java search"),Query.prefix(VALUE,"java"),Query.term(TEXT,"java"),
                Query.allTerms(TEXT,"java search"),Query.anyTerms(TEXT,"memory query"),Query.not(Query.term(TEXT,"missing")));
        report.put("filters",queries.stream().map(q->view.search(q).stream().map(Doc::id).toList()).toList());
        report.put("ranking",hits(view.searchTopK(RankedSearchRequest.of(TextScoringQuery.of(TEXT,"java search"),20))));
        var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"java search")).limit(3).build();
        report.put("search",List.of(hits(view.search(request).hits()),
                hits(view.search(SearchRequest.of(SearchQueries.phrase(TEXT,"java search"))).hits()),
                hits(view.search(SearchRequest.of(SearchQueries.fuzzy(TEXT,"serch"))).hits())));
        report.put("explanations",all.stream().map(d->view.explain(request,d.id()).orElseThrow()).map(e->Map.of(
                "document",doc(e.document()),"matched",e.matched(),"score",Double.toHexString(e.score()),"detail",explanation(e.detail()))).toList());
        report.put("highlights",view.search(HighlightedSearchRequest.<Doc>builder(request).field(TEXT)
                .contextCharacters(3).maxFragmentsPerField(3).build()).hits().stream().map(h->Map.of(
                "document",doc(h.hit().document()),"score",Double.toHexString(h.hit().score()),"fields",h.highlights().stream().map(f->Map.of(
                        "field",f.fieldName(),"fragments",f.fragments().stream().map(g->Map.of(
                                "start",g.startOffset(),"end",g.endOffset(),"text",g.text(),
                                "spans",g.spans().stream().map(s->List.of(s.startOffset(),s.endOffset())).toList())).toList())).toList())).toList());
        return report;
    }
}
