package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** The original owned node-2 directory, real TCP prefix acquisition, no copied
 * authority token and no clean close on the selected death path. */
public final class V53JointFloorWorker {
    static final String SCOPE="joint-floor-process";
    static void prepareScratch(Path root)throws IOException {
        Files.createDirectory(AdmissionPaths.safe(root));
        Files.createDirectory(root.resolve("outgoing"));
    }
    private static synchronized void line(String kind,Object value)throws IOException {
        System.out.write(canonical(Map.of("kind",kind,"value",value),16*1024*1024));System.out.write('\n');System.out.flush();
        require(System.in.read()=='a',"joint floor process observation not acknowledged");
    }
    private static List<Map<String,Object>> observations(String kind) {
        return Collections.synchronizedList(new ArrayList<>() {
            @Override public boolean add(Map<String,Object> value) {
                try{line(kind,value);}catch(IOException error){throw new UncheckedIOException(error);}return super.add(value);
            }
        });
    }
    public static void main(String[] args)throws Exception {
        require(args.length==1,"joint floor worker spec argument");
        var spec=V53JointFloorProcess.Spec.read(AdmissionPaths.read(Path.of(args[0]),16384));
        long pid=ProcessHandle.current().pid();line("STARTED",Map.of("mode",spec.mode(),"pid",pid));
        prepareScratch(spec.scratch());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        var trace=new V53JoiningTrace(spec.identity().nodeId().value(),observations("EVENT"),observations("WIRE"));
        var ordinal=new AtomicInteger();
        MembershipBallotAllocator.Cut cut=event->{
            trace.cut(SCOPE).at(event);
            line("USAGE",Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(resources)));
            if(event.equals("FLOOR_COPY_CREATED"))ordinal.incrementAndGet();
            if(ordinal.get()==spec.cut().ordinal() && event.equals(spec.cut().point())) {
                line("CUT",Map.of("mode",spec.mode(),"pid",pid,"ordinal",ordinal.get(),"point",event));
                if(spec.mode().equals("halt"))Runtime.getRuntime().halt(73);
                try{new CountDownLatch(1).await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
            }
        };
        try(var owner=MembershipGrantJournal.openRetainingFuturePeers(spec.replica(),spec.application(),spec.root(),spec.identity(),
                resources,MembershipGrantJournal.MAXIMUM,cut)) {
            line("OPENED",Map.of("pid",pid,"replica",spec.replica().toString(),"application",spec.application().toString()));
            var bounds=new V53RoundDriverTest().controlBounds();var link=new AtomicReference<MembershipTransport>();
            try(var endpoint=new MembershipActivationEndpoint(owner,resources,bounds,
                    (peer,q,kind,deadline)->link.get().exchange(peer,q,kind,deadline),List.of(),List.of(),
                    spec.scratch().resolve("incoming"),System::nanoTime,V53JointFloorRecoveryTest.BUDGET,builder().configuration(),storage(spec.application(),2));
                var transport=new MembershipTransport(owner,bounds,resources,endpoint::handle,trace.transport(SCOPE))) {
                link.set(transport);
                try(var maintenance=MembershipGenerationMaintenance.beforeGrant(owner,resources,bounds,transport::exchange,()->{},
                        spec.scratch().resolve("outgoing"),System::nanoTime,spec.startedNanos(),V53JointFloorRecoveryTest.BUDGET)) {
                    maintenance.run();
                }
            }
        }
        throw new IllegalStateException("joint floor process cut not reached");
    }
}
