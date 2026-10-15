package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/** Candidate-only capability; never placed on the published V5.1 classpath. */
public final class V52MeasuredExplicitReads implements V52MeasurementConsumer.Reads {
    private final AutomaticReplicatedSearchEngine<Integer,Doc> engine;private final String mode;
    public V52MeasuredExplicitReads(AutomaticReplicatedSearchEngine<Integer,Doc> engine,String mode){this.engine=engine;this.mode=mode;}
    private static View view(ReplicaReadView<Integer,Doc> v) {
        return new View() {
            public Doc get(Integer id){return v.get(id);}
            public List<Doc> search(Query<Doc> query){return v.search(query);}
            public List<SearchHit<Doc>> searchTopK(RankedSearchRequest<Doc> request){return v.searchTopK(request);}
            public SearchResult<Doc> search(SearchRequest<Doc> request){return v.search(request);}
            public HighlightedSearchResult<Doc> search(HighlightedSearchRequest<Doc> request){return v.search(request);}
            public Optional<SearchExplanation<Doc>> explain(SearchRequest<Doc> request,Integer id){return v.explain(request,id);}
            public long currentSequence(){return v.currentSequence();}
        };
    }
    @SuppressWarnings("unchecked") public CompletableFuture<Map<String,Object>> read(Map<String,Object> request) {
        // A separately labelled setup-token call always targets the leader and is
        // excluded from the offered M01 program by the future history validator.
        boolean setup=Boolean.TRUE.equals(request.get("setupToken"));
        ReplicaReadPolicy policy=setup||mode.equals("candidate-explicit-strong")?ReplicaReadPolicy.LEADER_STRONG:
                mode.equals("candidate-stale")?ReplicaReadPolicy.STALE_ALLOWED:ReplicaReadPolicy.AT_LEAST_INDEX;
        Optional<ReplicaReadToken> minimum=policy==ReplicaReadPolicy.AT_LEAST_INDEX?Optional.of(ReplicaReadToken.decode(Base64.getDecoder().decode((String)request.get("minimum")))):Optional.empty();
        var options=new ReplicaReadOptions(policy,minimum,policy==ReplicaReadPolicy.AT_LEAST_INDEX?5000:0);
        return engine.read(options,v->{
            V52MeasurementConsumer.event("CLIENT_CALLBACK_BEGIN",Map.of("opId",request.get("opId"),"sequence",v.currentSequence()));
            try {return V52MeasurementQueries.answer(view(v),(Map<String,Object>)request.get("query"));}
            finally {V52MeasurementConsumer.event("CLIENT_CALLBACK_END",Map.of("opId",request.get("opId"),"sequence",v.currentSequence()));}
        }).thenApply(result->{
            var value=new LinkedHashMap<String,Object>();value.put("answer",result.value());value.put("sequence",result.applicationSequence());
            value.put("policy",result.policy().name());value.put("token",Base64.getEncoder().encodeToString(result.progress().encode()));return value;
        });
    }
}
