package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticProtocol.Kind.*;
import java.nio.file.*;
import java.util.*;

/** A fresh JVM per scenario, three real stores, deterministic typed delivery; no sockets. */
public final class V51ProtocolWorker {
    private V51ProtocolWorker() { }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);String scenario=args[1];
        var result=new LinkedHashMap<String,Object>();
        try(var group=new V51ProtocolFixture(root)) {
            result.put("schema","gse-v51-protocol-case-v1");result.put("scenario",scenario);
            result.put("execution","automatic-transition-kernel-only");result.put("publicRuntime",false);
            result.put("trace",group.trace);
            group.elect(1);
            switch(scenario) {
                case "healthy" -> {group.submit(1,1,new byte[]{31});group.advance(60_000);}
                case "entry-chosen", "hidden-proof" -> {
                    var kind=scenario.equals("entry-chosen")?ACCEPT:PROOF;
                    group.loss=m->m.response()&&m.kind()==kind;group.submit(1,2,new byte[]{73});
                    group.stop(1);group.loss=m->false;group.elect(3);
                }
                case "fenced" -> {
                    group.loss=m->m.response()&&m.kind()==ACCEPT&&m.recipient().equals("node-1");group.submit(1,3,new byte[]{91});
                    var late=group.dropped.getLast();group.now=31_000;group.node(2).tick(group.now);group.pump();
                    group.loss=m->false;group.deliver(late);group.pump();
                }
                case "retry" -> {
                    for(var kind:List.of(ACCEPT,PROOF)) {
                        group.loss=m->m.response()&&m.kind()==kind;group.submit(1,kind.ordinal()+10,new byte[]{55});
                        var lost=group.dropped.getLast();group.loss=m->false;group.node(1).transportFailed(lost.id(),group.now);
                        group.now+=250;group.node(1).tick(group.now);group.pump();
                    }
                }
                case "restart" -> {group.stop(1);group.open(1,AutomaticStore.Faults.NONE);group.pump();group.elect(1);}
                default -> throw new IllegalArgumentException(scenario);
            }
            var views=new ArrayList<Object>();
            for(var item:group.nodes.entrySet()) {
                var view=item.getValue().view();views.add(Map.of("node",item.getKey(),"state",view.state().name(),"promisedEpoch",view.promisedEpoch(),
                        "provenIndex",view.provenIndex(),"publishedIndex",view.publishedIndex()));
            }
            result.put("views",views);
        } finally {Files.write(root.resolve("trace.json"),canonical(result));}
        System.out.println(new String(canonical(Map.of("scenario",scenario,"status","RECORDED")),java.nio.charset.StandardCharsets.US_ASCII));
    }
}
