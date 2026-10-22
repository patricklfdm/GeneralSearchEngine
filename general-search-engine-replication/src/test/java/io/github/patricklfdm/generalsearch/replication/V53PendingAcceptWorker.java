package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh processes physically own pending votes; historical quorum inputs remain fixtures. */
public final class V53PendingAcceptWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);var fixture=new V53PendingAcceptFixture(Integer.parseInt(args[2]),Boolean.parseBoolean(args[3]));
        try {
            if(command.equals("init")) {
                fixture.f.provision(path);Path inputs=path.resolveSibling("inputs");Files.createDirectory(inputs);
                for(int node=2;node<=1+fixture.f.size/2;node++) {
                    var source=fixture.f.remote(node,20,fixture.f.tail && node==2);
                    Files.write(inputs.resolve("node-"+node+".basis"),source.basis.bytes());Files.write(inputs.resolve("node-"+node+".gscp"),source.capsule.packet.bytes());
                }
                fixture.f.images().forEach((h,bytes)->{try{Files.write(inputs.resolve(h+".image"),bytes);}catch(java.io.IOException error){throw new java.io.UncheckedIOException(error);}});
                print(map("status","PASS","command",command));return;
            }
            if(command.equals("install")) {
                try(var store=fixture.f.open(path,fixture.resources(),e->{})){store.installCurrent(fixture.f.offers(store,20),fixture.f.bridges,fixture.f.images());}
                AdmissionPaths.write(path.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());AdmissionPaths.forceDirectory(path);
                print(map("status","PASS","command",command));return;
            }
            if(!Set.of("accept","capture","inspect").contains(command))throw new IllegalArgumentException("unknown pending command");
            String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var resources=fixture.resources();
            try(var store=fixture.open(path,resources,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")){print(map("event","AWAITING_KILL","cut",point));try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}throw new java.io.IOException("external kill did not arrive");}
                }
            })) {
                byte[] payload=fixture.payload(path);var entry=fixture.entry(path,payload);
                if(command.equals("accept"))store.acceptCurrent(entry,payload);
                if(command.equals("capture"))store.prepareCurrent(fixture.f.initial.fixture.source.ballot(21));
                var owned=store.currentOwnedTail().orElseThrow();var basis=store.originalBasis().orElseThrow();
                print(map("status","PASS","command",command,"accepted",owned.record(),"entry",entry.digest(),"basis",basis.digest(),"captured",basis.value().get("accepted")));
            }
            if(resources.usage().leases()!=0)throw new IllegalArgumentException("pending lease leak");
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
