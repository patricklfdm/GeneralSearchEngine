package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.regex.Pattern;

/** One bounded component rejection retained by a reopen report. */
public record DurableReopenRejection(int ordinal, String code) {
    private static final Pattern CODE = Pattern.compile("[A-Z][A-Z0-9_]{0,63}");

    public DurableReopenRejection {
        if (ordinal < 0 || ordinal >= 100_000) {
            throw new IllegalArgumentException("ordinal is outside its bound");
        }
        code = Objects.requireNonNull(code, "code");
        if (!CODE.matcher(code).matches()) {
            throw new IllegalArgumentException("code is not a stable identifier");
        }
    }
}
