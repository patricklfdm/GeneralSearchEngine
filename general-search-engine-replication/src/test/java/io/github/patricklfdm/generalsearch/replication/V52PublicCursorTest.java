package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V52PublicReadTest.*;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Explicit read tokens do not change the lifetime or portability of old opaque cursors. */
class V52PublicCursorTest {
    @TempDir Path root;
    V51PublicRuntimeTest fixture(){var f=new V51PublicRuntimeTest();f.root=root;return f;}

    @Test void oldCursorSurvivesNoOpAndExplicitReadsButRejectsChangedApplication() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.addAll(List.of(new Doc(1,"shared alpha"),new Doc(2,"shared beta"))).join();
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(1).build();
            var first=leader.search(SearchPageRequest.builder(request).build());var cursor=first.nextCursor().orElseThrow();
            long index=leader.leadershipStatus().provenIndex(),sequence=leader.leadershipStatus().applicationSequence();
            var strong=leader.read(STRONG,v->v.currentSequence()).get(10,TimeUnit.SECONDS);
            assertEquals(index+1,strong.progress().index());assertEquals(sequence,strong.value());
            var minimumRead=leader.read(minimum(strong.progress(),0),v->v.get(1)).get(5,TimeUnit.SECONDS);
            assertEquals(strong.progress(),minimumRead.progress());
            assertEquals(new Doc(1,"shared alpha"),leader.read(STALE,v->v.get(1)).get(5,TimeUnit.SECONDS).value());
            var next=leader.search(SearchPageRequest.builder(request).after(cursor).build());
            assertEquals(1,first.hits().size());assertEquals(1,next.hits().size());
            assertEquals(Set.of(1,2),Set.of(first.hits().getFirst().document().id(),next.hits().getFirst().document().id()));
            assertEquals(sequence,leader.leadershipStatus().applicationSequence());
            leader.update(new Doc(1,"shared changed")).join();
            // AutomaticApplication replaces the whole materialization on each
            // application mutation. Control NO_OPs above keep that owner intact.
            assertEquals(SearchCursorException.Reason.DIFFERENT_ENGINE,assertThrows(SearchCursorException.class,
                    ()->leader.search(SearchPageRequest.builder(request).after(cursor).build())).reason());
            leader.update(new Doc(2,"shared changed beta")).join();
            assertEquals(SearchCursorException.Reason.DIFFERENT_ENGINE,assertThrows(SearchCursorException.class,
                    ()->leader.search(SearchPageRequest.builder(request).after(cursor).build())).reason());
            assertEquals("shared changed",leader.read(minimum(strong.progress(),0),v->v.get(1)).get(5,TimeUnit.SECONDS).value().value());
        }
    }

    @Test void oldCursorRejectsAnotherLeaderAndReopenedHandlesWhileTokenStillWorks() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var original=group.leader();original.addAll(List.of(new Doc(1,"shared alpha"),new Doc(2,"shared beta"))).join();
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(1).build();
            var cursor=original.search(SearchPageRequest.builder(request).build()).nextCursor().orElseThrow();
            var token=original.read(STRONG,v->v.currentSequence()).get(10,TimeUnit.SECONDS).progress();
            original.close();group.engines.remove(original);
            var successor=group.leader();assertNotSame(original,successor);
            assertEquals(SearchCursorException.Reason.DIFFERENT_ENGINE,assertThrows(SearchCursorException.class,
                    ()->successor.search(SearchPageRequest.builder(request).after(cursor).build())).reason());
            assertEquals(new Doc(1,"shared alpha"),successor.read(minimum(token,5000),v->v.get(1)).get(10,TimeUnit.SECONDS).value());
            var beforeReopen=successor.search(SearchPageRequest.builder(request).build()).nextCursor().orElseThrow();
            for(var engine:group.engines)engine.close();group.engines.clear();
            for(var config:group.configs) {
                var engine=AutomaticReplicatedSearchEngines.builder(group.app,config).build();group.engines.add(engine);
                engine.start().get(15,TimeUnit.SECONDS);
            }
            var reopened=group.leader();
            assertEquals(SearchCursorException.Reason.DIFFERENT_ENGINE,assertThrows(SearchCursorException.class,
                    ()->reopened.search(SearchPageRequest.builder(request).after(beforeReopen).build())).reason());
            assertEquals(new Doc(1,"shared alpha"),reopened.read(minimum(token,5000),v->v.get(1)).get(10,TimeUnit.SECONDS).value());
        }
    }
}
