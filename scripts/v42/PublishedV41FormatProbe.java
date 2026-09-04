import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;

/** Runs the V4.2 exact fixtures through an isolated published V4.1 class path. */
public final class PublishedV41FormatProbe {
    private PublishedV41FormatProbe() {
    }

    public static void main(String[] arguments) {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("expected live and backup directories");
        }
        print("store", DurableStorageOperations.verifyStore(Path.of(arguments[0])));
        print("backup", DurableStorageOperations.verifyBackup(Path.of(arguments[1])));
    }

    private static void print(String kind, DurableVerificationReport report) {
        String findings = report.findings().stream()
                .map(value -> value.code() + ":" + value.member())
                .sorted()
                .reduce((left, right) -> left + "," + right)
                .orElse("-");
        System.out.printf("publishedV41 kind=%s status=%s findings=%s%n",
                kind, report.status(), findings);
    }
}
