package io.github.patricklfdm.generalsearch.replication;

/** Queryable certified operation progress. */
public enum MembershipPhase { NOT_FOUND, RESERVED, PREPARING, READY, SEALED, JOINT, COMPLETED, CANCELLED, RETIRED }
