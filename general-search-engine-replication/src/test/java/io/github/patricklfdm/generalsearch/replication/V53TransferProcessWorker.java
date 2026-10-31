package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One donor lifetime; control pipe observations cannot replace the TCP replies. */
public final class V53TransferProcessWorker {
    public static void main(String[] args)throws Exception {
        var spec=object(parse(Files.readAllBytes(Path.of(args[0])),65536));
        int life=Integer.parseInt(args[1]);String mode=(String)spec.get("mode"),point=(String)spec.get("point");
        require(life==1 || life==2,"transfer worker life");require(Set.of("halt","kill").contains(mode),"transfer worker mode");
        require(Set.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT").contains(point),"transfer worker point");
        Path replica=Path.of((String)spec.get("replica")),application=Path.of((String)spec.get("application"));
        Path stop=Path.of(args[2]);var pipe=new V53NodeProcessWorker.Pipe();
        var root=decode(Files.readAllBytes(replica.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(replica.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var resources=V53SourceExchangeTest.resources();var bounds=V53TransferServiceTest.bound(2);
        pipe.accept("STARTED",Map.of("pid",ProcessHandle.current().pid(),"life",life));
        try(var owner=MembershipGrantJournal.openBootstrapped(replica,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,
                event->pipe.accept("STORE",event))) {
            var basis=owner.originalBasis().orElseThrow();var promise=owner.promised().orElseThrow();
            long started=System.nanoTime(),budget=V53SourceExchangeTest.BUDGET;
            try(var service=new MembershipTransferService(owner,object(basis.value().get("ballot")),resources,bounds,
                    ()->owner.checkActivation(basis,null,false),System::nanoTime,started,budget);
                var transport=new MembershipTransport(owner.activationCapsule(),identity,bounds,resources,service,(event,q,a)->{
                    var row=new TreeMap<String,Object>();row.put("event",event);row.put("request",V53TransferFaultsTest.encoded(q));
                    if(a!=null)row.put("response",V53TransferFaultsTest.encoded(a));pipe.accept("WIRE",row);
                    if(life==1 && event.equals("BEFORE_RESPONSE_WRITE") && a.kind().equals(point))V53NodeProcessWorker.crash(pipe,point,mode);
                })) {
                pipe.accept("OPEN",Map.of("started",started,"budget",budget,"promise",promise.digest(),"basis",basis.digest()));
                while(!Files.exists(stop)) {
                    require(System.nanoTime()-started<TimeUnit.MINUTES.toNanos(2),"transfer worker explicit stop absent");Thread.sleep(10);
                }
                require(life==2,"interrupted donor returned normally");
            }
        }
        require(resources.usage().leases()==0 && resources.usage().queued()==0,"transfer donor resource leak");
        pipe.accept("CLOSED",V53TransferFaultsTest.usage(resources));
    }
}
