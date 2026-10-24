package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RetirementSourceProcessTest {
    @TempDir Path temp;
    @Test void pinnedSourceRetirementRecoversAcrossTwoFreshProcessDeaths()throws Exception {
        var helper=new V53RetirementSourceImagesTest();helper.temp=Files.createDirectory(temp.resolve("producer"));var seed=helper.seed("process");
        Path out=Path.of("target/v53-retirement-source-process/run-"+UUID.randomUUID());Files.createDirectories(out);
        V53JournalApplicationTest.copy(seed.raw(),out.resolve("reference"));
        var target=seed.prepared().f().request.targets().getFirst();Path inputs=out.resolve("inputs.json");
        Files.write(inputs,canonical(Map.of("node",target.replicaDirectory().toString(),"materialization",target.materialization().directory().toString(),
                "observations",V53JournalApplicationTest.observations(seed.prepared().f().observations)),1024*1024));
        var cuts=new ArrayList<>(V53RetirementTest.CUTS);cuts.remove("RETIREMENT_IMAGE_WRITTEN");cuts.remove("RETIREMENT_IMAGE_FORCED");cuts.addAll(V53RetirementImagesTest.BORROW_CUTS);
        cuts.addAll(List.of("CONTEXT_SOURCE_MEMBER_FORCED","CONTEXT_SOURCE_DIRECTORY_FORCED","CONTEXT_SOURCE_PARENT_FORCED","RETIREMENT_BORROWED_SOURCE_FORCED"));
        System.out.println("v53RetirementSourceProcessEvidence="+out.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        try {
            for(String mode:List.of("halt","kill"))for(String cut:cuts) {
                seed.producer().reset(seed.prepared(),seed.copy(),"process-previous-"+ordinal++);String name=mode+"-"+cut;Path path=Files.createDirectory(out.resolve(name));
                int first=child(inputs,seed.node(),path,"fault",cut,mode);V53JournalApplicationTest.copy(seed.node(),path.resolve("first"));
                String second=Files.exists(seed.node().resolve("retirement/retirement.gsr"))?"RETIREMENT_AUTHORITY_RESEALED":"ACCEPT_ACTIVE_FORCED";
                int again=child(inputs,seed.node(),path,"recovery",second,"halt");V53JournalApplicationTest.copy(seed.node(),path.resolve("second"));
                int last=child(inputs,seed.node(),path,"resume","none","none");V53JournalApplicationTest.copy(seed.node(),path.resolve("final"));
                rows.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                System.out.println("v53RetirementSourceProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-retirement-source-process-v1","status",rows.size()==64?"PASS":"FAIL","cases",rows,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(row->row.get("mode").equals("kill")).count(),"inputsSha256",hash(Files.readAllBytes(inputs)),
                    "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(64,rows.size());
    }
    static Process launch(Class<?> worker,Path path,String label,String... args)throws Exception {
        var command=new ArrayList<>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),worker.getName()));
        command.addAll(Arrays.asList(args));return new ProcessBuilder(command).redirectOutput(path.resolve(label+".stdout").toFile()).redirectError(path.resolve(label+".stderr").toFile()).start();
    }
    static int child(Path inputs,Path node,Path path,String label,String cut,String mode)throws Exception {
        return child(V53RetirementSourceProcessWorker.class,inputs,node,path,label,cut,mode);
    }
    static int child(Class<?> worker,Path inputs,Path node,Path path,String label,String cut,String mode)throws Exception {
        var process=launch(worker,path,label,inputs.toAbsolutePath().toString(),cut,mode);
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",cut),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"source worker exited before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"source kill marker timeout");Thread.sleep(20);
                }
                var probe=launch(LockProbe.class,path,"lock",node.resolve("replica.lock").toString());
                try {
                    assertTrue(probe.waitFor(20,java.util.concurrent.TimeUnit.SECONDS),"source lock probe timeout");
                    Files.write(path.resolve("lock.exit.json"),canonical(Map.of("exitCode",probe.exitValue()),16384));
                    assertEquals(0,probe.exitValue(),Files.readString(path.resolve("lock.stderr")));assertEquals("",Files.readString(path.resolve("lock.stderr")));
                    assertTrue(process.isAlive(),"source worker released before lock probe");
                }finally{if(probe.isAlive())probe.destroyForcibly();probe.waitFor();}
                process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"source child timeout");
            Files.write(path.resolve(label+".exit.json"),canonical(Map.of("exitCode",process.exitValue(),"cut",cut,"mode",mode),16384));
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally{if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
    public static final class LockProbe {
        public static void main(String[] args)throws Exception {
            try(var channel=java.nio.channels.FileChannel.open(Path.of(args[0]),StandardOpenOption.READ,StandardOpenOption.WRITE)) {
                try(var lock=channel.tryLock()){if(lock!=null)throw new IllegalStateException("retirement ownership lock released");}
            }
            V53AppliedEndWorker.print(Map.of("event","LOCK_HELD","path",args[0]));
        }
    }
}
