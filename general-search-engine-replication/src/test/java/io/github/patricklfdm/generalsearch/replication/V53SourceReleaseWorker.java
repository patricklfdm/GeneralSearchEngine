package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Physical original-source cleanup. Historical membership/application inputs remain fixtures. */
public final class V53SourceReleaseWorker {
    static final List<String> CUTS=List.of("SOURCE_RETIREMENT_CREATED","SOURCE_RETIREMENT_WRITTEN","SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_PARENT_FORCED",
            "JOURNAL_ROTATION_CREATED","JOURNAL_ROTATION_WRITTEN","JOURNAL_ROTATION_FORCED","JOURNAL_ROTATION_RENAMED","JOURNAL_ROTATION_PARENT_FORCED",
            "SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_FILE_DELETED@2",
            "SOURCE_RETIREMENT_DIRECTORY_DELETED","SOURCE_RETIREMENT_CLEARED","SOURCE_RETIREMENT_BEFORE_RETURN");
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static String provision(Path path,int size,int through)throws Exception {
        var f=new V53CurrentGenerationFixture(size,through,false);f.provision(path);Path peers=path.getParent().resolve("inputs");Files.createDirectory(peers);
        var copies=new ArrayList<MembershipFloor.Copy>();var resources=new MembershipResources(512*MembershipResources.MIB);String id;
        try(var store=MembershipGrantJournal.openReclaiming(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,e->{})) {
            copies.add(store.floorCopyCurrent());
            for(int node=2;node<=size/2+1;node++) {
                Path peer=peers.resolve("node-"+node);V53FloorWorker.provision(peer,size,through,node);var used=new MembershipResources(512*MembershipResources.MIB);
                try(var other=MembershipGrantJournal.openMaintenance(peer,f.root(),V53DeclarationsTest.node(node),used,f::verify,e->{})){copies.add(other.floorCopyCurrent());}
                if(used.usage().leases()!=0)throw new IllegalStateException("source release peer leases");
            }
            store.establishFloor(copies);id=(String)store.prepareCurrent(f.fixture.source.ballot(20)).value().get("basisId");store.prepareCurrent(f.fixture.source.ballot(21));
        }
        if(resources.usage().leases()!=0)throw new IllegalStateException("source release setup leases");
        Files.write(path.getParent().resolve("fixture.json"),canonical(map("basisId",id),4096));return id;
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var f=new V53CurrentGenerationFixture(size,through,false);
        String event=point.split("@")[0];int occurrence=point.contains("@")?Integer.parseInt(point.split("@")[1]):1;int[] seen={0};
        try {
            if(!Set.of("init","retire","inspect").contains(command))throw new IllegalArgumentException("unknown source release command");
            if(command.equals("init")){provision(path,size,through);print(map("command",command,"status","PASS"));return;}
            String id=(String)object(parse(Files.readAllBytes(path.getParent().resolve("fixture.json")),4096)).get("basisId");var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openReclaiming(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,e->{
                print(map("event",e));if(e.equals(event) && ++seen[0]==occurrence) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {print(map("event","AWAITING_KILL","cut",point));try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}throw new java.io.IOException("external kill did not arrive");}
                }
            })) {
                if(command.equals("retire") && (Files.exists(path.resolve("sources").resolve(id)) || Files.exists(path.resolve(MembershipSourceRetirementFiles.FILE))))store.retireSource(id);
                print(map("command",command,"status","PASS","retired",!Files.exists(path.resolve("sources").resolve(id)),
                        "journal",hash(Files.readAllBytes(path.resolve("grants.gsr"))),"floor",store.governingFloor().orElseThrow().digest(),
                        "selector",hash(Files.readAllBytes(path.resolve("selector.gsr"))),"networkAck",false));
            }
            if(resources.usage().leases()!=0)throw new IllegalStateException("source release leases");
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
