package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53LearnerResourceCaptureTest {
    @TempDir Path temp;
    @Test void returnObservationRequiresSuccessfulOriginalClose()throws Exception {
        var capture=new V53LearnerResourceCapture(temp.resolve("capture"));
        var lease=capture.resources.reserve(MembershipResources.Unit.CONTROL,"original",19);
        var failure=new IOException("original close failure");
        var failed=V53LearnerResourceCapture.own(capture,"failed",()->{throw failure;});
        assertSame(failure,assertThrows(IOException.class,failed::close));
        assertEquals(19,capture.resources.usage().queued());
        assertEquals("CLOSE_BEGIN",capture.rows.getLast().get("kind"));
        assertFalse(capture.rows.stream().anyMatch(row->row.get("kind").equals("CLOSE_RETURN")));
        var owned=V53LearnerResourceCapture.own(capture,"drain",lease);
        owned.close();assertEquals(0,capture.resources.usage().leases());
        assertEquals("CLOSE_BEGIN",capture.rows.get(capture.rows.size()-2).get("kind"));
        assertEquals("CLOSE_RETURN",capture.rows.getLast().get("kind"));
        assertTrue(((Number)capture.rows.getLast().get("sequence")).longValue()>
                ((Number)capture.rows.get(capture.rows.size()-2).get("sequence")).longValue());
    }
}
