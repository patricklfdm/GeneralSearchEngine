package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;

/** Additive query-planner configuration. */
public record PlannerConfig(RangePlanningMode rangePlanningMode) {
    /** Default cost-aware v2 planner configuration. */
    public static final PlannerConfig DEFAULT =
            new PlannerConfig(RangePlanningMode.COST_AWARE);

    public PlannerConfig {
        Objects.requireNonNull(rangePlanningMode, "rangePlanningMode");
    }
}
