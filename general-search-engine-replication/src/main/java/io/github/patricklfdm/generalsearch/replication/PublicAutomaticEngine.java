package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.schema.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

/** Pure stopped handle, bounded ordered admission and per-call quorum reads. */
final class PublicAutomaticEngine<K,T> implements AutomaticReplicatedSearchEngine<K,T> {
    private final SearchEngineConfiguration<K,T> application;
    private final AutomaticReplicationGroupConfig<K,T> config;
    private final Semaphore admission;
    private final ThreadPoolExecutor ordered;
    private final ExecutorService completions;
    private final ScheduledThreadPoolExecutor deadlines;
    private final Object lifecycle=new Object(), closingLock=new Object();
    private volatile AutomaticRuntime<K,T> node;
    private volatile AutomaticReplicationState state=AutomaticReplicationState.STOPPED;
    private volatile boolean closing;
    private CompletableFuture<AutomaticReplicationStatus> starting;
    private Thread starter;

    PublicAutomaticEngine(SearchEngineConfiguration<K,T> application,AutomaticReplicationGroupConfig<K,T> config) {
        this.application=application;this.config=config;
        AutomaticBootstrap.guarded(()->{AdmissionConfiguration.application(application);return null;});
        var replica=config.replicaDirectory().toAbsolutePath().normalize();
        var materialization=config.materialization().directory().toAbsolutePath().normalize();
        if(replica.startsWith(materialization)||materialization.startsWith(replica))throw error(STORAGE_FAILURE,NOT_APPLICABLE);
        int bound=config.bounds().maxPendingClientOperations();admission=new Semaphore(bound);
        ordered=pool("ordered",1,bound);
        // Each completion still owns an admission permit: at most bound virtual threads,
        // including blocked callbacks. Fixed completion workers can deadlock on nested calls.
        completions=Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("gse-automatic-public-completion-",0).factory());
        deadlines=new ScheduledThreadPoolExecutor(1,task->thread("deadline",task));deadlines.setRemoveOnCancelPolicy(true);
        // Executor construction starts no thread and invokes no codec or filesystem operation.
    }
    private Thread thread(String name,Runnable task) {return Thread.ofPlatform().daemon().name("gse-automatic-public-"+name+"-"+config.localNodeId().value()).unstarted(task);}
    private ThreadPoolExecutor pool(String name,int workers,int capacity) {
        return new ThreadPoolExecutor(workers,workers,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(capacity),task->thread(name,task));
    }
    private AutomaticReplicationException error(AutomaticReplicationException.Reason reason,AutomaticReplicationException.Outcome outcome) {
        var value=node;
        return new AutomaticReplicationException(reason,outcome,value==null?Optional.empty():value.status().observedLeader(),"automatic application "+reason);
    }
    private void context(AutomaticReplicationException.Outcome outcome) {
        if(AutomaticContext.active(this))throw error(REENTRANT_CALL,outcome);
    }
    @Override public CompletableFuture<AutomaticReplicationStatus> start() {
        try {
            context(NOT_APPLICABLE);
            synchronized(lifecycle) {
                if(closing)throw error(CLOSED,NOT_APPLICABLE);
                if(starting==null) {
                    starting=new CompletableFuture<>();state=AutomaticReplicationState.STARTING;
                    starter=thread("start",this::open);starter.start();
                }
                return starting.copy();
            }
        } catch(RuntimeException error){return CompletableFuture.failedFuture(error);}
    }
    private void open() {
        try {
            var hooks=AutomaticRuntimeHooks.CURRENT.get();
            var opened=AutomaticContext.call(this,()->AutomaticBootstrap.guarded(()->{
                if(closing)throw error(CLOSED,NOT_APPLICABLE);
                byte[] manifest=AdmissionPaths.read(config.replicaDirectory().resolve("manifest.gsr"),AutomaticRecords.META);
                return new AutomaticRuntime<>(config,application,manifest,hooks.storage(),hooks.network(),hooks.events(),this);
            }));
            node=opened;
            var status=await(opened.started(),deadline(),NOT_APPLICABLE);
            synchronized(lifecycle) {
                if(closing)throw error(CLOSED,NOT_APPLICABLE);
                state=AutomaticReplicationState.FOLLOWER;
            }
            starting.complete(status); // No lifecycle lock or codec scope is held during caller callbacks.
        } catch(Throwable failed) {
            try {if(node!=null)node.close();}catch(Throwable cleanup){failed.addSuppressed(cleanup);}
            state=closing?AutomaticReplicationState.CLOSED:AutomaticReplicationState.FAILED;
            starting.completeExceptionally(classify(failed,NOT_APPLICABLE));
        }
    }
    private long deadline() {return System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(config.leadershipPolicy().operationTimeoutMillis());}
    private AutomaticRuntime<K,T> available(boolean leader,AutomaticReplicationException.Outcome outcome) {
        if(closing)throw error(CLOSED,outcome);
        var value=node;
        if(value==null||state!=AutomaticReplicationState.FOLLOWER)throw error(NOT_READY,outcome);
        var status=value.status();
        if(value.failure()!=null||status.state()==AutomaticReplicationState.FAILED)throw error(STORAGE_FAILURE,outcome);
        if(leader&&status.state()!=AutomaticReplicationState.LEADER_READY) {
            throw error(status.state()==AutomaticReplicationState.FOLLOWER?NOT_LEADER:
                    status.state()==AutomaticReplicationState.UNAVAILABLE?QUORUM_UNAVAILABLE:NOT_READY,outcome);
        }
        return value;
    }
    private RuntimeException classify(Throwable failure,AutomaticReplicationException.Outcome outcome) {
        while((failure instanceof CompletionException||failure instanceof ExecutionException)&&failure.getCause()!=null)failure=failure.getCause();
        if(failure instanceof AutomaticReplicationException auto) {
            if(outcome==NOT_APPLICABLE&&auto.outcome()!=NOT_APPLICABLE)
                return new AutomaticReplicationException(auto.reason(),NOT_APPLICABLE,auto.observedLeader(),auto.getMessage(),auto);
            return auto;
        }
        if(failure instanceof ReplicationException old) {
            AutomaticReplicationException.Reason reason;
            try {reason=AutomaticReplicationException.Reason.valueOf(old.reason().name());}catch(IllegalArgumentException ignored){reason=STORAGE_FAILURE;}
            return new AutomaticReplicationException(reason,outcome,Optional.empty(),old.getMessage(),old);
        }
        if(failure instanceof RuntimeException runtime)return runtime;
        return new AutomaticReplicationException(STORAGE_FAILURE,outcome,Optional.empty(),"automatic application failure",failure);
    }
    private <R> R await(CompletableFuture<R> result,long until,AutomaticReplicationException.Outcome timeoutOutcome) {
        try {return result.get(Math.max(0,until-System.nanoTime()),TimeUnit.NANOSECONDS);}
        catch(TimeoutException failure){throw error(DEADLINE_EXCEEDED,timeoutOutcome);}
        catch(InterruptedException failure){Thread.currentThread().interrupt();throw error(DEADLINE_EXCEEDED,timeoutOutcome);}
        catch(ExecutionException failure){throw classify(failure,timeoutOutcome);}
    }
    private <R> R join(CompletableFuture<R> result) {
        try {return result.join();}catch(CompletionException failure){throw classify(failure,NOT_APPLICABLE);}
    }
    private interface Work<R> {R run(long deadline);}
    private final class Request<R> implements Runnable {
        final CompletableFuture<R> result=new CompletableFuture<>();
        final AtomicInteger phase=new AtomicInteger(); // queued, running, settled
        final Work<R> work;
        final boolean mutation,leader;
        final long until=deadline();
        volatile Future<?> alarm;
        Request(boolean mutation,boolean leader,Work<R> work) {this.mutation=mutation;this.leader=leader;this.work=work;}
        AutomaticReplicationException.Outcome unsubmitted() {return mutation?NOT_SUBMITTED:NOT_APPLICABLE;}
        void queuedFailure(AutomaticReplicationException.Reason reason) {
            if(phase.compareAndSet(0,2)) {ordered.remove(this);if(alarm!=null)alarm.cancel(false);finish(null,error(reason,unsubmitted()));}
        }
        void finish(R value,Throwable failure) {
            // Keep one bounded permit until user completion callbacks have returned.
            completions.execute(()->{try {if(failure==null)result.complete(value);else result.completeExceptionally(failure);}finally{admission.release();}});
        }
        @Override public void run() {
            if(!phase.compareAndSet(0,1))return;
            if(alarm!=null)alarm.cancel(false);
            R value=null;Throwable failure=null;
            try {
                if(result.isCancelled())throw error(NOT_READY,unsubmitted());
                if(System.nanoTime()>=until)throw error(DEADLINE_EXCEEDED,unsubmitted());
                available(leader,unsubmitted());value=work.run(until);
            } catch(Throwable e){failure=classify(e,mutation?INDETERMINATE:NOT_APPLICABLE);}
            phase.set(2);finish(value,failure);
        }
    }
    private <R> CompletableFuture<R> enqueue(boolean mutation,boolean leader,Work<R> work) {
        try {
            var outcome=mutation?NOT_SUBMITTED:NOT_APPLICABLE;context(outcome);available(leader,outcome);
            synchronized(lifecycle) {
                if(closing)throw error(CLOSED,outcome);
                if(!admission.tryAcquire())throw error(CAPACITY_EXCEEDED,outcome);
                var request=new Request<R>(mutation,leader,work);
                try {
                    request.alarm=deadlines.schedule(()->request.queuedFailure(DEADLINE_EXCEEDED),Math.max(0,request.until-System.nanoTime()),TimeUnit.NANOSECONDS);
                    ordered.execute(request);
                    request.result.whenComplete((v,e)->{if(request.result.isCancelled())request.queuedFailure(NOT_READY);});
                    return request.result;
                } catch(RejectedExecutionException failed){request.queuedFailure(CLOSED);return request.result;}
            }
        } catch(RuntimeException error){return CompletableFuture.failedFuture(error);}
    }
    private CompletableFuture<Void> mutate(String operation,Function<ReplicaApplication<K,T>,byte[]> encoder) {
        return enqueue(true,true,until->{
            var submitted=available(true,NOT_SUBMITTED).submit(ReplicaEntry.OPERATIONS.indexOf(operation)+1,encoder);
            try {await(submitted,until,INDETERMINATE);return null;}
            catch(RuntimeException error){submitted.cancel(false);throw error;}
        });
    }
    private <R> R capture(long until,Function<AutomaticApplication<K,T>,R> action) {
        var value=available(true,NOT_APPLICABLE);long epoch=value.status().promisedEpoch();
        var barrier=value.submit(9,app->new byte[0]);long cut;
        try {cut=await(barrier,until,NOT_APPLICABLE);}catch(RuntimeException error){barrier.cancel(false);throw error;}
        var captured=value.capture(epoch,cut,until,action);
        try {await(captured.begun(),until,NOT_APPLICABLE);}catch(RuntimeException error){captured.result().cancel(false);throw error;}
        // The deadline bounds admission/barrier/capture. An active user query is cooperative.
        return join(captured.result());
    }
    private <R> R strong(Function<AutomaticApplication<K,T>,R> action) {
        context(NOT_APPLICABLE);return join(enqueue(false,true,until->capture(until,action)));
    }
    @Override public CompletableFuture<Void> add(T document) { return mutate("ADD", app -> app.documents("ADD", List.of(document))); }
    @Override public CompletableFuture<Void> update(T document) { return mutate("UPDATE", app -> app.documents("UPDATE", List.of(document))); }
    @Override public CompletableFuture<Void> remove(K id) { return mutate("REMOVE", app -> app.keys("REMOVE", List.of(id))); }
    @Override public CompletableFuture<Void> addAll(Collection<? extends T> documents) { return mutate("ADD_ALL", app -> app.documents("ADD_ALL", documents)); }
    @Override public CompletableFuture<Void> updateAll(Collection<? extends T> documents) { return mutate("UPDATE_ALL", app -> app.documents("UPDATE_ALL", documents)); }
    @Override public CompletableFuture<Void> removeAll(Collection<? extends K> ids) { return mutate("REMOVE_ALL", app -> app.keys("REMOVE_ALL", ids)); }
    @Override public CompletableFuture<Void> createIndex(IndexDefinition<T> definition) { return mutate("INDEX_CREATE", app -> app.index(definition)); }
    @Override public CompletableFuture<Void> dropIndex(String fieldName) { return mutate("INDEX_DROP", app -> app.dropIndex(fieldName)); }
    private <R> R read(Function<SearchEngine<K, T>, R> action) { return strong(app -> app.readLocal(action)); }
    @Override public T get(K id) { return read(engine -> engine.get(id)); }
    @Override public List<T> search(Query<T> query) { return read(engine -> engine.search(query)); }
    @Override public List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request) { return read(engine -> engine.searchTopK(request)); }
    @Override public SearchResult<T> search(SearchRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public SearchPageResult<T> search(SearchPageRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public HighlightedSearchResult<T> search(HighlightedSearchRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id) { return read(engine -> engine.explain(request, id)); }
    @Override public SearchEngineMetrics metrics() { return read(SearchEngine::metrics); }
    @Override public long currentSequence() { return strong(AutomaticApplication::sequence); }
    @Override public SearchSchema<T, K> schema() { return application.schema(); }
    @Override public Field<T, ?> field(String name) { return schema().requireField(name); }
    @Override public <V> Field<T, V> field(String name, Class<V> valueType) { return schema().requireField(name, valueType); }
    @Override public TextField<T> textField(String name) { return schema().requireTextField(name); }

    @Override public CompletableFuture<Void> checkpoint() {
        return enqueue(false,false,until->{await(available(false,NOT_APPLICABLE).checkpoint(until),until,NOT_APPLICABLE);return null;});
    }
    @Override public CompletableFuture<DurableBackupResult> backup(DurableBackupRequest request) {
        return enqueue(false,true,until->capture(until,app->{validateBackupTarget(request,app.sequence());return app.encoder().backup(AdmissionFormat.history(config.groupId().value()),request);}));
    }
    private void validateBackupTarget(DurableBackupRequest request,long sequence) {
        var target = java.util.Objects.requireNonNull(request, "request").targetDirectory().toAbsolutePath().normalize();
        // Preserve the core TARGET_EXISTS result for an occupied target. An absent child must not add unknown authority members.
        if (java.nio.file.Files.exists(target, java.nio.file.LinkOption.NOFOLLOW_LINKS)) return;
        try {
            for (java.nio.file.Path ancestor = target.getParent(); ancestor != null; ancestor = ancestor.getParent()) {
                if (java.nio.file.Files.exists(ancestor, java.nio.file.LinkOption.NOFOLLOW_LINKS)
                        && java.nio.file.Files.isSameFile(ancestor, config.replicaDirectory()))
                    throw new DurableOperationException(DurableOperationException.Reason.TARGET_INVALID,
                            java.util.OptionalLong.of(sequence), null);
            }
        } catch (java.io.IOException error) {
            throw new DurableOperationException(DurableOperationException.Reason.IO_FAILURE,
                    java.util.OptionalLong.of(sequence), error);
        }
    }
    private DurabilityMetrics diagnostics() {
        var value=node;
        if(value==null||value.durability()==null)throw error(state==AutomaticReplicationState.FAILED?STORAGE_FAILURE:NOT_READY,NOT_APPLICABLE);
        var metrics=value.durability();
        var local=state==AutomaticReplicationState.CLOSED?DurabilityStatus.CLOSED:
                state==AutomaticReplicationState.FAILED||value.failure()!=null||value.status().state()==AutomaticReplicationState.FAILED?DurabilityStatus.FAILED:metrics.status();
        return new DurabilityMetrics(local,metrics.currentSequence(),metrics.checkpointSequence(),metrics.walGeneration(),metrics.walRecords(),metrics.walBytes(),
                metrics.retainedBytes(),metrics.recoverySource(),metrics.replayedRecords(),metrics.recoveryDuration(),metrics.indexRebuildDuration(),metrics.lastCheckpointFailure());
    }
    @Override public DurabilityMetrics durabilityMetrics() {return diagnostics();}
    @Override public Optional<DurableReopenReport> lastReopenReport() {if(diagnostics().status()==DurabilityStatus.FAILED)throw error(STORAGE_FAILURE,NOT_APPLICABLE);return Optional.empty();}
    @Override public AutomaticReplicationStatus leadershipStatus() {
        var value=node;var local=state;
        if(value==null) {
            var peers=config.members().stream().filter(m->!m.nodeId().equals(config.localNodeId())).map(m->new ReplicationPeerStatus(m.nodeId(),false,0,0,0,Optional.empty())).toList();
            return new AutomaticReplicationStatus(config.localNodeId(),local,Optional.empty(),Optional.empty(),0,new UUID(0,0),0,0,0,0,0,Optional.empty(),peers);
        }
        var status=value.status();
        if(local==AutomaticReplicationState.FOLLOWER)local=value.failure()!=null?AutomaticReplicationState.FAILED:status.state();
        if(closing&&local!=AutomaticReplicationState.CLOSED)local=AutomaticReplicationState.UNAVAILABLE;
        return new AutomaticReplicationStatus(status.localNodeId(),local,status.observedLeader(),status.promisedLeader(),status.promisedEpoch(),status.promisedIncarnation(),
                local==AutomaticReplicationState.LEADER_READY?status.activeEpoch():0,status.provenIndex(),status.appliedIndex(),status.applicationSequence(),
                config.bounds().maxPendingClientOperations()-admission.availablePermits(),status.lastQuorumSuccess(),status.peers());
    }
    @Override public void close() {
        context(NOT_APPLICABLE);
        synchronized(closingLock) {
            if(state==AutomaticReplicationState.CLOSED&&node==null)return;
            Thread opening;
            synchronized(lifecycle) {
                closing=true;opening=starter;
                for(Runnable queued:ordered.getQueue().toArray(Runnable[]::new)) {
                    @SuppressWarnings("unchecked") var request=(Request<Object>)queued;request.queuedFailure(CLOSED);
                }
                ordered.shutdown();deadlines.shutdownNow();
            }
            try {
                long wait=config.bounds().requestTimeoutMillis()+100L;
                if(opening!=null&&opening!=Thread.currentThread()){opening.join(wait);if(opening.isAlive())throw error(DEADLINE_EXCEEDED,NOT_APPLICABLE);}
                if(!deadlines.awaitTermination(wait,TimeUnit.MILLISECONDS)||!ordered.awaitTermination(wait,TimeUnit.MILLISECONDS))throw error(DEADLINE_EXCEEDED,NOT_APPLICABLE);
                if(node!=null)node.close();
                state=AutomaticReplicationState.CLOSED;completions.shutdown();
            } catch(InterruptedException failure){Thread.currentThread().interrupt();throw error(DEADLINE_EXCEEDED,NOT_APPLICABLE);}
        }
    }
}
