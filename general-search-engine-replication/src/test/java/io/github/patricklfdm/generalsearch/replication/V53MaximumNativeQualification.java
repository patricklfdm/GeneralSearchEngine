package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.AnnotatedElementContext;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.io.CleanupMode;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.io.TempDirFactory;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit long qualification, excluded from the ordinary *Test discovery.
 * Use only the capacity-admitted execution entry; this producer is not admission. */
class V53MaximumNativeQualification {
    @TempDir(factory=WorkspaceTemporaryDirectory.class,cleanup=CleanupMode.ON_SUCCESS) Path temp;
    static final String SEED="maximum-native-seed";
    static void checkConfiguration(){V53BackupJoiningQualification.checkConfiguration();}

    /** Keep live replica and bootstrap storage on the capacity-admitted volume.
     * Failed private work remains available alongside the original observations. */
    public static class WorkspaceTemporaryDirectory implements TempDirFactory {
        @Override public Path createTempDirectory(AnnotatedElementContext element,ExtensionContext context)throws Exception {
            Path root=Path.of("target/v53-maximum-native-work").toAbsolutePath();
            Files.createDirectories(root);
            for(Path path:List.of(root,root.getParent()))
                if(Files.isSymbolicLink(path)||!Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))
                    throw new IllegalStateException("maximum native workspace must be an unlinked directory");
            return Files.createTempDirectory(root,"run-");
        }
    }

    @Test void maximumImageCompletesRequiredFourReplacement()throws Exception {
        checkConfiguration();
        Path evidence=Files.createDirectories(Path.of("target/v53-maximum-native-seed/run-"+UUID.randomUUID()));
        System.out.println("v53MaximumNativeSeedEvidence="+evidence.toAbsolutePath());
        var seed=V53MaximumApplicationTest.captureMaximum(temp,evidence);
        assertEquals(MembershipApplicationImage.MAXIMUM-32,seed.image().length);
        var original=V53ReplayFilesTest.files(seed.source());
        var bootstrap=new V53BootstrapSeedTest();bootstrap.temp=temp;
        var request=bootstrap.request(temp.resolve("group"),5,seed.source());
        var history=new V53JoiningIntentExportTest();history.temp=temp;
        Path raw=history.requiredFourFromVerifiedBackup(request,V53WireArchive.Layout.SEGMENTED_BACKUP,
                V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING);
        assertEquals(original,V53ReplayFilesTest.files(seed.source()));
        assertArrayEquals(seed.image(),Files.readAllBytes(raw.resolve("original-application.image")));
        var binding=new TreeMap<String,Object>();
        binding.put("schema","gse-v53-maximum-native-seed-v1");binding.put("status","PARTIAL");
        binding.put("bootstrapSource",request.source().name());binding.put("wireLayout",V53WireArchive.Layout.SEGMENTED_BACKUP.name());
        binding.put("resourceProfile",V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING.name());
        binding.put("stagingLimit",V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING.stagingBytes);
        binding.put("applicationBytes",(long)seed.image().length);binding.put("applicationSha256",hash(seed.image()));
        binding.put("history",V53MaximumApplicationTest.HISTORY.toString());binding.put("applicationSequence",41L);
        binding.put("extra",(long)seed.extra());binding.put("phase3Complete",false);
        Files.write(evidence.resolve("binding.json"),canonical(binding,16384),StandardOpenOption.CREATE_NEW);
        // Only this newly generated seed observation moves, after the complete
        // history succeeds. The live source and native original are not moved.
        Files.move(evidence,raw.resolve(SEED),StandardCopyOption.ATOMIC_MOVE);
        System.out.println("v53MaximumNativeEvidence="+raw.toAbsolutePath());
    }
}
