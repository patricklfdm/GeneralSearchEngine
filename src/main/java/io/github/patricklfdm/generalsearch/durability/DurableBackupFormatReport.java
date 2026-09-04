package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

/** Codec-free backup/source declarations combined with structural bundle evidence. */
public record DurableBackupFormatReport(
        DurableVerificationReport structuralReport,
        Optional<DurableBackupFormat> declaredFormat,
        Optional<DurableStorageFormat> sourceFormat,
        Optional<String> profileDigest
) {
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    /** Freezes non-null optional values and validates any declared profile digest. */
    public DurableBackupFormatReport {
        structuralReport = Objects.requireNonNull(structuralReport, "structuralReport");
        declaredFormat = Objects.requireNonNull(declaredFormat, "declaredFormat");
        sourceFormat = Objects.requireNonNull(sourceFormat, "sourceFormat");
        profileDigest = Objects.requireNonNull(profileDigest, "profileDigest");
        profileDigest.ifPresent(value -> {
            if (!SHA256.matcher(value).matches()) {
                throw new IllegalArgumentException(
                        "profileDigest must be 64 lowercase hexadecimal characters");
            }
        });
    }
}
