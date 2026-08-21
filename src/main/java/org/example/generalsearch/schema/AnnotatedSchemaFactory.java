package org.example.generalsearch.schema;

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.reflect.AccessibleObject;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.RecordComponent;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.function.Function;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.schema.annotation.IndexType;
import org.example.generalsearch.schema.annotation.SearchId;
import org.example.generalsearch.schema.annotation.SearchIndex;

public final class AnnotatedSchemaFactory {
    private AnnotatedSchemaFactory() {}

    public static <T, K> AnnotatedSearchConfiguration<T, K> create(
            Class<T> documentType,
            Class<K> idType
    ) {
        Objects.requireNonNull(documentType, "documentType");
        Objects.requireNonNull(idType, "idType");

        List<MemberDefinition<T>> members = documentType.isRecord()
                ? recordMembers(documentType)
                : classMembers(documentType);
        if (members.isEmpty()) {
            throw error(documentType, "no annotated fields or getters were found");
        }

        List<MemberDefinition<T>> ids = members.stream()
                .filter(MemberDefinition::id)
                .toList();
        if (ids.isEmpty()) {
            throw error(documentType, "exactly one @SearchId member is required");
        }
        if (ids.size() > 1) {
            throw error(documentType, "multiple @SearchId members were found");
        }

        MemberDefinition<T> id = ids.getFirst();
        Class<?> expectedIdType = boxed(idType);
        if (id.field().valueType() != expectedIdType) {
            throw error(documentType, "@SearchId field '" + id.field().name()
                    + "' has type " + id.field().valueType().getName()
                    + " but " + expectedIdType.getName() + " was requested");
        }

        Field<T, K> idField = typedIdField(id.field());
        SearchSchema.Builder<T, K> schema = SearchSchema.builder(documentType, idField);
        List<IndexDefinition<T>> indexes = new ArrayList<>();
        for (MemberDefinition<T> member : members) {
            schema.field(member.field());
            if (member.indexType() != null) {
                indexes.add(indexDefinition(documentType, member));
            }
        }
        return new AnnotatedSearchConfiguration<>(schema.build(), indexes);
    }

    private static <T> List<MemberDefinition<T>> recordMembers(Class<T> documentType) {
        List<MemberDefinition<T>> members = new ArrayList<>();
        for (RecordComponent component : documentType.getRecordComponents()) {
            Method accessor = component.getAccessor();
            makeAccessible(documentType, accessor, "record accessor " + accessor.getName());
            members.add(new MemberDefinition<>(
                    field(
                            component.getName(),
                            component.getType(),
                            methodExtractor(documentType, accessor)
                    ),
                    component.isAnnotationPresent(SearchId.class),
                    indexType(component.getAnnotation(SearchIndex.class))
            ));
        }
        return List.copyOf(members);
    }

    private static <T> List<MemberDefinition<T>> classMembers(Class<T> documentType) {
        List<MemberDefinition<T>> members = new ArrayList<>();
        List<Class<?>> hierarchy = hierarchy(documentType);
        for (Class<?> type : hierarchy) {
            for (java.lang.reflect.Field reflectedField : type.getDeclaredFields()) {
                SearchId id = reflectedField.getAnnotation(SearchId.class);
                SearchIndex index = reflectedField.getAnnotation(SearchIndex.class);
                if (id == null && index == null) {
                    continue;
                }
                if (Modifier.isStatic(reflectedField.getModifiers())) {
                    throw error(documentType, "annotated field must not be static: "
                            + reflectedField.getName());
                }
                makeAccessible(
                        documentType,
                        reflectedField,
                        "field " + reflectedField.getName()
                );
                members.add(new MemberDefinition<>(
                        field(
                                reflectedField.getName(),
                                reflectedField.getType(),
                                fieldExtractor(documentType, reflectedField)
                        ),
                        id != null,
                        indexType(index)
                ));
            }
            for (Method method : type.getDeclaredMethods()) {
                SearchId id = method.getAnnotation(SearchId.class);
                SearchIndex index = method.getAnnotation(SearchIndex.class);
                if (id == null && index == null) {
                    continue;
                }
                validateGetter(documentType, method);
                makeAccessible(documentType, method, "getter " + method.getName());
                members.add(new MemberDefinition<>(
                        field(
                                propertyName(method),
                                method.getReturnType(),
                                methodExtractor(documentType, method)
                        ),
                        id != null,
                        indexType(index)
                ));
            }
        }
        members.sort(Comparator.comparing(member -> member.field().name()));
        rejectDuplicateNames(documentType, members);
        return List.copyOf(members);
    }

    private static List<Class<?>> hierarchy(Class<?> documentType) {
        List<Class<?>> hierarchy = new ArrayList<>();
        for (Class<?> type = documentType;
             type != null && type != Object.class;
             type = type.getSuperclass()) {
            hierarchy.add(type);
        }
        Collections.reverse(hierarchy);
        return hierarchy;
    }

    private static <T> void rejectDuplicateNames(
            Class<T> documentType,
            List<MemberDefinition<T>> members
    ) {
        for (int index = 1; index < members.size(); index++) {
            String previous = members.get(index - 1).field().name();
            String current = members.get(index).field().name();
            if (previous.equals(current)) {
                throw error(documentType, "duplicate annotated field name: " + current);
            }
        }
    }

    private static void validateGetter(Class<?> documentType, Method method) {
        if (Modifier.isStatic(method.getModifiers())) {
            throw error(documentType, "annotated getter must not be static: "
                    + method.getName());
        }
        if (method.getParameterCount() != 0 || method.getReturnType() == void.class) {
            throw error(documentType, "annotated method must be a zero-argument getter: "
                    + method.getName());
        }
    }

    private static String propertyName(Method method) {
        String name = method.getName();
        if (name.startsWith("get") && name.length() > 3) {
            return decapitalize(name.substring(3));
        }
        if (name.startsWith("is") && name.length() > 2
                && (method.getReturnType() == boolean.class
                || method.getReturnType() == Boolean.class)) {
            return decapitalize(name.substring(2));
        }
        return name;
    }

    private static String decapitalize(String value) {
        if (value.length() > 1
                && Character.isUpperCase(value.charAt(0))
                && Character.isUpperCase(value.charAt(1))) {
            return value;
        }
        return Character.toLowerCase(value.charAt(0)) + value.substring(1);
    }

    private static void makeAccessible(
            Class<?> documentType,
            AccessibleObject member,
            String description
    ) {
        try {
            if (!member.trySetAccessible()) {
                throw error(documentType, "cannot access private " + description);
            }
        } catch (SecurityException failure) {
            throw new SchemaGenerationException(
                    "Cannot access " + description + " on " + documentType.getName(),
                    failure
            );
        }
    }

    private static <T> Function<T, Object> fieldExtractor(
            Class<T> documentType,
            java.lang.reflect.Field field
    ) {
        MethodHandle handle;
        try {
            handle = MethodHandles.lookup().unreflectGetter(field);
        } catch (IllegalAccessException failure) {
            throw new SchemaGenerationException(
                    "Cannot bind field " + field.getName() + " on "
                            + documentType.getName(),
                    failure
            );
        }
        return document -> invoke(handle, document, "field " + field.getName());
    }

    private static <T> Function<T, Object> methodExtractor(
            Class<T> documentType,
            Method method
    ) {
        MethodHandle handle;
        try {
            handle = MethodHandles.lookup().unreflect(method);
        } catch (IllegalAccessException failure) {
            throw new SchemaGenerationException(
                    "Cannot bind getter " + method.getName() + " on "
                            + documentType.getName(),
                    failure
            );
        }
        return document -> invoke(handle, document, "getter " + method.getName());
    }

    private static Object invoke(
            MethodHandle handle,
            Object document,
            String description
    ) {
        try {
            return handle.invoke(document);
        } catch (RuntimeException | Error failure) {
            throw failure;
        } catch (Throwable failure) {
            throw new IllegalStateException(description + " failed", failure);
        }
    }

    @SuppressWarnings("unchecked")
    private static <T, V> Field<T, V> field(
            String name,
            Class<?> valueType,
            Function<T, Object> extractor
    ) {
        return Field.of(
                name,
                (Class<V>) boxed(valueType),
                document -> (V) extractor.apply(document)
        );
    }

    private static IndexType indexType(SearchIndex annotation) {
        return annotation == null ? null : annotation.value();
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static <T> IndexDefinition<T> indexDefinition(
            Class<T> documentType,
            MemberDefinition<T> member
    ) {
        return switch (member.indexType()) {
            case EQUALITY -> IndexDefinition.equality((Field) member.field());
            case RANGE -> {
                if (!supportsNaturalRange(member.field().valueType())) {
                    throw error(documentType, "RANGE index requires a Comparable field: "
                            + member.field().name());
                }
                yield IndexDefinition.range((Field) member.field());
            }
            case PREFIX -> {
                if (member.field().valueType() != String.class) {
                    throw error(documentType, "PREFIX index requires a String field: "
                            + member.field().name());
                }
                yield IndexDefinition.prefix((Field) member.field());
            }
        };
    }

    private static boolean supportsNaturalRange(Class<?> valueType) {
        if (valueType.isEnum()) {
            return true;
        }
        return hasCompatibleComparable(valueType, valueType);
    }

    private static boolean hasCompatibleComparable(
            Class<?> valueType,
            Class<?> inspectedType
    ) {
        for (Type interfaceType : inspectedType.getGenericInterfaces()) {
            if (isCompatibleComparable(valueType, interfaceType)) {
                return true;
            }
            Class<?> rawInterface = rawClass(interfaceType);
            if (rawInterface != null
                    && rawInterface != Comparable.class
                    && hasCompatibleComparable(valueType, rawInterface)) {
                return true;
            }
        }
        Class<?> superclass = inspectedType.getSuperclass();
        return superclass != null
                && superclass != Object.class
                && hasCompatibleComparable(valueType, superclass);
    }

    private static boolean isCompatibleComparable(Class<?> valueType, Type interfaceType) {
        if (!(interfaceType instanceof ParameterizedType parameterized)
                || parameterized.getRawType() != Comparable.class) {
            return false;
        }
        Class<?> comparisonType = rawClass(parameterized.getActualTypeArguments()[0]);
        return comparisonType != null && comparisonType.isAssignableFrom(valueType);
    }

    private static Class<?> rawClass(Type type) {
        if (type instanceof Class<?> rawClass) {
            return rawClass;
        }
        if (type instanceof ParameterizedType parameterized
                && parameterized.getRawType() instanceof Class<?> rawClass) {
            return rawClass;
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static <T, K> Field<T, K> typedIdField(Field<T, ?> field) {
        return (Field<T, K>) field;
    }

    private static Class<?> boxed(Class<?> type) {
        if (!type.isPrimitive()) {
            return type;
        }
        if (type == boolean.class) {
            return Boolean.class;
        }
        if (type == byte.class) {
            return Byte.class;
        }
        if (type == short.class) {
            return Short.class;
        }
        if (type == int.class) {
            return Integer.class;
        }
        if (type == long.class) {
            return Long.class;
        }
        if (type == float.class) {
            return Float.class;
        }
        if (type == double.class) {
            return Double.class;
        }
        if (type == char.class) {
            return Character.class;
        }
        if (type == void.class) {
            return Void.class;
        }
        throw new IllegalArgumentException("unknown primitive type: " + type.getName());
    }

    private static SchemaGenerationException error(
            Class<?> documentType,
            String detail
    ) {
        return new SchemaGenerationException(
                "Cannot generate schema for " + documentType.getName() + ": " + detail);
    }

    private record MemberDefinition<T>(
            Field<T, ?> field,
            boolean id,
            IndexType indexType
    ) {}
}
