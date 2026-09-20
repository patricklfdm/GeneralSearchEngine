package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import java.util.*;
import java.util.function.Function;

/** Single application-worker port; two current engines plus at most two staged engines. */
final class AutomaticApplication<K,T> implements AutoCloseable {
    private final ReplicaApplication<K,T> current;
    private final String schemaDigest;
    private ReplicaApplication<K,T> staged;
    private long stagedIndex=-1;
    private byte[] reconstructed;
    private long reconstructedIndex=-1;

    AutomaticApplication(SearchEngineConfiguration<K,T> captured,DurableStorageConfig<K,T> config,ReplicationBounds bounds) {
        current=new ReplicaApplication<>(captured,config,bounds);
        schemaDigest=schemaDigest(captured,config);
    }
    static String schemaDigest(SearchEngineConfiguration<?,?> captured,DurableStorageConfig<?,?> config) {
        return sha(canonical(Map.of("schemaIdentity",config.schemaIdentity(),"application",AdmissionConfiguration.application(captured))));
    }
    void validate(Record manifest,DurableStorageConfig<K,T> config) {
        need(manifest.value().get("codecId").equals(config.codec().codecId())&&number(manifest.value(),"codecVersion")==config.codec().codecVersion()
                &&manifest.value().get("schemaDigest").equals(schemaDigest)
                &&manifest.value().get("indexesDigest").equals(current.indexDigest()),"automatic application identities");
    }
    ReplicaApplication<K,T> encoder() {return current;}
    <R> R readLocal(Function<SearchEngine<K,T>,R> action) {return current.read(action);}
    long index() {return current.appliedIndex();}
    long sequence() {return current.sequence();}
    private void discard() {if(staged!=null)staged.close();staged=null;stagedIndex=-1;}
    /** Business validation must finish before the runtime dispatches an acceptance. */
    void stage(int operation,byte[] payload) {
        discard();staged=current.rebuildApplication(current.snapshot(),current.appliedIndex(),current.sequence());
        try {staged.prepare(ReplicaEntry.OPERATIONS.get(operation-1),payload);staged.publish(current.appliedIndex()+1);stagedIndex=staged.appliedIndex();}
        catch(RuntimeException|Error error) {discard();throw error;}
    }
    byte[] reconstruct(AutomaticStore.Replay replay) {
        // Publication and opaque command decoding use V4's existing canonical application path.
        discard();var snapshot=replay.snapshot();
        staged=current.rebuildApplication(unbase(snapshot.value().get("application")),AutomaticRecovery.index(snapshot),number(snapshot.value(),"applicationSequence"));
        try {
            for(Record entry:replay.entries()) {
                staged.prepare(ReplicaEntry.OPERATIONS.get((int)number(entry.value(),"operation")-1),unbase(entry.value().get("payload")));
                staged.publish(number(entry.value(),"index"));
            }
            need(staged.appliedIndex()==replay.through()&&staged.sequence()==replay.sequence(),"application replay cut/sequence");
            stagedIndex=staged.appliedIndex();reconstructed=staged.snapshot();reconstructedIndex=stagedIndex;
            return reconstructed.clone();
        } catch(RuntimeException|Error error) {discard();throw error;}
    }
    void publish(Record snapshot) {
        long index=AutomaticRecovery.index(snapshot),sequence=number(snapshot.value(),"applicationSequence");
        byte[] bytes=unbase(snapshot.value().get("application"));
        need(index==reconstructedIndex&&Arrays.equals(bytes,reconstructed)&&staged!=null&&stagedIndex==index,"publication reconstructed image");
        if(sequence==current.sequence()&&Arrays.equals(bytes,current.snapshot())&&index>=current.appliedIndex()) {
            // Control cuts preserve the live search snapshot/cursors.
            while(current.appliedIndex()<index) {current.prepare("NO_OP",new byte[0]);current.publish(current.appliedIndex()+1);}
            discard();
        } else {current.replaceWith(staged);staged=null;stagedIndex=-1;}
        need(current.appliedIndex()==index&&current.sequence()==sequence,"published application cut");
    }
    @Override public void close() {discard();current.close();}
}
