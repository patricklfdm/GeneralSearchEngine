package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process capture recovery probe; historical quorum ownership is a fixture. */
public final class V53CaptureRecoveryWorker {
    static final List<String> CUTS=List.of("CAPTURE_INTENT_CREATED","CAPTURE_INTENT_PREFIX_WRITTEN","CAPTURE_INTENT_WRITTEN",
            "CAPTURE_INTENT_FORCED","CAPTURE_INTENT_PARENT_FORCED","SOURCE_BEFORE_CREATE","SOURCE_CREATED",
            "SOURCE_PACKET_CREATED","SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_PACKET_WRITTEN","SOURCE_PACKET_FORCED",
            "SOURCE_IMAGE_CREATED","SOURCE_IMAGE_PREFIX_WRITTEN","SOURCE_IMAGE_WRITTEN","SOURCE_IMAGE_FORCED",
            "SOURCE_FILES_DIRECTORY_FORCED","SOURCE_DIRECTORY_FORCED","BASIS_BEFORE_WRITE","BASIS_WRITTEN","BASIS_FORCED",
            "CAPTURE_INTENT_DELETED","CAPTURE_INTENT_CLEARED","GRANT_BEFORE_RETURN");
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);boolean tail=Boolean.parseBoolean(args[4]);
        try {
            var f=new V53CurrentGenerationFixture(size,through,tail);
            if(command.equals("init")){f.provision(path);print(map("status","PASS","command",command));return;}
            if(!Set.of("prepare","inspect").contains(command))throw new IllegalArgumentException("unknown capture command");
            String point=args.length>5?args[5]:"none",mode=args.length>6?args[6]:"none";var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openCapturing(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")){print(map("event","AWAITING_KILL","cut",point));try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}throw new java.io.IOException("external kill did not arrive");}
                }
            })) {
                if(command.equals("prepare"))store.prepareCurrent(f.fixture.source.ballot(20));
                var basis=store.originalBasis().orElseThrow();print(map("status","PASS","command",command,"basis",basis.digest(),"accepted",basis.value().get("accepted"),"cut",object(basis.value().get("cut")).get("index"),"sourceCount",(long)resources.usage().counts().get(MembershipResources.Unit.SOURCE)));
            }
            if(resources.usage().leases()!=0)throw new IllegalArgumentException("capture lease leak");
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
