package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;

/** Exact internal encoding context for one admitted durable minor. */
final class DurableFormatContext {
    static final short MAJOR = 1;
    static final short MINOR_1_0 = 0;
    static final short MINOR_1_1 = 1;
    static final short MINOR_1_2 = 2;
    static final String FAMILY = "gse-durable";
    static final DurableFormatContext V1_0 = new DurableFormatContext(
            DurableStorageFormat.V1_0, new byte[0], new byte[0]);
    static final DurableFormatContext V1_1;
    static final DurableFormatContext V1_2;

    private static final byte[] PROFILE_DOMAIN =
            "gse-durable-format-profile-v1\0"
                    .getBytes(StandardCharsets.US_ASCII);
    private static final List<String> REQUIRED_CAPABILITIES_V1_1 = List.of(
            "canonical-documents-v1",
            "checkpoint-authority-v1",
            "crc32c-wal-v1",
            "logical-index-config-v1",
            "sha256-profile-binding-v1");
    private static final List<String> REQUIRED_CAPABILITIES_V1_2 = List.of(
            "canonical-documents-v1",
            "checkpoint-authority-v1",
            "crc32c-wal-v1",
            "logical-index-config-v1",
            "reconstructible-derived-index-images-v1",
            "sha256-profile-binding-v1");

    static {
        byte[] profile = encodeProfile(REQUIRED_CAPABILITIES_V1_1);
        MessageDigest digest = sha256();
        digest.update(PROFILE_DOMAIN);
        digest.update(profile);
        V1_1 = new DurableFormatContext(
                DurableStorageFormat.V1_1, profile, digest.digest());
        profile = encodeProfile(REQUIRED_CAPABILITIES_V1_2);
        digest = sha256();
        digest.update(PROFILE_DOMAIN);
        digest.update(profile);
        V1_2 = new DurableFormatContext(
                DurableStorageFormat.V1_2, profile, digest.digest());
    }

    private final DurableStorageFormat publicFormat;
    private final byte[] profile;
    private final byte[] profileDigest;

    private DurableFormatContext(
            DurableStorageFormat publicFormat,
            byte[] profile,
            byte[] profileDigest
    ) {
        this.publicFormat = publicFormat;
        this.profile = profile.clone();
        this.profileDigest = profileDigest.clone();
    }

    static DurableFormatContext from(DurableStorageFormat format) {
        if (DurableStorageFormat.V1_0.equals(format)) {
            return V1_0;
        }
        if (DurableStorageFormat.V1_1.equals(format)) {
            return V1_1;
        }
        if (DurableStorageFormat.V1_2.equals(format)) {
            return V1_2;
        }
        throw new DurabilityException(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                "configured durable format is not supported");
    }

    static DurableFormatContext from(short major, short minor, String family) {
        if (major != MAJOR || !FAMILY.equals(family)) {
            throw new DurabilityException(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "durable metadata format family or major is unsupported");
        }
        return switch (minor) {
            case MINOR_1_0 -> V1_0;
            case MINOR_1_1 -> V1_1;
            case MINOR_1_2 -> V1_2;
            default -> throw new DurabilityException(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "durable metadata minor is incompatible");
        };
    }

    DurableStorageFormat publicFormat() {
        return publicFormat;
    }

    short minor() {
        return (short) publicFormat.minor();
    }

    boolean hasProfile() {
        return minor() != MINOR_1_0;
    }

    byte[] profile() {
        return profile.clone();
    }

    byte[] profileDigest() {
        return profileDigest.clone();
    }

    boolean matchesProfile(byte[] encoded, byte[] digest) {
        return Arrays.equals(profile, encoded)
                && Arrays.equals(profileDigest, digest);
    }

    boolean matchesDigest(byte[] digest) {
        return Arrays.equals(profileDigest, digest);
    }

    int walHeaderBytes() {
        return hasProfile() ? 80 : 48;
    }

    int checkpointFixedBytes() {
        return hasProfile() ? 88 : 56;
    }

    int manifestMinimumBytes() {
        return hasProfile() ? 104 : 72;
    }

    private static byte[] encodeProfile(List<String> requiredCapabilities) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                output.writeInt(requiredCapabilities.size());
                for (String capability : requiredCapabilities) {
                    writeString(output, capability);
                }
                output.writeInt(0);
            }
            return bytes.toByteArray();
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }
}
