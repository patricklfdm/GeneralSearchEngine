package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit complete backup qualification, excluded by the ordinary *Test pattern.
 * Reuses the unchanged required-four history; a passing producer is only PARTIAL. */
class V53BackupJoiningQualification {
    @TempDir Path temp;
    static final List<String> OBSERVATIONS=List.of(
        "v53.joining.requiredFour","v53.publication.resources","v53.resource.transitions",
        "v53.transport.connections","v53.transport.diagnostics","v53.transport.unsent","v53.resource.storage.transfers",
        "v53.resource.owner.close","v53.resource.joined.close","v53.resource.source.control",
        "v53.resource.control.close","v53.resource.export.ownership","v53.resource.slot.control");

    static void checkConfiguration() {
        for(String key:OBSERVATIONS)assertEquals("true",System.getProperty(key),"complete backup observation: "+key);
        assertTrue(System.getProperty("v53.joining.sourceFault","").isEmpty(),"complete backup cannot inject a source fault");
    }

    @Test void verifiedBackupCompletesReplacementFinalAndStableBarrier()throws Exception {
        checkConfiguration();
        var seed=new V53NativeSeedTest();seed.temp=temp;var request=seed.request(5,true);
        var original=V53ReplayFilesTest.files(request.sourcePath().orElseThrow());
        var history=new V53JoiningIntentExportTest();history.temp=temp;
        history.requiredFourFromVerifiedBackup(request,V53WireArchive.Layout.SEGMENTED_BACKUP);
        assertEquals(original,V53ReplayFilesTest.files(request.sourcePath().orElseThrow()));
    }
}
