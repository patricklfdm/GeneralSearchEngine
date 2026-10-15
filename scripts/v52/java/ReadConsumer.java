package fixture.v52;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import io.github.patricklfdm.generalsearch.replication.*;
import fixture.V52StyleConsumer;

/** External client; no implementation classes or test classes on its classpath. */
public final class ReadConsumer {
    static void check(boolean condition,String message) {if(!condition)throw new AssertionError(message);}
    static void rejected(AutomaticReplicatedSearchEngine engine,boolean legacy) {
        var token=new ReplicaReadToken(1,new ReplicationGroupId(new UUID(1,2)),new UUID(3,4),"ab".repeat(32),0);
        for(var policy:ReplicaReadPolicy.values()) {
            var options=new ReplicaReadOptions(policy,policy==ReplicaReadPolicy.AT_LEAST_INDEX?Optional.of(token):Optional.empty(),0);
            var calls=new AtomicInteger();
            CompletableFuture<?> result=engine.read(options,(Function)(view->{calls.incrementAndGet();return null;}));
            check(result.isCompletedExceptionally(),"default result is not immediately failed");
            try {result.join();throw new AssertionError("enabled explicit read");}
            catch(CompletionException error) {
                check(legacy ? error.getCause() instanceof UnsupportedOperationException :
                        error.getCause() instanceof AutomaticReplicationException e&&e.reason()==AutomaticReplicationException.Reason.NOT_READY,
                        "wrong unsupported/stopped error");
            }
            check(calls.get()==0,"disabled callback executed");
        }
        try {engine.read(null,(Function)(v->null));throw new AssertionError("null options");}catch(NullPointerException expected) { }
        try {engine.read(new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.empty(),0),null);throw new AssertionError("null callback");}catch(NullPointerException expected) { }
        try {new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.of(token),0);throw new AssertionError("unexpected minimum");}catch(IllegalArgumentException expected) { }
        try {new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.empty(),0);throw new AssertionError("missing minimum");}catch(IllegalArgumentException expected) { }
        try {new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(token),60001);throw new AssertionError("unbounded wait");}catch(IllegalArgumentException expected) { }
        check(token.equals(ReplicaReadToken.decode(token.encode())),"token roundtrip");
    }
    public static void main(String[] args) throws Exception {
        rejected((AutomaticReplicatedSearchEngine)Class.forName("fixture.v52.LegacyAutomatic").getConstructor().newInstance(),true);
        // Reuse the independently compiled V5.1 stopped-handle fixture (instrumented codec).
        Path root=Path.of(args[0]);Files.createDirectory(root);
        var configs=V52StyleConsumer.request(root,null).replicas();V52StyleConsumer.CODEC_CALLS.set(0);
        Set<Long> threads=new HashSet<>();Thread.getAllStackTraces().keySet().forEach(t->threads.add(t.threadId()));
        var handle=V52StyleConsumer.stopped(configs.getFirst());
        rejected(handle,false);check(V52StyleConsumer.CODEC_CALLS.get()==0,"stopped read called codec");
        check(Thread.getAllStackTraces().keySet().stream().filter(t->t.getName().contains("gse")).allMatch(t->threads.contains(t.threadId())),"disabled read started runtime thread");
        try(var files=Files.list(root)) {check(files.findAny().isEmpty(),"disabled read created files");}
        handle.close();
        System.out.println("v52ExternalRead=PASS legacyBinary=published-5.1 default=disabled runtimeStarted=false");
    }
}
