package io.github.patricklfdm.generalsearch.durability;

import java.util.Comparator;
import java.util.Objects;
import java.util.regex.Pattern;

/** One bounded, payload-free derived-state diagnostic. */
public record DurableDerivedFinding(String code, String member, String detail) {
    private static final Pattern CODE = Pattern.compile("[A-Z][A-Z0-9_]{0,63}");
    static final Comparator<DurableDerivedFinding> CANONICAL_ORDER =
            Comparator.comparing(DurableDerivedFinding::code)
                    .thenComparing(DurableDerivedFinding::member)
                    .thenComparing(DurableDerivedFinding::detail);

    /** Validates stable code and bounded single-line diagnostic text. */
    public DurableDerivedFinding {
        code = Objects.requireNonNull(code, "code");
        member = bounded(member, "member", 256);
        detail = bounded(detail, "detail", 4096);
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
