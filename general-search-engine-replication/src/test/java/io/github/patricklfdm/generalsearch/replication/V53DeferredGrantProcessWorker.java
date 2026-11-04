package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Actual process death and exclusive owner; preceding membership history remains conditional. */
public final class V53DeferredGrantProcessWorker {
    static final V53CurrentGenerationFixture FIXTURE=new V53CurrentGenerationFixture(5,6,false);
    static void line(Map<String,Object> row){V53AppliedEndWorker.print(row);}
    static MembershipGrantJournal open(Path path,MembershipResources used,MembershipBallotAllocator.Cut cut)throws IOException {
        return MembershipGrantJournal.openCapturing(path,FIXTURE.root(),V53DeclarationsTest.node(1),used,FIXTURE::verify,cut);
    }
    static void reclaim(Path owners,MembershipGrantJournal owner,List<String> sources)throws IOException {
        var copies=new ArrayList<MembershipFloor.Copy>();copies.add(owner.floorCopyCurrent());
        for(int node:List.of(2,5,6)) {
            var used=V53SourceExchangeTest.resources();
            try(var peer=MembershipGrantJournal.openGenerations(owners.resolve("node-"+node),FIXTURE.root(),
                    V53DeclarationsTest.node(node),used,FIXTURE::verify,e->{})){copies.add(peer.floorCopyCurrent());}
            require(used.usage().leases()==0,"peer process lease leak");
        }
        owner.establishFloor(copies);
        for(String id:sources)if(Files.exists(owners.resolve("node-1/sources").resolve(id)))owner.retireSource(id);
        owner.releaseFloor();
    }
    static void snapshot(Path store,Path path,String name)throws IOException {V53RetirementImagesTest.copy(store,path.resolve(name));}
    public static void main(String[] args)throws Exception {
        require(args.length==4,"deferred process arguments");Path path=Path.of(args[0]),owners=path.resolve("owners"),store=owners.resolve("node-1");
        String action=args[1],point=args[2],mode=args[3];long pid=ProcessHandle.current().pid();
        require(Set.of("fault","resume","inspect").contains(action),"deferred process action");
        var input=object(parse(Files.readAllBytes(path.getParent().resolve("inputs.json")),65536));
        var sources=list(input.get("sources")).stream().map(v->(String)v).toList();
        var used=V53SourceExchangeTest.resources();boolean[] armed={false};int[] peak={0,0};
        line(Map.of("event","STARTED","pid",pid,"action",action));
        try(var owner=open(store,used,event->{
            V53RetirementImagesTest.bounded(used);var counts=used.usage().counts();
            peak[0]=Math.max(peak[0],counts.getOrDefault(MembershipResources.Unit.SOURCE,0));
            peak[1]=Math.max(peak[1],counts.getOrDefault(MembershipResources.Unit.APPLICATION,0));
            line(Map.of("event",event));
            if(armed[0] && event.equals(point)) {
                line(Map.of("event","CUT","cut",point,"pid",pid));
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                require(mode.equals("kill"),"deferred process death mode");
                line(Map.of("event","AWAITING_KILL","cut",point));
                try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
                throw new IOException("external kill did not arrive");
            }
        })) {
            if(action.equals("fault")) {
                armed[0]=true;
                owner.prepareCurrent(FIXTURE.fixture.source.ballot(30),grant->{
                    require(!Thread.holdsLock(owner),"deferred process maintenance under writer");grant.check();reclaim(owners,owner,sources);grant.check();
                });
                throw new IllegalStateException("deferred process cut not reached");
            }
            require(owner.originalSelection().isEmpty(),"deferred process cannot select");
            if(action.equals("resume")) {
                boolean captured=owner.originalBasis().isPresent();
                require(number(object(owner.promised().orElseThrow().value().get("ballot")).get("counter"))==30,"recovered original promise");
                snapshot(store,path,"reopened");
                if(!captured)reclaim(owners,owner,sources);
                snapshot(store,path,"maintained");var before=V53ReplayFilesTest.files(store);
                if(captured) {
                    byte[] original=owner.originalBasis().orElseThrow().bytes();
                    require(Arrays.equals(original,owner.prepareCurrent(FIXTURE.fixture.source.ballot(30)).bytes()),"changed original recovered basis");
                }else {
                    try{owner.prepareCurrent(FIXTURE.fixture.source.ballot(30));throw new AssertionError("unmarked promise gained a basis");}
                    catch(IllegalArgumentException expected){require(expected.getMessage().equals("incomplete original basis; fresh ballot required"),"unexpected incomplete refusal");}
                }
                require(before.equals(V53ReplayFilesTest.files(store)),"same ballot changed original files");
                snapshot(store,path,"same-ballot");
                var next=owner.prepareCurrent(FIXTURE.fixture.source.ballot(31));
                require(number(object(next.value().get("ballot")).get("counter"))==31,"fresh process grant");
                require(used.usage().counts().get(MembershipResources.Unit.SOURCE)==(captured?2:1),"fresh process source count");
                line(Map.of("event","RESUMED","captured",captured,"basis",next.digest()));
            }else {
                var before=V53ReplayFilesTest.files(store);byte[] original=owner.originalBasis().orElseThrow().bytes();
                require(number(object(owner.promised().orElseThrow().value().get("ballot")).get("counter"))==31,"cold original grant");
                require(Arrays.equals(original,owner.prepareCurrent(FIXTURE.fixture.source.ballot(31)).bytes()) &&
                        before.equals(V53ReplayFilesTest.files(store)),"cold duplicate changed original files");
            }
            snapshot(store,path,action.equals("resume")?"final":"cold");
        }
        require(used.usage().leases()==0,"deferred process lease leak");
        line(Map.of("status","PASS","action",action,"pid",pid,"peakSources",peak[0],"peakImages",peak[1],"nativeHistory",false));
    }
}
