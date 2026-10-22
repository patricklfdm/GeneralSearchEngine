package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Private deterministic application projection. Certificates/catalog and publication belong to the owner. */
final class MembershipApplicationReplay {
    private MembershipApplicationReplay() { }
    record Step(long index,String kind,byte[] payload) {
        Step {position(index);Objects.requireNonNull(kind);Objects.requireNonNull(payload);require(payload.length<=MembershipFormat.FRAME,"application command capacity");payload=payload.clone();}
        @Override public byte[] payload(){return payload.clone();}
    }
    record Result(long index,long sequence,byte[] image) {
        Result {position(index);position(sequence);require(image.length>0 && image.length<=MembershipApplicationImage.MAXIMUM,"application result capacity");image=image.clone();}
        @Override public byte[] image(){return image.clone();}
    }
    static byte[] data(String operation,byte[] body) {
        int code=ReplicaEntry.OPERATIONS.indexOf(operation)+1;
        require(code>=1 && code<=8 && body.length<MembershipFormat.FRAME,"membership DATA operation/capacity");
        byte[] result=new byte[body.length+1];result[0]=(byte)code;System.arraycopy(body,0,result,1,body.length);return result;
    }
    static <K,T> Result replay(SearchEngineConfiguration<K,T> captured,DurableStorageConfig<K,T> storage,
            byte[] original,String digest,UUID history,long sequence,long index,List<Step> requested,Path scratch)throws IOException {
        position(index);position(sequence);uuid(history);MembershipValidation.digest(digest);
        require(original.length>=MembershipApplicationImage.OVERHEAD && original.length<=MembershipApplicationImage.MAXIMUM,"application original capacity");
        require(MembershipFormat.hash(original).equals(digest),"application original digest");
        require(requested.size()<=10_000,"application replay count");var steps=List.copyOf(requested);require(steps.size()<=10_000,"application replay count");long bytes=0,next=index;
        for(var step:steps) {
            require(next<MAX && step.index()==++next,"application replay contiguous index");
            byte[] payload=step.payload();bytes+=payload.length;
            require(bytes<=MembershipResources.Unit.JOURNAL.bytes,"application replay byte capacity");
            MembershipFormat.command(step.kind(),payload);
            if(step.kind().equals("DATA"))require(payload.length>1 && Byte.toUnsignedInt(payload[0])>=1 && Byte.toUnsignedInt(payload[0])<=8,"membership DATA opcode");
        }
        AdmissionPaths.disjoint(List.of(storage.directory(),scratch));AdmissionPaths.absent(scratch);
        var parent=AdmissionPaths.binding(scratch);Files.createDirectory(scratch);AdmissionPaths.recheck(parent);
        var state=MembershipApplicationImage.read(captured,storage,original,scratch.resolve("input"));
        require(state.history().equals(history) && state.sequence()==sequence,"application original history/sequence");
        if(steps.isEmpty())return new Result(index,sequence,original);
        var active=new SearchEngineConfiguration<>(captured.schema(),state.indexes(),captured.config(),captured.plannerConfig());
        byte[] legacy=AdmissionBootstrap.application(active,state.documents(),storage,MembershipApplicationImage.MAXIMUM);
        // Internal serializer allowance only. The 1.3 DATA/frame cap is checked separately above.
        var d=ReplicationBounds.defaults();var bounds=new ReplicationBounds(12*1024*1024,d.maxEntriesPerAppend(),d.maxInFlightPerPeer(),d.maxPendingClientOperations(),
                d.maxRetryAttempts(),d.requestTimeoutMillis(),d.retryBackoffMillis(),d.snapshotChunkBytes(),d.maxRetainedLogBytes(),d.maxSnapshotStagingBytes());
        boolean changed=false;
        try(var empty=new ReplicaApplication<>(captured,storage,bounds);
                var application=empty.rebuildApplication(legacy,index,sequence)) {
            for(var step:steps) {
                if(step.kind().equals("DATA")) {
                    require(application.sequence()<MAX,"application sequence capacity");byte[] payload=step.payload();
                    application.prepare(ReplicaEntry.OPERATIONS.get(Byte.toUnsignedInt(payload[0])-1),Arrays.copyOfRange(payload,1,payload.length));changed=true;
                }else application.prepare("NO_OP",new byte[0]);
                application.publish(step.index()); // Private engine only; there is no runtime/public reader.
            }
            if(!changed)return new Result(application.appliedIndex(),application.sequence(),original);
            var exported=application.applicationState(history);
            // A new DATA result uses canonical active field order, independent of the recovery base.
            var ordered=exported.indexes().stream().sorted(Comparator.comparing(v->v.field().name())).toList();
            var result=new DurableApplicationState<>(history,exported.sequence(),exported.documents(),ordered);
            byte[] image=MembershipApplicationImage.capture(captured,storage,result,scratch.resolve("output"));
            return new Result(application.appliedIndex(),application.sequence(),image);
        }
    }
}
