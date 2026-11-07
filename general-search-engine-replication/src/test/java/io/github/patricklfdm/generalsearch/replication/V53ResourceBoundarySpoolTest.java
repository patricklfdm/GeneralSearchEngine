package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;

/** Original capture order and file contracts, not maximum runtime qualification. */
class V53ResourceBoundarySpoolTest {
    @TempDir Path temp;
    static final String ROOT="a".repeat(64);
    static final Map<String,Object> OPEN=Map.of("node","node-1","event","OPEN");
    static MembershipIdentity identity(int node){return V53ResourceTransitionCaptureTest.identity(node);}
    static V53ResourceTransitionCapture capture(Path root,boolean spooled)throws Exception {
        return new V53ResourceTransitionCapture(root,ROOT,List.of(),true,false,spooled);
    }
    static Path boundaries(Path root){return root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/boundaries.json");}
    static Path index(Path root){return root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/index.json");}

    private void original(Path root,boolean spooled)throws Exception {
        try(var capture=capture(root,spooled);var events=new V53EvidenceSpool(root.resolve("events.json"),4096,capture::event)) {
            var first=capture.create(identity(1),0);
            try(var journal=first.reserve(Unit.JOURNAL,"journal",20)) {
                events.add(OPEN);var joining=capture.create(identity(2),1);
                try(var learner=joining.reserve(Unit.LEARNER,"learner",30)){events.add(Map.of("node","node-2","event","ADMIT"));}
                events.add(Map.of("node","node-2","event","CLOSE"));
            }
            events.add(Map.of("node","node-1","event","CLOSE"));
            events.close();capture.save(events);
        }
    }
    @Test void completeFilesAndIndexesMatchTheLegacyCollectorByteForByte()throws Exception {
        Path legacy=Files.createDirectory(temp.resolve("legacy")),spooled=Files.createDirectory(temp.resolve("spooled"));
        String property="v53.resource.storage.transfers",before=System.getProperty(property);
        try{System.setProperty(property,"true");original(legacy,false);original(spooled,true);}
        finally{if(before==null)System.clearProperty(property);else System.setProperty(property,before);}
        assertEquals(V53ReplayFilesTest.files(legacy),V53ReplayFilesTest.files(spooled));
        assertEquals(4,list(parse(Files.readAllBytes(boundaries(spooled)),8192)).size());
        var value=object(parse(Files.readAllBytes(index(spooled)),16384));
        assertEquals(hash(Files.readAllBytes(boundaries(spooled))),value.get("boundariesSha256"));
        assertEquals(hash(Files.readAllBytes(spooled.resolve("events.json"))),value.get("eventsSha256"));
    }
    @Test void unfinishedCloseRetainsThePrefixWithoutInventingAnIndex()throws Exception {
        var capture=capture(temp,true);capture.create(identity(1),0);capture.event(0,OPEN);
        assertFalse(Files.readString(boundaries(temp)).endsWith("]"));
        capture.close();capture.close();assertTrue(Files.readString(boundaries(temp)).endsWith("]"));
        assertFalse(Files.exists(index(temp)));assertEquals(1,list(parse(Files.readAllBytes(boundaries(temp)),4096)).size());
        assertThrows(IllegalArgumentException.class,()->capture.save(canonical(List.of(OPEN),4096)));
        assertThrows(IllegalArgumentException.class,()->capture.create(identity(2),1));
        assertThrows(IllegalArgumentException.class,()->capture.event(1,OPEN));
    }
    @Test void observerOrderFailureCannotBeCaughtAndThenSavedAsACompleteCapture()throws Exception {
        var capture=capture(temp,true);capture.create(identity(1),0);capture.event(0,OPEN);
        var failure=assertThrows(IllegalArgumentException.class,()->capture.event(2,OPEN));
        assertEquals("resource capture event capacity/order",failure.getMessage());
        assertSame(failure,assertThrows(IllegalStateException.class,()->capture.event(1,OPEN)).getCause());
        assertSame(failure,assertThrows(IllegalStateException.class,()->capture.save(canonical(List.of(OPEN),4096))).getCause());
        assertSame(failure,assertThrows(IllegalStateException.class,capture::close).getCause());capture.close();
        assertFalse(Files.exists(index(temp)));assertEquals(1,list(parse(Files.readAllBytes(boundaries(temp)),4096)).size());
    }
    @Test void changedBoundaryBytesCannotAcquireAnIndexEvenWithUnchangedExtent()throws Exception {
        var capture=capture(temp,true);capture.create(identity(1),0);capture.event(0,OPEN);
        var path=boundaries(temp);String changed=Files.readString(path).replace("node-1","node-2");
        long size=Files.size(path);Files.writeString(path,changed);assertEquals(size,Files.size(path));
        assertEquals("evidence spool content changed",assertThrows(IllegalArgumentException.class,
                ()->capture.save(canonical(List.of(OPEN),4096))).getMessage());
        capture.close();assertEquals(changed,Files.readString(path));assertFalse(Files.exists(index(temp)));
    }
    @Test void coupledEventAndBoundaryFailurePreservesTheOriginalExceptionAndClosesBoth()throws Exception {
        var capture=capture(temp,true);capture.create(identity(1),0);
        var events=new V53EvidenceSpool(temp.resolve("events.json"),4096,capture::event);
        var failure=assertThrows(IllegalArgumentException.class,()->{
            try(capture;events){events.add(Map.of("node","node-2","event","UNKNOWN_OWNER"));}
        });
        assertEquals("resource capture unknown event owner",failure.getMessage());assertEquals(2,failure.getSuppressed().length);
        for(var suppressed:failure.getSuppressed())assertSame(failure,suppressed.getCause());
        assertEquals("[",Files.readString(temp.resolve("events.json")));assertEquals("[]",Files.readString(boundaries(temp)));
        assertFalse(Files.exists(index(temp)));capture.close();events.close();
    }
    @Test void bothCollectorsReachTheUnchangedRowLimitUnderA32MiBHeap()throws Exception {
        Path root=Files.createDirectory(temp.resolve("heap")),log=temp.resolve("heap.log");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin","java").toString(),"-Xmx32m","-cp",
                System.getProperty("surefire.test.class.path",System.getProperty("java.class.path")),HeapProbe.class.getName(),root.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            assertTrue(process.waitFor(90,TimeUnit.SECONDS),"bounded boundary probe did not finish");
            assertEquals(0,process.exitValue(),Files.readString(log));assertEquals("rows=65536\n",Files.readString(log));
            assertTrue(Files.size(boundaries(root))>8L*1024*1024);assertTrue(Files.size(boundaries(root))<V53EvidenceArray.EVENT_BYTES);
        }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
    }
    public static final class HeapProbe {
        static String digest(Path path)throws Exception {
            var digest=java.security.MessageDigest.getInstance("SHA-256");
            try(var input=Files.newInputStream(path)){byte[] buffer=new byte[65536];int count;while((count=input.read(buffer))!=-1)digest.update(buffer,0,count);}
            return HexFormat.of().formatHex(digest.digest());
        }
        public static void main(String[] args)throws Exception {
            Path root=Path.of(args[0]);
            try(var capture=capture(root,true);var events=new V53EvidenceSpool(root.resolve("events.json"),V53EvidenceArray.EVENT_BYTES,capture::event)) {
                var budget=capture.create(identity(1),0);var lease=budget.reserve(Unit.SOURCE,"original",1024);
                try(lease) {
                    for(int i=0;i<V53EvidenceArray.HISTORY_ROWS;i++) {
                        if(i==V53EvidenceArray.HISTORY_ROWS-1)lease.close();
                        events.add(OPEN);
                    }
                }
                events.close();capture.save(events);
            }
            var value=object(parse(Files.readAllBytes(index(root)),16384));
            if(!value.get("eventsSha256").equals(digest(root.resolve("events.json"))) || !value.get("boundariesSha256").equals(digest(boundaries(root))))
                throw new IllegalStateException("original streamed index hashes");
            System.out.println("rows="+V53EvidenceArray.HISTORY_ROWS);
        }
    }
}
