package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Physical original-source cleanup. Historical membership/application inputs remain fixtures. */
public final class V53CapturedSourceReleaseWorker {
    static final List<String> CUTS=List.of("SOURCE_RETIREMENT_CREATED","SOURCE_RETIREMENT_WRITTEN","SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_PARENT_FORCED",
            "JOURNAL_ROTATION_CREATED","JOURNAL_ROTATION_WRITTEN","JOURNAL_ROTATION_FORCED","JOURNAL_ROTATION_RENAMED","JOURNAL_ROTATION_PARENT_FORCED",
            "SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_FILE_DELETED@2",
            "SOURCE_RETIREMENT_DIRECTORY_DELETED","SOURCE_RETIREMENT_CLEARED","SOURCE_RETIREMENT_BEFORE_RETURN");
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void copy(Path from,Path to)throws Exception {
        try(var paths=Files.walk(from)){for(Path p:paths.toList()) {
            Path dest=to.resolve(from.relativize(p));if(Files.isDirectory(p))Files.createDirectory(dest);else Files.copy(p,dest);
        }}
    }
    static MembershipGrantJournal open(Path path,V53AdoptionFenceFixture f,boolean tail,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        f.owned.addAll(new V53CurrentGenerationFixture(f.initial.size,0,tail).fixture.owned);
        return MembershipGrantJournal.openReclaiming(path,f.initial.root(),V53DeclarationsTest.node(1),resources,
            (root,packet,images)->MembershipCapsule.verify(root,packet,images,f.owned),cut);
    }
    static String provision(Path path,int size,int through,boolean tail)throws Exception {
        var f=new V53AdoptionFenceFixture(size,through);var initial=new V53CurrentGenerationFixture(size,0,tail);
        f.owned.addAll(initial.fixture.owned);initial.provision(path);Path inputs=path.getParent().resolve("inputs");Files.createDirectory(inputs);
        var resources=new MembershipResources(512*MembershipResources.MIB);boolean captured=false;
        try(var store=open(path,f,tail,resources,e->{if(e.equals("SOURCE_DIRECTORY_FORCED"))throw new java.io.IOException("captured");})) {
            store.prepareCurrent(initial.fixture.source.ballot(20));
        }catch(java.io.IOException error){if(!error.getMessage().equals("captured"))throw error;captured=true;}
        if(!captured || resources.usage().leases()!=0)throw new IllegalStateException("captured source setup");
        copy(path,inputs.resolve("original"));Path adoption=inputs.resolve("adoption");Files.createDirectory(adoption);
        Files.createDirectory(adoption.resolve("initial"));Files.copy(path.resolve("root.gsr"),adoption.resolve("initial/root.gsr"));
        Path remote=adoption.resolve("inputs");Files.createDirectory(remote);Files.write(remote.resolve("source.gscp"),f.remote.packet().bytes());
        for(var image:f.remote.source.images.entrySet())Files.write(remote.resolve(image.getKey()+".image"),image.getValue());
        String id;try(var store=open(path,f,tail,resources,e->{})) {
            if(store.originalBasis().isPresent())throw new IllegalStateException("captured source fabricated BASIS");
            id=(String)store.promised().orElseThrow().value().get("basisId");store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
            var copies=new ArrayList<MembershipFloor.Copy>();copies.add(store.floorCopyCurrent());
            var peerFixture=new V53CurrentGenerationFixture(size,through,false);
            for(int node=2;node<=size/2+1;node++) {
                Path peer=inputs.resolve("node-"+node);V53FloorWorker.provision(peer,size,through,node);var used=new MembershipResources(512*MembershipResources.MIB);
                try(var other=MembershipGrantJournal.openMaintenance(peer,peerFixture.root(),V53DeclarationsTest.node(node),used,peerFixture::verify,e->{})){copies.add(other.floorCopyCurrent());}
                if(used.usage().leases()!=0)throw new IllegalStateException("captured peer leases");
            }
            store.establishFloor(copies);store.retireInactive();
        }
        if(resources.usage().leases()!=0)throw new IllegalStateException("captured setup leases");
        Files.write(path.getParent().resolve("fixture.json"),canonical(map("basisId",id),4096));return id;
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        boolean tail=Boolean.parseBoolean(args[4]);String point=args.length>5?args[5]:"none",mode=args.length>6?args[6]:"none";var f=new V53AdoptionFenceFixture(size,through);
        String event=point.split("@")[0];int occurrence=point.contains("@")?Integer.parseInt(point.split("@")[1]):1;int[] seen={0};
        try {
            if(!Set.of("init","retire","inspect").contains(command))throw new IllegalArgumentException("unknown source release command");
            if(command.equals("init")){provision(path,size,through,tail);print(map("command",command,"status","PASS"));return;}
            String id=(String)object(parse(Files.readAllBytes(path.getParent().resolve("fixture.json")),4096)).get("basisId");var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=open(path,f,tail,resources,e->{
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
