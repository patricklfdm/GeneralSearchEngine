package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static org.junit.jupiter.api.Assertions.*;

/** Fresh process, original joined locks and actual TCP retention acquisition. */
public final class V53JoiningInitializationWorker {
    private static V53ProcessTrace trace;
    private static synchronized void line(String kind,Object value) {
        var row=Map.<String,Object>of("kind",kind,"value",value);trace.add(row);
        System.out.println(new String(canonical(row,16*1024*1024),java.nio.charset.StandardCharsets.UTF_8));System.out.flush();
    }
    private static List<Map<String,Object>> observations(String kind) {
        return Collections.synchronizedList(new ArrayList<>() {
            @Override public boolean add(Map<String,Object> value){line(kind,value);return super.add(value);}
        });
    }
    public static void main(String[] args)throws Exception {
        require(args.length==5,"joining worker arguments");String mode=args[2],point=args[3];
        require(Set.of("halt","kill","resume").contains(mode) && V53JoiningInitializationProcess.points().contains(point),"joining worker case");
        var spec=V53JoiningInitializationProcess.Spec.read(AdmissionPaths.read(Path.of(args[0]),16384));
        trace=new V53ProcessTrace(Path.of(args[1]),mode,false);
        line("STARTED",Map.of("mode",mode,"pid",ProcessHandle.current().pid()));
        var request=spec.plan().request();var bounds=new V53RoundDriverTest().controlBounds();
        var config=new MembershipReplicaConfig<>(request.root(),request.identity(),List.of(),request.replicaDirectory(),storage(spec.application(),2),
            bounds,AutomaticLeadershipPolicy.forBounds(bounds));
        var resources=new MembershipResources(512*MembershipResources.MIB);
        var observed=new V53JoiningTrace(request.identity().nodeId().value(),observations("EVENT"),observations("WIRE"));
        MembershipBallotAllocator.Cut cut=event->{
            observed.cut("initialization-"+mode).at(event);
            if(!mode.equals("resume") && event.equals(point)) {
                line("CUT",Map.of("point",point,"mode",mode,"pid",ProcessHandle.current().pid()));
                require(System.in.read()=='c',"joining cut requires live-lock observation");
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                try{new CountDownLatch(1).await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        };
        // Resume must retain the original decision, including an incomplete
        // seed prefix. Missing or changed originals never fall back to genesis.
        try(var owner=mode.equals("resume")?
                MembershipGrantJournal.reopenJoinedRetaining(spec.plan(),resources,builder().configuration(),config,cut):
                MembershipGrantJournal.reopenJoined(spec.plan(),resources,builder().configuration(),config,cut)) {
            observed.cut("initialization-"+mode).at("FIXTURE_OPEN_RETURNED");
            boolean completed=Files.exists(request.replicaDirectory().resolve(MembershipJoiningRetentionFiles.DONE),LinkOption.NOFOLLOW_LINKS);
            require(mode.equals("resume") || !completed,"first joining worker already initialized");
            if(mode.equals("resume") && !completed) {
                var before=V53ReplayFilesTest.files(request.replicaDirectory());var usage=resources.usage();
                var state=owner.discoveryState(resources);assertNotNull(owner.readOnlyCapsule());
                owner.checkReadOnlyBallot(state.context().authority(),state.ballot());
                assertThrows(IllegalArgumentException.class,owner::activationContext);
                assertThrows(IllegalArgumentException.class,owner::activationCapsule);
                assertThrows(IllegalArgumentException.class,owner::beginActivation);
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(state.ballot()));
                assertThrows(IllegalArgumentException.class,owner::floorCopyCurrent);
                assertThrows(IllegalArgumentException.class,()->owner.joiningEndpointReady(resources));
                assertThrows(IllegalArgumentException.class,()->owner.openScratch(Path.of(args[4]),MembershipScratch.Role.INCOMING,
                    resources,event->{}));
                assertEquals(before,V53ReplayFilesTest.files(request.replicaDirectory()));assertEquals(usage,resources.usage());
                observed.cut("initialization-"+mode).at("INCOMPLETE_NATIVE_USES_REFUSED");
            }
            var channel=new AtomicReference<MembershipTransport>();Path scratch=Files.createDirectory(Path.of(args[4]));
            MembershipSourcePull.Link link=(peer,q,kind,deadline)->channel.get().exchange(peer,q,kind,deadline);
            long started=System.nanoTime(),budget=V53JoiningIntentExportTest.BUDGET;
            try(var endpoint=completed?
                    MembershipJoiningEndpoint.resume(owner,resources,bounds,link,scratch,System::nanoTime,budget,builder().configuration(),config.materialization()):
                    new MembershipJoiningEndpoint<>(owner,resources,bounds,link,scratch,System::nanoTime,started,budget,builder().configuration(),config.materialization());
                var transport=new MembershipTransport(owner,bounds,resources,endpoint,observed.transport("initialization-"+mode))) {
                channel.set(transport);
                if(!completed)endpoint.initializeFrom(spec.proposer());
                owner.joiningEndpointReady(resources);require(endpoint.state()==MembershipEndpointHandoff.State.ACTIVE,"joining recovery not active");
                require(mode.equals("resume"),"joining process cut was not reached");
                line("READY",Map.of("mode",mode,"pid",ProcessHandle.current().pid(),"cut",owner.activationContext().cut,"state","ACTIVE","publicReady",false));
                require(System.in.read()=='s',"joining recovered worker requires explicit stop");
            }
        }
        require(resources.usage().leases()==0 && resources.usage().queued()==0,"joining process resources leaked");
        observed.cut("initialization-"+mode).at("FIXTURE_CLOSE_RETURNED");
        line("CLOSED",Map.of("mode",mode,"pid",ProcessHandle.current().pid(),"leases",0L,"queued",0L));
    }
}
