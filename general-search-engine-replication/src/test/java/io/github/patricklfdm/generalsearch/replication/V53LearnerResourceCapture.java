package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only checkpoints of the actual admitted learner pool. A caller may set
 * a cold pool's limit before opening; no live limits or charges are rewritten. */
final class V53LearnerResourceCapture {
    final Path directory;
    final MembershipResources resources;
    final List<Map<String,Object>> rows=new ArrayList<>();
    V53LearnerResourceCapture(Path directory)throws IOException {
        this(directory,512*MembershipResources.MIB);
    }
    V53LearnerResourceCapture(Path directory,long stagingLimit)throws IOException {
        resources=new MembershipResources(MembershipResources.METADATA_LIMIT,stagingLimit,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
        this.directory=Files.createDirectory(directory);mark("POOL","start","");
    }
    synchronized void mark(String kind,String name,String point) {
        require(rows.size()<4096,"learner resource boundary capacity");
        var checkpoint=resources.observationCheckpoint();require(checkpoint.complete(),"learner resource complete checkpoint");
        rows.add(Map.of("ordinal",rows.size(),"kind",kind,"name",name,"point",point,
                "sequence",checkpoint.sequence(),"usage",V53ResourceTraceFiles.usage(checkpoint.usage())));
    }
    static MembershipBallotAllocator.Cut events(V53LearnerResourceCapture capture,List<String> events,String phase) {
        return point->{events.add(point);if(capture!=null)capture.mark("CALLBACK",phase,point);};
    }
    static void stage(V53LearnerResourceCapture capture,String name) {if(capture!=null)capture.mark("SNAPSHOT",name,"");}
    static <T extends AutoCloseable> Owner<T> own(V53LearnerResourceCapture capture,String name,T value) {
        return new Owner<>(capture,name,value);
    }
    static final class Owner<T extends AutoCloseable> implements AutoCloseable {
        final V53LearnerResourceCapture capture;final String name;final T value;
        Owner(V53LearnerResourceCapture capture,String name,T value){this.capture=capture;this.name=name;this.value=value;}
        @Override public void close()throws Exception {
            if(capture!=null)capture.mark("CLOSE_BEGIN",name,"");
            value.close(); // A failed close has no successful return marker.
            if(capture!=null)capture.mark("CLOSE_RETURN",name,"");
        }
    }
    void finish(Path original,boolean success)throws IOException {
        V53ResourceTraceFiles.write(directory.resolve("trace.json"),resources.observations());
        Files.write(directory.resolve("boundaries.json"),canonical(rows,4*1024*1024),StandardOpenOption.CREATE_NEW);
        Path plan=original==null?null:original.resolve("learner-plan.gslp");
        Files.write(directory.resolve("index.json"),canonical(Map.of("schema","gse-v53-native-learner-resources-v1",
                "status",success?"PARTIAL":"FAIL","pid",ProcessHandle.current().pid(),
                "planSha256",plan!=null&&Files.exists(plan)?hash(Files.readAllBytes(plan)):"",
                "wholeRuntimeResourcesQualified",false,"phase3Complete",false),65536),StandardOpenOption.CREATE_NEW);
    }
}
