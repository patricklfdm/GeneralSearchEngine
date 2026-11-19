package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assumptions.assumeTrue;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.cutDigest;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.hash;

class V53PrefixWholeImageTest {
    @TempDir Path temp;

    // Linux counts bytes read by the calling thread, including page-cache hits.
    // Comparing with this same export's owner checks avoids wall-clock thresholds.
    private static long readBytes(Path counters)throws Exception {
        String value=Files.readAllLines(counters).stream().filter(s->s.startsWith("rchar:")).findFirst().orElseThrow();
        return Long.parseLong(value.substring(6).trim());
    }

    @Test void localImageReadScansItsContentsOnceBetweenOwnerChecks()throws Exception {
        Path counters=Path.of("/proc/thread-self/io");
        assumeTrue(Files.isReadable(counters));
        var helper=new V53SourceImageValidationTest();helper.temp=temp;
        var f=helper.fixture(144);
        try(var owner=f.open(f.request.targets().getFirst(),"whole-prefix")) {
            var state=owner.discoveryState(f.resources);
            try(var export=owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),
                    f.resources,()->0L,0,V53SourceImageValidationTest.BUDGET)) {
                var image=export.references().values().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                assertTrue(image.bytes()>8*1024*1024);
                assertTrue(export.hasImage(image.digest(),image.bytes()));
                long before=readBytes(counters);
                assertTrue(export.hasImage(image.digest(),image.bytes()));
                long ownerRead=readBytes(counters)-before;
                before=readBytes(counters);
                byte[] bytes=export.image(image.digest(),image.bytes());
                long wholeRead=readBytes(counters)-before;
                assertEquals(image.digest(),hash(bytes));
                assertTrue(wholeRead<=2*ownerRead+image.bytes()+1024*1024,
                        "whole-image read bytes="+wholeRead+", owner check bytes="+ownerRead+", image bytes="+image.bytes());
                assertThrows(IllegalArgumentException.class,()->export.read(image.digest(),0,4*1024*1024+1));
            }
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
