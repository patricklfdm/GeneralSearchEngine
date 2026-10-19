package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.*;
import java.util.*;

/** One declared query per invocation; independently compiled against published core. */
public final class V52MeasurementQueries {
    public static SearchEngineBuilder<Integer,Doc> measurementBuilder() {
        return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.text(TEXT))
                .config(new SnapshotEngineConfig(64,64,java.time.Duration.ofMillis(1)));
    }
    public static final class MeasurementCodec implements DurableCodec<Integer,Doc> {
        private final Codec delegate=new Codec();
        public String codecId(){return "v52-measured-read-codec";}public int codecVersion(){return 1;}
        public byte[] encodeKey(Integer key){return delegate.encodeKey(key);}
        public Integer decodeKey(byte[] bytes){return delegate.decodeKey(bytes);}
        public byte[] encodeDocument(Doc doc){return delegate.encodeDocument(doc);}
        public Doc decodeDocument(byte[] bytes){return delegate.decodeDocument(bytes);}
    }
    public static DurableStorageConfig<Integer,Doc> storage(Path directory) {
        return DurableStorageConfig.builder(directory,new MeasurementCodec()).format(new DurableStorageFormat("gse-durable",1,2))
                .storageIdentity("v52-measurement-store").schemaIdentity("v52-measurement-schema")
                .maxEncodedDocumentBytes(128).maxDocuments(64).maxBulkElements(100).build();
    }
    private static Object hits(List<SearchHit<Doc>> hits) {
        return hits.stream().map(h->Map.of("document",doc(h.document()),"score",Double.toHexString(h.score()))).toList();
    }
    private static Object detail(ExplanationNode node) {
        return Map.of("matched",node.matched(),"score",Double.toHexString(node.score()),"description",node.description(),
                "children",node.children().stream().map(V52MeasurementQueries::detail).toList());
    }
    public static Object answer(View view,Map<String,Object> query) {
        String kind=(String)query.get("kind");
        if(kind.equals("get")) {Doc value=view.get(((Number)query.get("id")).intValue());return value==null?null:doc(value);}
        if(kind.equals("filter"))return view.search(Query.prefix(VALUE,(String)query.get("prefix"))).stream().map(V52ReadQueries::doc).toList();
        int limit=((Number)query.get("limit")).intValue();String text=(String)query.get("text");
        if(kind.equals("ranked"))return hits(view.searchTopK(RankedSearchRequest.of(TextScoringQuery.of(TEXT,text),limit)));
        var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,text)).limit(limit).build();
        if(kind.equals("explain"))return view.explain(request,((Number)query.get("id")).intValue()).map(value->Map.of(
                "document",doc(value.document()),"matched",value.matched(),"score",Double.toHexString(value.score()),"detail",detail(value.detail()))).orElseThrow();
        if(!kind.equals("highlight"))throw new IllegalArgumentException("undeclared measurement query");
        return view.search(HighlightedSearchRequest.<Doc>builder(request).field(TEXT)
                .contextCharacters(((Number)query.get("contextCharacters")).intValue())
                .maxFragmentsPerField(((Number)query.get("maxFragmentsPerField")).intValue()).build()).hits().stream().map(h->Map.of(
                "document",doc(h.hit().document()),"score",Double.toHexString(h.hit().score()),"fields",h.highlights().stream().map(f->Map.of(
                        "field",f.fieldName(),"fragments",f.fragments().stream().map(g->Map.of("start",g.startOffset(),"end",g.endOffset(),"text",g.text(),
                                "spans",g.spans().stream().map(s->List.of(s.startOffset(),s.endOffset())).toList())).toList())).toList())).toList();
    }
    private static Doc from(Map<String,Object> value){return new Doc(((Number)value.get("id")).intValue(),(String)value.get("value"));}
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path output=Path.of(args[0]),input=Path.of(args[1]);Files.createDirectories(output);
        System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        var corpus=(List<Map<String,Object>>)AdmissionJson.parse(Files.readString(input.resolve("corpus.json")));
        var calls=(List<Map<String,Object>>)AdmissionJson.parse(Files.readString(input.resolve("calls.json")));
        var queries=(List<Map<String,Object>>)AdmissionJson.parse(Files.readString(input.resolve("queries.json")));
        var results=new ArrayList<Object>();
        try(var engine=measurementBuilder().buildDurable(storage(output.resolve("store")))) {
            engine.addAll(corpus.stream().map(V52MeasurementQueries::from).toList()).join();
            var view=core(engine);var selected=Set.of(1L,2L,65L,66L,181L);
            for(int i=-1;i<calls.size();i++) {
                if(i>=0) {
                    var call=calls.get(i);if(!call.get("kind").equals("update"))continue;
                    engine.update(from((Map<String,Object>)call.get("document"))).join();
                }
                long sequence=engine.currentSequence();
                if(selected.contains(sequence))results.add(Map.of("sequence",sequence,"documents",engine.search(Query.matchAll()).stream().map(V52ReadQueries::doc).toList(),
                        "answers",queries.stream().map(query->Map.of("query",query,"answer",answer(view,query))).toList()));
            }
            if(engine.currentSequence()!=181)throw new IllegalStateException("measurement foundation sequence");
        }
        System.out.println(AdmissionJson.canonical(Map.of("status","PASS","measured",false,"states",results)));
    }
}
