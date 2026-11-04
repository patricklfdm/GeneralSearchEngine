package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Real process death; the preceding four-original history remains a conditional fixture. */
public final class V53PinnedFloorProcessWorker {
    static final V53GenerationInstallFixture FIXTURE=new V53GenerationInstallFixture(5,6,6,false);
    static void line(Map<String,Object> row){V53AppliedEndWorker.print(row);}
    static MembershipGrantJournal open(Path path,MembershipResources used,MembershipBallotAllocator.Cut cut)throws IOException {
        return MembershipGrantJournal.openCapturing(path,FIXTURE.root(),V53DeclarationsTest.node(1),used,FIXTURE::verify,cut);
    }
    static List<MembershipFloor.Copy> copies(Path owners,MembershipGrantJournal owner)throws IOException {
        var copies=new ArrayList<MembershipFloor.Copy>();copies.add(owner.floorCopyCurrent());
        for(int node:List.of(2,5,6)) {
            var used=V53SourceExchangeTest.resources();
            try(var peer=MembershipGrantJournal.openGenerations(owners.resolve("node-"+node),FIXTURE.root(),
                    V53DeclarationsTest.node(node),used,FIXTURE::verify,e->{})){copies.add(peer.floorCopyCurrent());}
            require(used.usage().leases()==0,"pinned peer process lease leak");
        }
        return copies;
    }
    static void maintain(Path owners,MembershipGrantJournal owner,String oldSource)throws IOException {
        Path store=owners.resolve("node-1");
        if(Files.exists(store.resolve("generations/b")) && owner.governingFloor().isEmpty())
            owner.establishMaintenanceFloor(copies(owners,owner),null);
        if(Files.exists(store.resolve("generations/b")) || Files.exists(store.resolve("retirement")))owner.retireInactive();
        if(Files.exists(store.resolve("sources").resolve(oldSource)))owner.retireSource(oldSource);
        if(Files.exists(store.resolve("floor-copies")))owner.releaseFloor();
    }
    static void snapshot(Path from,Path path,String name)throws IOException {V53RetirementImagesTest.copy(from,path.resolve(name));}
    public static void main(String[] args)throws Exception {
        require(args.length==4,"pinned process arguments");Path path=Path.of(args[0]),owners=path.resolve("owners"),store=owners.resolve("node-1");
        String action=args[1],point=args[2],mode=args[3];long pid=ProcessHandle.current().pid();
        require(Set.of("fault","resume","inspect").contains(action),"pinned process action");
        var input=object(parse(Files.readAllBytes(path.getParent().resolve("inputs.json")),65536));String source=(String)input.get("oldSource");
        var used=V53SourceExchangeTest.resources();boolean[] armed={false};int[] peak={0,0};
        line(Map.of("event","STARTED","pid",pid,"action",action));
        try(var owner=open(store,used,event->{
            V53RetirementImagesTest.bounded(used);var counts=used.usage().counts();
            int sources=counts.getOrDefault(MembershipResources.Unit.SOURCE,0),images=counts.getOrDefault(MembershipResources.Unit.APPLICATION,0);
            peak[0]=Math.max(peak[0],sources);peak[1]=Math.max(peak[1],images);line(Map.of("event",event,"sources",sources,"images",images));
            if(armed[0] && event.equals(point)) {
                line(Map.of("event","CUT","cut",point,"pid",pid));
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                require(mode.equals("kill"),"pinned process death mode");line(Map.of("event","AWAITING_KILL","cut",point));
                try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
                throw new IOException("external kill did not arrive");
            }
        })) {
            if(action.equals("fault")) {
                armed[0]=true;maintain(owners,owner,source);throw new IllegalStateException("pinned process cut not reached");
            }
            if(action.equals("resume")) {snapshot(store,path,"reopened");maintain(owners,owner,source);snapshot(store,path,"final");}
            else snapshot(store,path,"cold");
            require(!Files.exists(store.resolve("floor-copies")) && !Files.exists(store.resolve("generations/b")) &&
                    !Files.exists(store.resolve("sources").resolve(source)),"pinned process incomplete cleanup");
            require(number(object(owner.promised().orElseThrow().value().get("ballot")).get("counter"))==21 && owner.originalSelection().isPresent(),
                    "pinned process original selected grant changed");
            require(used.usage().counts().get(MembershipResources.Unit.SOURCE)==1 && used.usage().counts().get(MembershipResources.Unit.APPLICATION)==2,
                    "pinned process final ownership counts");
        }
        require(used.usage().leases()==0,"pinned process lease leak");
        line(Map.of("status","PASS","action",action,"pid",pid,"peakSources",peak[0],"peakImages",peak[1],"nativeHistory",false));
    }
}
