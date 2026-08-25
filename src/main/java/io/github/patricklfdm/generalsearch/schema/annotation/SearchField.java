package io.github.patricklfdm.generalsearch.schema.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Includes a class field or getter in its generated search schema without creating a
 * startup index. Record components are already included automatically; the annotation
 * may still be used there to make searchable intent explicit.
 */
@Documented
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.RECORD_COMPONENT, ElementType.FIELD, ElementType.METHOD})
public @interface SearchField {}
