package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53ProcessTraceTest {
    @TempDir Path temp;
    @Test void threadsAndSeparateProcessesKeepEveryWholeObservation()throws Exception {
        Path path=temp.resolve("trace.jsonl");var parent=new V53ProcessTrace(path,"parent",true);
        var children=new ArrayList<Process>();
        try {
            for(String mode:List.of("kill","resume"))children.add(new ProcessBuilder(
                Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ProcessTraceTest.class.getName(),path.toString(),mode).redirectErrorStream(true).redirectOutput(temp.resolve(mode+".log").toFile()).start());
            write(parent);
            for(var child:children){assertTrue(child.waitFor(30,TimeUnit.SECONDS));assertEquals(0,child.exitValue());}
            var lines=Files.readAllLines(path);assertEquals(180,lines.size());assertEquals(180,new HashSet<>(lines).size());
            for(String mode:List.of("parent","kill","resume"))for(int i=0;i<60;i++)
                assertTrue(lines.contains(new String(MembershipFormat.canonical(Map.of("origin",mode,"value",Map.of("event","record","ordinal",i)),4096),java.nio.charset.StandardCharsets.UTF_8)));
        }finally{for(var child:children)if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(10,TimeUnit.SECONDS));}}
    }
    static void write(V53ProcessTrace trace)throws Exception {
        try(var pool=Executors.newFixedThreadPool(3)) {
            var work=new ArrayList<Future<?>>();
            for(int i=0;i<60;i++){int ordinal=i;work.add(pool.submit(()->trace.add(Map.of("event","record","ordinal",ordinal))));}
            for(var task:work)task.get(10,TimeUnit.SECONDS);
        }
    }
    @Test void outputCannotBeReusedOrRedirectedToAnotherFile()throws Exception {
        Path path=temp.resolve("trace.jsonl");new V53ProcessTrace(path,"parent",true);
        assertThrows(FileAlreadyExistsException.class,()->new V53ProcessTrace(path,"parent",true));
        Path linked=temp.resolve("linked");Files.createSymbolicLink(linked,path);
        assertThrows(IllegalArgumentException.class,()->new V53ProcessTrace(linked,"resume",false));
        assertThrows(IllegalArgumentException.class,()->new V53ProcessTrace(path,"unknown",false));
    }
    @Test void fullTraceFailsWithoutTruncatingEarlierObservations()throws Exception {
        Path path=temp.resolve("trace.jsonl");var recorder=new V53ProcessTrace(path,"parent",true);
        try(var file=FileChannel.open(path,StandardOpenOption.WRITE)) {file.position(64L*1024*1024-1);file.write(ByteBuffer.wrap(new byte[]{'\n'}));}
        assertThrows(IllegalArgumentException.class,()->recorder.add(Map.of("event","over-capacity")));
        assertEquals(64L*1024*1024,Files.size(path));
    }
    public static void main(String[] args)throws Exception {write(new V53ProcessTrace(Path.of(args[0]),args[1],false));}
}
