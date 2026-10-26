package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual receiving scratch and process death; no remote vote or runtime READY claim. */
class V53ScratchProcessTest {
    @TempDir Path temp;
    static final List<String> RECEIVE=List.of("CREATED","PARTIAL_PACKET","PACKET_VERIFIED","PARTIAL_IMAGE","COMPLETE");
    static final List<String> CLEANUP=List.of("RECOVERY_VALIDATED","FILE_REMOVED","FILE_REMOVAL_FORCED","DIRECTORY_REMOVED","DIRECTORY_REMOVAL_FORCED");
    static final long BUDGET=TimeUnit.SECONDS.toNanos(60);
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static Map<String,Object> read(Path path)throws Exception{return object(parse(Files.readAllBytes(path),65536));}
    static void save(Path path,Object value)throws Exception{Files.write(path,canonical(value,65536));}
    int child(Path raw,Path scope,MembershipScratch.Role role,String action,String cut,String mode,Path record)throws Exception {
        Path ready=record.resolveSibling(record.getFileName()+".ready"),result=record.resolveSibling(record.getFileName()+".json");
        var command=List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                Worker.class.getName(),raw.toAbsolutePath().toString(),scope.toAbsolutePath().toString(),role.name(),action,cut,mode,ready.toString(),result.toString());
        var process=new ProcessBuilder(command).redirectOutput(record.resolveSibling(record.getFileName()+".stdout").toFile())
                .redirectError(record.resolveSibling(record.getFileName()+".stderr").toFile()).start();
        try {
            if(!mode.equals("none")) {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
                while(process.isAlive() && !Files.exists(ready) && System.nanoTime()<deadline)Thread.sleep(10);
                assertTrue(Files.exists(ready),"missing process cut: "+record+" stderr="+Files.readString(record.resolveSibling(record.getFileName()+".stderr")));
                assertEquals(Map.of("cut",cut,"mode",mode),read(ready));if(mode.equals("kill"))process.destroyForcibly();
            }
            assertTrue(process.waitFor(30,TimeUnit.SECONDS),"scratch worker timeout: "+record);
            int expected=mode.equals("none")?0:mode.equals("halt")?91:137;
            assertEquals(expected,process.exitValue(),"worker stderr="+Files.readString(record.resolveSibling(record.getFileName()+".stderr")));
            if(mode.equals("none"))assertEquals(0L,read(result).get("remainingLeases"));return process.exitValue();
        }finally{if(process.isAlive()){process.destroyForcibly();assertTrue(process.waitFor(10,TimeUnit.SECONDS));}}
    }
    @Test void realReceivingDeathsAndRepeatedCleanupDeathsRetainAuthority()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-scratch-process/run-"+UUID.randomUUID()));
        System.out.println("v53ScratchProcessEvidence="+evidence.toAbsolutePath());Path raw=Files.createDirectory(evidence.resolve("stable-3"));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("group")),raw,3,false);var target=f.request.targets().getFirst();var cases=new ArrayList<Map<String,Object>>();
        try(var owner=f.open(target,"scratch-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
            Path captured=Files.createDirectory(raw.resolve("captured"));for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
            Path output=Files.createDirectory(raw.resolve("exported"));var contents=new ArrayList<Map<String,Object>>();
            for(var content:export.contents()){Files.write(output.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));}
            save(raw.resolve("contents.json"),contents);
            save(raw.resolve("grant.json"),Map.of("root",export.context().root,"source",MembershipBootstrapSeed.identity(export.identity()),
                    "local",MembershipBootstrapSeed.identity(f.request.targets().get(1).identity()),"promise",export.promise().digest(),"basis",export.source().basis.digest(),"capsule",V53SourceReceiveTest.packetOffer(export).digest()));
            Path histories=Files.createDirectory(raw.resolve("crashes"));
            for(var role:MembershipScratch.Role.values())for(String mode:List.of("halt","kill"))for(int n=0;n<RECEIVE.size();n++) {
                String cut=RECEIVE.get(n),cleanup=CLEANUP.get(n),name=role.name().toLowerCase(Locale.ROOT)+"-"+mode+"-"+cut.toLowerCase(Locale.ROOT);
                Path history=Files.createDirectory(histories.resolve(name)),scope=temp.resolve("scope-"+UUID.randomUUID());
                int first=child(raw,scope,role,"receive",cut,mode,history.resolve("receive"));V53JournalApplicationTest.copy(scope,history.resolve("crashed"));
                int second=child(raw,scope,role,"recover",cleanup,mode,history.resolve("cleanup"));V53JournalApplicationTest.copy(scope,history.resolve("interrupted"));
                child(raw,scope,role,"recover","NONE","none",history.resolve("recover"));V53JournalApplicationTest.copy(scope,history.resolve("after"));
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scope,8));
                var row=Map.<String,Object>of("case",name,"role",role.name(),"mode",mode,"receiveCut",cut,"cleanupCut",cleanup,"receiveExit",first,"cleanupExit",second,"freshJvms",3,"status","PASS");
                save(history.resolve("case.json"),row);cases.add(row);
            }
        }
        f.snapshot("after");save(evidence.resolve("receipt.json"),Map.of("schema","gse-v53-scratch-process-v1","status","PASS","cases",cases,
                "freshJvms",60,"publicRuntime",false,"network",false,"scope","receiving-scratch-restart-only"));
    }
    public static final class Worker {
        static Path ready;static String wanted,mode;
        static void cut(String point)throws Exception {
            if(!point.equals(wanted))return;save(ready,Map.of("cut",point,"mode",mode));
            if(mode.equals("halt"))Runtime.getRuntime().halt(91);
            if(mode.equals("kill")){Thread.sleep(60000);throw new IllegalStateException("missing external SIGKILL");}
        }
        static void send(MembershipSourceReceive received,MembershipTransfer.Binding binding,byte[] body)throws Exception {
            for(int offset=0;offset<body.length;offset+=1024){byte[] chunk=Arrays.copyOfRange(body,offset,Math.min(body.length,offset+1024));received.chunk(binding,offset,chunk,hash(chunk));}
            received.finish(binding);
        }
        public static void main(String[] args)throws Exception {
            Path raw=Path.of(args[0]),path=Path.of(args[1]);var role=MembershipScratch.Role.valueOf(args[2]);String action=args[3];wanted=args[4];mode=args[5];ready=Path.of(args[6]);Path result=Path.of(args[7]);
            var grant=read(raw.resolve("grant.json"));var source=MembershipContext.identity(object(grant.get("source")));var local=MembershipContext.identity(object(grant.get("local")));var budget=resources();
            var discarded=new ArrayList<Map<String,Object>>();
            try(var scope=MembershipScratch.open(path,(String)grant.get("root"),local,role,budget,()->{},event->{
                if(action.equals("recover"))try{cut(event);}catch(java.io.IOException error){throw error;}catch(Exception error){throw new java.io.IOException(error);}
            })) {
                for(var row:scope.recovered())discarded.add(Map.of("path",row.path(),"directory",row.directory(),"bytes",row.bytes()));
                if(action.equals("receive")) {
                    var promise=decode(Files.readAllBytes(raw.resolve("exported/"+grant.get("promise")+".bin")),"records","PROMISE");
                    var basis=decode(Files.readAllBytes(raw.resolve("exported/"+grant.get("basis")+".bin")),"records","BASIS");
                    byte[] packet=Files.readAllBytes(raw.resolve("exported/"+grant.get("capsule")+".bin"));
                    Path destination=role==MembershipScratch.Role.OUTGOING?path.resolve("source-"+UUID.randomUUID()):Files.createDirectory(path.resolve("selected-"+UUID.randomUUID())).resolve("source-1");
                    long started=System.nanoTime();
                    try(var received=new MembershipSourceReceive(destination,(String)grant.get("root"),source,promise,basis,UUID.randomUUID(),
                            new MembershipSourceExport.Content((String)grant.get("capsule"),packet.length,MembershipTransfer.Kind.CAPSULE),budget,1024,System::nanoTime,started,BUDGET)) {
                        cut("CREATED");
                        if(wanted.equals("PARTIAL_PACKET")){byte[] part=Arrays.copyOf(packet,17);received.chunk(received.packetBinding(),0,part,hash(part));cut("PARTIAL_PACKET");}
                        send(received,received.packetBinding(),packet);cut("PACKET_VERIFIED");
                        for(var image:received.imageBindings()) {
                            byte[] body=Files.readAllBytes(raw.resolve("exported/"+image.digest()+".bin"));
                            if(wanted.equals("PARTIAL_IMAGE")){byte[] part=Arrays.copyOf(body,17);received.chunk(image,0,part,hash(part));cut("PARTIAL_IMAGE");}
                            send(received,image,body);
                        }
                        received.images();cut("COMPLETE");throw new IllegalStateException("receive did not stop at requested cut");
                    }
                }
            }
            save(result,Map.of("status","PASS","discarded",discarded,"remainingLeases",budget.usage().leases()));
        }
    }
}
