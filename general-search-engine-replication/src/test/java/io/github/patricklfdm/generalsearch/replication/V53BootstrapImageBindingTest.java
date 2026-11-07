package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableApplicationState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real small bootstrap binding, not maximum native or network qualification. */
class V53BootstrapImageBindingTest {
    @TempDir Path temp;

    @Test void importedContentIsReboundToNewHistoryAndDifferentBytes()throws Exception {
        var config=builder().configuration();var documents=List.of(new Doc(7,"original"),new Doc(2,"shared"));
        UUID imported=V53MaximumApplicationTest.HISTORY;
        Path source=temp.resolve("source");var core=storage(temp.resolve("source-core"),2);
        byte[] original=MembershipApplicationImage.capture(config,core,
                new DurableApplicationState<>(imported,41,documents,config.indexes()),source);
        var helper=new V53BootstrapSeedTest();helper.temp=temp;
        var raw=Files.createDirectories(Path.of("target/v53-bootstrap-rebinding/run-"+UUID.randomUUID()));
        System.out.println("v53BootstrapRebindingEvidence="+raw.toAbsolutePath());
        var fixture=new V53BootstrapPublicationTest.Fixture(raw,helper.request(temp.resolve("group"),3,source));
        var before=V53ReplayFilesTest.files(source);byte[] bootstrapped=fixture.original.seed.application();
        assertFalse(Arrays.equals(original,bootstrapped));assertEquals(original.length,bootstrapped.length);
        var binding=V53MaximumNativeQualification.reboundImage(raw,original,imported,temp.resolve("inspect"));
        assertEquals(fixture.result.root().historyId().toString(),binding.get("bootstrapHistory"));
        assertEquals(hash(bootstrapped),binding.get("bootstrapApplicationSha256"));
        assertNotEquals(imported.toString(),binding.get("bootstrapHistory"));
        assertThrows(AssertionError.class,()->V53MaximumNativeQualification.reboundImage(raw,original,
                UUID.randomUUID(),temp.resolve("wrong-history")));
        byte[] changed=MembershipApplicationImage.capture(config,core,
                new DurableApplicationState<>(imported,41,List.of(new Doc(7,"modified"),new Doc(2,"shared")),config.indexes()),temp.resolve("changed-source"));
        assertThrows(AssertionError.class,()->V53MaximumNativeQualification.reboundImage(raw,changed,imported,temp.resolve("wrong-content")));
        byte[] wrongSequence=MembershipApplicationImage.capture(config,core,
                new DurableApplicationState<>(imported,42,documents,config.indexes()),temp.resolve("changed-sequence"));
        assertThrows(AssertionError.class,()->V53MaximumNativeQualification.reboundImage(raw,wrongSequence,imported,temp.resolve("wrong-sequence")));
        Files.write(raw.resolve("original-application.image"),original);
        try {
            assertThrows(IllegalArgumentException.class,()->V53MaximumNativeQualification.reboundImage(raw,original,imported,temp.resolve("wrong-plan")));
        }finally{Files.write(raw.resolve("original-application.image"),bootstrapped);}
        assertEquals(before,V53ReplayFilesTest.files(source));
        Files.write(raw.resolve("source.image"),original);
        V53JournalApplicationTest.copy(source,raw.resolve("source-backup"));
        Files.write(raw.resolve("binding.json"),canonical(binding,4096));
    }
}
