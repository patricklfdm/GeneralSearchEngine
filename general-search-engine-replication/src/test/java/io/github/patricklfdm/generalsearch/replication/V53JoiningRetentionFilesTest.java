package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Encoding checks only; these byte arrays are not native owner capabilities. */
class V53JoiningRetentionFilesTest {
    @Test void completionEncodesLedgerFilenamesAsValuesAndBindsEveryOriginal() {
        var files=Map.of(MembershipPeerRetentionFiles.FILE,new byte[]{1},MembershipFutureRetentionFiles.FILE,new byte[]{2},
                MembershipLearnerRetentionFiles.FILE,new byte[]{3});
        byte[] bytes=MembershipJoiningRetentionFiles.completionRecord(Map.of("schema","test-only"),"a".repeat(64),"original-inode",files);
        var header=ByteBuffer.wrap(bytes);assertEquals(0x47534a44,header.getInt());assertEquals(1,header.getShort());assertEquals(3,header.getShort());
        assertEquals(bytes.length,header.getInt());byte[] body=Arrays.copyOfRange(bytes,44,bytes.length);
        assertArrayEquals(sha(body),Arrays.copyOfRange(bytes,12,44));var value=object(parse(body,16384));
        assertEquals("a".repeat(64),value.get("seed"));assertEquals("original-inode",value.get("seedKey"));
        var retained=new TreeMap<String,String>();for(Object raw:list(value.get("files"))){var row=object(raw);assertNull(retained.put((String)row.get("name"),(String)row.get("sha256")));}
        assertEquals(files.keySet(),retained.keySet());files.forEach((name,raw)->assertEquals(hash(raw),retained.get(name)));
        assertArrayEquals(body,canonical(value,16384));assertTrue(bytes.length<MembershipJoiningRetentionFiles.DONE_MAXIMUM);
    }
    @Test void completionCannotOmitAnInitialLedger() {
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionFiles.completionRecord(Map.of(),"a".repeat(64),"inode",
                Map.of(MembershipPeerRetentionFiles.FILE,new byte[]{1},MembershipLearnerRetentionFiles.FILE,new byte[]{2})));
    }
}
