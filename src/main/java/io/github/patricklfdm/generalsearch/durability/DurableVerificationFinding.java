package io.github.patricklfdm.generalsearch.durability;

import java.util.Comparator;
import java.util.Objects;
import java.util.regex.Pattern;

/** One bounded, payload-free structural-verification diagnostic. */
public record DurableVerificationFinding(String code, String member, String detail) {
    private static final Pattern CODE = Pattern.compile("[A-Z][A-Z0-9_]{0,63}");
    private static final int MAX_MEMBER_CHARS = 256;
    private static final int MAX_DETAIL_CHARS = 512;
    static final Comparator<DurableVerificationFinding> CANONICAL_ORDER =
            Comparator.comparing(DurableVerificationFinding::code)
                    .thenComparing(DurableVerificationFinding::member)
                    .thenComparing(DurableVerificationFinding::detail);

    /** Validates the stable code and bounded member/detail text. */
    public DurableVerificationFinding {
        code = Objects.requireNonNull(code, "code");
        member = bounded(member, "member", MAX_MEMBER_CHARS);
        detail = bounded(detail, "detail", MAX_DETAIL_CHARS);
        if (!CODE.matcher(code).matches()) {
            throw new IllegalArgumentException(
                    "code must match [A-Z][A-Z0-9_]{0,63}");
        }
    }

    private static String bounded(String value, String name, int maximum) {
        Objects.requireNonNull(value, name);
        if (value.isEmpty() || value.length() > maximum
                || value.indexOf('\n') >= 0 || value.indexOf('\r') >= 0) {
            throw new IllegalArgumentException(
                    name + " must be non-empty, single-line, and at most "
                            + maximum + " characters");
        }
        return value;
    }
}
