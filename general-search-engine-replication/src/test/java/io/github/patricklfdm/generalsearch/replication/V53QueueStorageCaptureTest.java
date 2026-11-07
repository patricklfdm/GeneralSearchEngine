package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53QueueStorageCaptureTest {
    @TempDir Path temp;

    @Test void originalPathsAreValuesInTheBoundedCanonicalIndex()throws Exception {
        Path image=temp.resolve("generations/g-a/state.image");Files.createDirectories(image.getParent());Files.write(image,new byte[]{1,2,3});
        Path metadata=temp.resolve("sources/s-a/manifest.json");Files.createDirectories(metadata.getParent());Files.write(metadata,new byte[]{4,5});
        var files=V53QueueCompletionQualification.storageFiles(temp);
        assertEquals(List.of("generations/g-a/state.image","sources/s-a/manifest.json"),files.stream().map(row->row.get("path")).toList());
        var point=Map.of("event","SEVEN_SENDS_HELD","node","node-1","eventIndex",10L,
                "beforeSequence",20L,"afterSequence",21L,"files",files);
        var index=Map.of("schema","gse-v53-queue-storage-captures-v1","points",List.of(point));
        assertEquals(index,parse(canonical(index,1024*1024),1024*1024));
        // A protocol object key cannot be a physical path. Keep that contract.
        assertThrows(ReplicationException.class,()->canonical(Map.of("files",V53ReplayFilesTest.files(temp)),1024*1024));
    }

    @Test void identicalImageBytesKeepBothPhysicalPaths()throws Exception {
        for(String name:List.of("generations/g-a/state.image","sources/s-a/state.image")) {
            Path image=temp.resolve(name);Files.createDirectories(image.getParent());Files.write(image,new byte[]{1,2,3});
        }
        var files=V53QueueCompletionQualification.storageFiles(temp);
        assertEquals(2,files.size());assertNotEquals(files.get(0).get("path"),files.get(1).get("path"));
        assertEquals(files.get(0).get("sha256"),files.get(1).get("sha256"));
        assertEquals(Map.of("files",files),parse(canonical(Map.of("files",files),1024*1024),1024*1024));
    }
}
