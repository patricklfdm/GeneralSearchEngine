package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** A whole native group on its original disks; only node 1 campaigns. No client retry. */
public final class V53NativeCarriedProcessWorker {
    static final Set<String> CUTS=Set.of("NATIVE_RETIREMENT_CERTIFICATE_RETAINED","ACCEPT_RENAMED",
            "PROOF_RENAMED","APPLY_ACK_DIRECTORY_FORCED");
    static void applicationCaptureCase(boolean first,boolean recovery,int life,String kind,String point,int arguments) {
        if(!first && !recovery)return;
        // Either just the original resource capture, or all three maintenance
        // families together. Other partial/extended shapes are not this entry.
        if(first && recovery || life!=(first?1:2) || !Set.of("INTENT","FINAL").contains(kind) ||
                !point.equals("APPLY_ACK_DIRECTORY_FORCED") || arguments!=5 && arguments!=8)
            throw new IllegalArgumentException("native carried explicit application capture layout");
    }
    public static void main(String[] args)throws Exception {
        Path applicationCut=null,applicationRetirement=null;
        if(args.length>=2 && args[args.length-2].equals("--application-cut-capture")) {
            applicationCut=Path.of(args[args.length-1]);args=Arrays.copyOf(args,args.length-2);
        } else if(args.length>=2 && args[args.length-2].equals("--application-retirement-capture")) {
            applicationRetirement=Path.of(args[args.length-1]);args=Arrays.copyOf(args,args.length-2);
        }
        if(args.length<4 || args.length>12)throw new IllegalArgumentException("native carried worker arguments");
        Path spec=Path.of(args[0]);int life=Integer.parseInt(args[1]);String point=args[2],mode=args[3];
        if((life!=1 && life!=2) || !CUTS.contains(point) || !Set.of("halt","kill").contains(mode))
            throw new IllegalArgumentException("native carried process case");
        var input=object(parse(Files.readAllBytes(spec),65536));
        var paths=list(input.get("nodes")).stream().map(MembershipFormat::object).toList();
        String kind=(String)input.getOrDefault("kind","DATA");boolean data=kind.equals("DATA");
        if(!Set.of("DATA","INTENT","FINAL").contains(kind) || paths.size()!=(data?3:4) ||
                !data && point.equals("NATIVE_RETIREMENT_CERTIFICATE_RETAINED"))
            throw new IllegalArgumentException("native carried process fixed topology/kind");
        applicationCaptureCase(applicationCut!=null,applicationRetirement!=null,life,kind,point,args.length);
        int carriedIndex=data?1:kind.equals("INTENT")?5:6;long seconds=data?180:600;
        var identities=new ArrayList<MembershipIdentity>();
        for(var path:paths)identities.add(MembershipContext.identity(object(decode(Files.readAllBytes(
                Path.of((String)path.get("replica")).resolve("node.gsr")),"records","NODE").value().get("identity"))));
        var root=decode(Files.readAllBytes(Path.of((String)paths.getFirst().get("replica")).resolve("root.gsr")),"records","ROOT");
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),
                UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var pipe=new V53NodeProcessWorker.Pipe();
        var capture=args.length>=5?new V53NodeResourceCapture(Path.of(args[4]),history.manifestDigest(),life,pipe,
                args.length>=6?Path.of(args[5]):null,args.length>=7?Path.of(args[6]):null,args.length>=8?Path.of(args[7]):null,
                args.length>=9?Path.of(args[8]):null,args.length>=10?Path.of(args[9]):null,args.length>=11?Path.of(args[10]):null,args.length==12?Path.of(args[11]):null,applicationCut,applicationRetirement):null;
        V53NodeProcessWorker.Sink sink=capture==null?pipe:capture;
        var owners=new ArrayList<MembershipNodeOwner<Integer,Doc>>();
        var activeSlot=new AtomicLong();var installations=new AtomicLong();var cut=new AtomicBoolean();
        var defaults=ReplicationBounds.defaults();
        var bounds=data?defaults:new ReplicationBounds(defaults.maxFrameBytes(),defaults.maxEntriesPerAppend(),defaults.maxInFlightPerPeer(),
                defaults.maxPendingClientOperations(),defaults.maxRetryAttempts(),30_000,defaults.retryBackoffMillis(),
                defaults.snapshotChunkBytes(),defaults.maxRetainedLogBytes(),defaults.maxSnapshotStagingBytes());
        long started=System.nanoTime();
        sink.accept("started",Map.of("pid",ProcessHandle.current().pid(),"life",life,"mode",mode,"cut",point));
        Throwable primary=null;
        try {
            for(int index=0;index<paths.size();index++) {
                var identity=identities.get(index);String name=identity.nodeId().value();var path=paths.get(index);
                Path replica=Path.of((String)path.get("replica")),application=Path.of((String)path.get("application"));
                var config=new MembershipReplicaConfig<>(history,identity,identities.stream().filter(v->!v.equals(identity)).toList(),
                        replica,storage(application,2),bounds,AutomaticLeadershipPolicy.forBounds(bounds));
                var original=V53NodeProcessWorker.hooks(name,life,(action,value)->{
                    if(action.equals("snapshot"))sink.accept(action,"life-"+life+"-"+value);
                    else if(!action.equals("installed"))sink.accept(action,value);
                });
                var hooks=new MembershipNodeOwner.Hooks(event->{
                    original.storage().at(event);
                    if(life==1 && name.equals("node-1") && activeSlot.get()==carriedIndex && event.equals(point) && cut.compareAndSet(false,true))
                        V53NodeProcessWorker.crash(sink,point,mode);
                },original.network(),(event,record)->{
                    if(name.equals("node-1") && event.equals("SLOT_BEGIN"))activeSlot.set(number(record.value().get("index")));
                    original.round().at(event,record);
                    if(name.equals("node-1") && event.equals("INSTALLED"))sink.accept("installed",Map.of("life",life,
                            "number",installations.incrementAndGet(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                },original.slot());
                Path scratch=Path.of((String)path.get("scratch"));
                var owner=new MembershipNodeOwner<>(config,builder().configuration(),scratch.resolve("incoming"),scratch.resolve("outgoing"),
                        System::nanoTime,TimeUnit.SECONDS.toNanos(seconds),hooks,capture!=null);
                if(capture!=null)capture.register(identity,owner,replica);
                owners.add(owner);owner.open();
                if(owner.serviceState().orElseThrow()!=MembershipAutomaticOwner.State.NEW)throw new AssertionError("restored READY");
                try{owner.readiness();throw new AssertionError("readiness before fresh barrier");}catch(IllegalArgumentException expected){}
                var counts=new TreeMap<String,Object>();owner.usage().counts().forEach((unit,count)->counts.put(unit.name(),count));
                sink.accept("event",Map.of("node",name,"incarnation",life,"event","NODE_OPEN","counts",counts));
            }
            sink.accept("opened",life);
            var ready=owners.getFirst().start().await(seconds,TimeUnit.SECONDS);
            if(life==1)throw new AssertionError("declared carried boundary not reached");
            sink.accept("snapshot","life-2-ready");
            sink.accept("ready",Base64.getEncoder().encodeToString(ready.bytes()));
        }catch(Exception|Error error){
            primary=error;
            try {
                sink.accept("snapshot","life-"+life+"-failed");
                for(int i=0;i<owners.size();i++) {
                    var owner=owners.get(i);var counts=new TreeMap<String,Object>();owner.usage().counts().forEach((unit,count)->counts.put(unit.name(),count));
                    sink.accept("event",Map.of("node","node-"+(i+1),"incarnation",life,"event","NODE_FAILED",
                            "counts",counts,"failure",error.toString()));
                }
            }catch(Exception diagnostic){error.addSuppressed(diagnostic);}
            throw error;
        }
        finally {
            IOException closing=null;
            for(var owner:owners.reversed())try{if(capture==null)owner.close();else capture.closeOwner(owner);if(owner.usage().leases()!=0)throw new IOException("native carried resource leak");}
            catch(IOException error){if(closing==null)closing=error;else closing.addSuppressed(error);}
            if(capture!=null)try{capture.save(primary==null && closing==null?"CLOSED":"FAILED");}
            catch(IOException|RuntimeException error){if(primary!=null)primary.addSuppressed(error);else if(closing!=null)closing.addSuppressed(error);else throw error;}
            if(primary!=null && closing!=null)primary.addSuppressed(closing);else if(closing!=null)throw closing;
        }
        sink.accept("closed",Map.of("life",life,"elapsedNanos",System.nanoTime()-started,"clientCalls",0));
    }
}
