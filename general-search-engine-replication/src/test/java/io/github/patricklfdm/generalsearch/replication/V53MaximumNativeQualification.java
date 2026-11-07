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
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Explicit long qualification, excluded from the ordinary *Test discovery.
 * Use only the capacity-admitted execution entry; this producer is not admission. */
class V53MaximumNativeQualification {
    @TempDir(factory=WorkspaceTemporaryDirectory.class,cleanup=CleanupMode.ON_SUCCESS) Path temp;
    static final String SEED="maximum-native-seed";
    static void checkConfiguration(){V53BackupJoiningQualification.checkConfiguration();}

    /** Bootstrap preserves application content, but allocates a new history. */
    static Map<String,Object> reboundImage(Path raw,byte[] sourceImage,UUID sourceHistory,Path scratch)throws Exception {
        byte[] image=Files.readAllBytes(raw.resolve("original-application.image"));
        var plan=MembershipBootstrapPlanData.decode(Files.readAllBytes(raw.resolve("original-plan.gsbp")),image);
        assertEquals(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP.name(),plan.seed.descriptor().get("source"));
        assertNotEquals(sourceHistory,plan.seed.root.historyId());
        Files.createDirectories(scratch);var config=builder().configuration();var core=storage(scratch.resolve("core-anchor"),2);
        var imported=MembershipApplicationImage.read(config,core,sourceImage,scratch.resolve("imported"));
        var bootstrapped=MembershipApplicationImage.read(config,core,image,scratch.resolve("bootstrapped"));
        assertEquals(sourceHistory,imported.history());assertEquals(plan.seed.root.historyId(),bootstrapped.history());
        assertEquals(plan.seed.sequence,bootstrapped.sequence());
        assertEquals(imported.sequence(),bootstrapped.sequence());assertEquals(imported.documents(),bootstrapped.documents());
        assertEquals(imported.indexes().stream().map(ReplicaApplication::descriptor).toList(),
                bootstrapped.indexes().stream().map(ReplicaApplication::descriptor).toList());
        assertEquals(sourceImage.length,image.length);assertFalse(Arrays.equals(sourceImage,image));
        return Map.of("bootstrapHistory",bootstrapped.history().toString(),"bootstrapApplicationSha256",hash(image));
    }

    static Map<String,Object> seedBinding(V53MaximumApplicationTest.Seed seed,Path raw,Path scratch)throws Exception {
        assertEquals(MembershipApplicationImage.MAXIMUM-32,seed.image().length);
        var binding=new TreeMap<String,Object>(reboundImage(raw,seed.image(),V53MaximumApplicationTest.HISTORY,scratch));
        binding.put("schema","gse-v53-maximum-native-seed-v2");binding.put("status","PARTIAL");
        binding.put("bootstrapSource",MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP.name());
        binding.put("wireLayout",V53WireArchive.Layout.SEGMENTED_BACKUP.name());
        binding.put("resourceProfile",V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING.name());
        binding.put("stagingLimit",V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING.stagingBytes);
        binding.put("applicationBytes",(long)seed.image().length);binding.put("applicationSha256",hash(seed.image()));
        binding.put("history",V53MaximumApplicationTest.HISTORY.toString());binding.put("applicationSequence",41L);
        binding.put("extra",(long)seed.extra());binding.put("phase3Complete",false);
        return binding;
    }

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
        var binding=seedBinding(seed,raw,temp.resolve("seed-inspection"));
        Files.write(evidence.resolve("binding.json"),canonical(binding,16384),StandardOpenOption.CREATE_NEW);
        // Only this newly generated seed observation moves, after the complete
        // history succeeds. The live source and native original are not moved.
        Files.move(evidence,raw.resolve(SEED),StandardCopyOption.ATOMIC_MOVE);
        System.out.println("v53MaximumNativeEvidence="+raw.toAbsolutePath());
    }
}
