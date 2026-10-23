package io.github.patricklfdm.generalsearch.replication;

import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional selected-generation input; explicit damage injection is not a power-loss simulation. */
public final class V53PromiseBoundaryWorker {
    static void print(Map<String,Object> v){V53AppliedEndWorker.print(v);}
    static String refusal(String point){return point.equals("DAMAGED_HEADER")?"torn grant journal header":"torn grant journal body";}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),node=root.resolve("node-1");String command=args[1],mode=args[2];
        var profile=object(parse(Files.readAllBytes(root.resolve("profile.json")),4096));String point=(String)profile.get("cut");
        var f=new V53CurrentGenerationFixture(Math.toIntExact(number(profile.get("size"))),Math.toIntExact(number(profile.get("through"))),true);
        var resources=new MembershipResources(512*MembershipResources.MIB);boolean damaged=point.startsWith("DAMAGED_");
        if(command.equals("fault")) {
            int prior=Files.readAllBytes(node.resolve("grants.gsr")).length;
            try(var store=MembershipGrantJournal.openCapturing(node,f.root(),V53DeclarationsTest.node(1),resources,f::verify,event->{
                print(Map.of("event",event));
                if(event.equals("PROMISE_WRITTEN")) {
                    byte[] written=Files.readAllBytes(node.resolve("grants.gsr"));byte[] request=Arrays.copyOfRange(written,prior,written.length);
                    Files.write(root.resolve("original-promise.gsr"),request);
                    if(damaged) {
                        // Test-only storage damage, after the normal whole-frame write. Never used by recovery.
                        int length=point.equals("DAMAGED_HEADER")?17:request.length/2;
                        try(var channel=FileChannel.open(node.resolve("grants.gsr"),StandardOpenOption.WRITE)){channel.truncate(prior+length);}
                        print(Map.of("event",point,"retainedPrefix",(long)length));stop(point,mode);
                    }
                }
                if(event.equals(point))stop(point,mode);
            })) {store.prepareCurrent(f.fixture.source.ballot(20));throw new AssertionError("fault absent");}
        }
        var before=V53ReplayFilesTest.files(node);
        if(damaged) {
            if(!command.equals("inspect"))throw new AssertionError("damaged authority cannot resume");
            try(var ignored=MembershipGrantJournal.openCapturing(node,f.root(),V53DeclarationsTest.node(1),resources,f::verify,event->print(Map.of("event",event)))) {
                throw new AssertionError("torn promise opened");
            }catch(IllegalArgumentException e){if(!refusal(point).equals(e.getMessage()))throw e;}
            if(!before.equals(V53ReplayFilesTest.files(node)) || resources.usage().leases()!=0)throw new AssertionError("failed open changed authority or leaked leases");
            print(Map.of("status","PASS","disposition","OPEN_REFUSED","reason",refusal(point),"liveLeases",0L));return;
        }
        try(var store=MembershipGrantJournal.openCapturing(node,f.root(),V53DeclarationsTest.node(1),resources,f::verify,event->print(Map.of("event",event)))) {
            if(command.equals("inspect")) {
                if(store.originalBasis().isPresent() || store.originalSelection().isPresent())throw new AssertionError("invented original grant");
                long counter=number(object(store.promised().orElseThrow().value().get("ballot")).get("counter"));
                if(counter!=(point.equals("PROMISE_BEFORE_WRITE")?10:20))throw new AssertionError("promise floor changed");
                if(counter==20) {
                    try{store.prepareCurrent(f.fixture.source.ballot(20));throw new AssertionError("same ballot resampled");}
                    catch(IllegalArgumentException e){if(!"incomplete original basis; fresh ballot required".equals(e.getMessage()))throw e;}
                }
                if(!before.equals(V53ReplayFilesTest.files(node)))throw new AssertionError("inspection changed bytes");
                print(Map.of("status","PASS","disposition","NO_BASIS","counter",counter));
            }else if(command.equals("resume") || command.equals("duplicate")) {
                long counter=point.equals("PROMISE_BEFORE_WRITE")?20:21;
                var basis=store.prepareCurrent(f.fixture.source.ballot(counter));
                if(command.equals("duplicate") && !before.equals(V53ReplayFilesTest.files(node)))throw new AssertionError("duplicate changed bytes");
                print(Map.of("status","PASS","disposition","NEW_GRANT","counter",counter,"basis",basis.digest(),"accepted",basis.value().get("accepted")));
            }else throw new AssertionError("unknown command");
        }
        if(resources.usage().leases()!=0)throw new AssertionError("promise lease leak");
    }
    static void stop(String point,String mode)throws java.io.IOException {
        if(mode.equals("halt"))Runtime.getRuntime().halt(73);
        if(mode.equals("kill")) {
            print(Map.of("event","AWAITING_KILL","cut",point));
            try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
        }
        throw new java.io.IOException("external crash absent");
    }
}
