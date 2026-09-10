import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormatReport;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableStoreFormatReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;

/** Proves the immutable published V4.2 reader fails closed on exact V4.3 bytes. */
public final class PublishedV42FormatRejectionProbe {
    private PublishedV42FormatRejectionProbe() {
    }

    public static void main(String[] arguments) {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("expected live and backup directories");
        }
        DurableStoreFormatReport store = DurableStorageOperations.inspectStoreFormat(
                Path.of(arguments[0]));
        DurableBackupFormatReport backup = DurableStorageOperations.inspectBackupFormat(
                Path.of(arguments[1]));
        requireRejected("store", store.structuralReport().status());
        requireRejected("backup", backup.structuralReport().status());
        System.out.printf("publishedV42V12Rejection=PASS store=%s backup=%s%n",
                store.structuralReport().status(),
                backup.structuralReport().status());
    }

    private static void requireRejected(
            String kind,
            DurableVerificationStatus status
    ) {
        if (status == DurableVerificationStatus.VALID
                || status == DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS) {
            throw new IllegalStateException(
                    "published V4.2 accepted V4.3 " + kind + " bytes");
        }
    }
}
