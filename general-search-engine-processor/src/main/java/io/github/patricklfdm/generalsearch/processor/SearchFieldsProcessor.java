package io.github.patricklfdm.generalsearch.processor;

import java.io.IOException;
import java.io.Writer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import javax.annotation.processing.AbstractProcessor;
import javax.annotation.processing.FilerException;
import javax.annotation.processing.Generated;
import javax.annotation.processing.RoundEnvironment;
import javax.annotation.processing.SupportedAnnotationTypes;
import javax.lang.model.SourceVersion;
import javax.lang.model.element.AnnotationMirror;
import javax.lang.model.element.AnnotationValue;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.PackageElement;
import javax.lang.model.element.RecordComponentElement;
import javax.lang.model.element.TypeElement;
import javax.lang.model.element.VariableElement;
import javax.lang.model.type.ArrayType;
import javax.lang.model.type.DeclaredType;
import javax.lang.model.type.PrimitiveType;
import javax.lang.model.type.TypeKind;
import javax.lang.model.type.TypeMirror;
import javax.tools.Diagnostic;
import javax.tools.JavaFileObject;

/** Generates one canonical {@code *SearchFields} companion for annotated documents. */
@SupportedAnnotationTypes({
        SearchFieldsProcessor.SEARCH_ID,
        SearchFieldsProcessor.SEARCH_INDEX
})
public final class SearchFieldsProcessor extends AbstractProcessor {
    static final String SEARCH_ID =
            "io.github.patricklfdm.generalsearch.schema.annotation.SearchId";
    static final String SEARCH_INDEX =
            "io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex";
    private static final String FIELD =
            "io.github.patricklfdm.generalsearch.schema.Field";
    private static final String SCHEMA =
            "io.github.patricklfdm.generalsearch.schema.SearchSchema";
    private static final String INDEX_DEFINITION =
            "io.github.patricklfdm.generalsearch.index.IndexDefinition";

    private final Set<String> generatedTypes = new HashSet<>();

    @Override
    public SourceVersion getSupportedSourceVersion() {
        return SourceVersion.RELEASE_21;
    }

    @Override
    public boolean process(
            Set<? extends TypeElement> annotations,
            RoundEnvironment roundEnvironment
    ) {
        if (roundEnvironment.processingOver()) {
            return false;
        }
        Map<String, TypeElement> documents = new LinkedHashMap<>();
        collectAnnotatedOwners(roundEnvironment, SEARCH_ID, documents);
        collectAnnotatedOwners(roundEnvironment, SEARCH_INDEX, documents);
        documents.values().stream()
                .sorted(Comparator.comparing(type -> type.getQualifiedName().toString()))
                .forEach(this::generate);
        return false;
    }

    private void collectAnnotatedOwners(
            RoundEnvironment roundEnvironment,
            String annotationName,
            Map<String, TypeElement> documents
    ) {
        TypeElement annotation = processingEnv.getElementUtils()
                .getTypeElement(annotationName);
        if (annotation == null) {
            return;
        }
        for (Element annotated : roundEnvironment.getElementsAnnotatedWith(annotation)) {
            TypeElement owner = owningType(annotated);
            if (owner != null) {
                documents.put(owner.getQualifiedName().toString(), owner);
            }
        }
    }

    private TypeElement owningType(Element element) {
        for (Element current = element;
             current != null;
             current = current.getEnclosingElement()) {
            if (current instanceof TypeElement type) {
                return type;
            }
        }
        return null;
    }

    private void generate(TypeElement document) {
        try {
            DocumentModel model = model(document);
            if (!generatedTypes.add(model.generatedQualifiedName())) {
                return;
            }
            JavaFileObject source = processingEnv.getFiler().createSourceFile(
                    model.generatedQualifiedName(),
                    document);
            try (Writer writer = source.openWriter()) {
                writer.write(source(model));
            }
        } catch (InvalidModel ignored) {
            // A stable diagnostic was already emitted at the offending element.
        } catch (FilerException collision) {
            error(document, "GSE009 generated type already exists: "
                    + generatedQualifiedName(document));
        } catch (IOException failure) {
            error(document, "GSE010 cannot write generated source: "
                    + failure.getMessage());
        }
    }

    private DocumentModel model(TypeElement document) {
        if (document.getKind() != ElementKind.RECORD
                && document.getKind() != ElementKind.CLASS) {
            reject(document, "GSE001 only records and classes are supported");
        }
        ensureAccessibleType(document);
        PackageElement packageElement = processingEnv.getElementUtils()
                .getPackageOf(document);
        if (packageElement.isUnnamed()) {
            reject(document, "GSE002 documents in the unnamed package are not supported");
        }

        List<MemberModel> members = document.getKind() == ElementKind.RECORD
                ? recordMembers(document)
                : classMembers(document);
        List<MemberModel> ids = members.stream().filter(MemberModel::id).toList();
        if (ids.size() != 1) {
            reject(document, "GSE003 exactly one @SearchId member is required; found "
                    + ids.size());
        }
        rejectNameCollisions(document, members);
        members.forEach(member -> validateIndex(document, member));

        String packageName = packageElement.getQualifiedName().toString();
        String generatedName = generatedSimpleName(document);
        return new DocumentModel(
                packageName,
                generatedName,
                packageName + "." + generatedName,
                document.getQualifiedName().toString(),
                List.copyOf(members),
                ids.getFirst());
    }

    private void ensureAccessibleType(TypeElement document) {
        for (Element current = document;
             current instanceof TypeElement type;
             current = current.getEnclosingElement()) {
            if (type.getModifiers().contains(Modifier.PRIVATE)) {
                reject(document, "GSE004 private document or enclosing types are not "
                        + "supported by generated companions");
            }
        }
    }

    private List<MemberModel> recordMembers(TypeElement document) {
        List<MemberModel> members = new ArrayList<>();
        for (RecordComponentElement component : document.getRecordComponents()) {
            members.add(member(
                    document,
                    component,
                    component.getSimpleName().toString(),
                    component.asType(),
                    document.getQualifiedName() + "::" + component.getSimpleName()));
        }
        return List.copyOf(members);
    }

    private List<MemberModel> classMembers(TypeElement document) {
        List<MemberModel> members = new ArrayList<>();
        for (Element element : document.getEnclosedElements()) {
            if (!hasAnnotation(element, SEARCH_ID)
                    && !hasAnnotation(element, SEARCH_INDEX)) {
                continue;
            }
            if (element.getModifiers().contains(Modifier.STATIC)) {
                reject(element, "GSE005 annotated members must not be static");
            }
            if (element.getModifiers().contains(Modifier.PRIVATE)) {
                reject(element, "GSE005 private annotated members require the runtime "
                        + "reflection factory");
            }
            if (element instanceof VariableElement field) {
                String name = field.getSimpleName().toString();
                members.add(member(
                        document,
                        field,
                        name,
                        field.asType(),
                        "document -> document." + name));
            } else if (element instanceof ExecutableElement method) {
                if (!method.getParameters().isEmpty()
                        || method.getReturnType().getKind() == TypeKind.VOID) {
                    reject(method, "GSE005 annotated methods must be zero-argument "
                            + "non-void getters");
                }
                String name = propertyName(method);
                members.add(member(
                        document,
                        method,
                        name,
                        method.getReturnType(),
                        document.getQualifiedName() + "::" + method.getSimpleName()));
            } else {
                reject(element, "GSE005 annotations are supported only on fields and "
                        + "getter methods for classes");
            }
        }
        members.sort(Comparator.comparing(MemberModel::logicalName));
        return List.copyOf(members);
    }

    private MemberModel member(
            TypeElement document,
            Element element,
            String logicalName,
            TypeMirror valueType,
            String extractor
    ) {
        String valueTypeName = sourceType(element, valueType);
        return new MemberModel(
                logicalName,
                constantName(logicalName),
                valueTypeName,
                valueTypeName + ".class",
                extractor,
                hasAnnotation(element, SEARCH_ID),
                indexType(element),
                valueType,
                element);
    }

    private String sourceType(Element element, TypeMirror type) {
        return switch (type.getKind()) {
            case BOOLEAN, BYTE, SHORT, INT, LONG, CHAR, FLOAT, DOUBLE ->
                    processingEnv.getTypeUtils()
                            .boxedClass((PrimitiveType) type)
                            .getQualifiedName()
                            .toString();
            case ARRAY -> arrayType(element, (ArrayType) type);
            case DECLARED -> declaredType(element, (DeclaredType) type);
            default -> {
                reject(element, "GSE006 unsupported generated field type: " + type);
                yield "";
            }
        };
    }

    private String arrayType(Element element, ArrayType array) {
        TypeMirror component = array.getComponentType();
        if (component.getKind() == TypeKind.TYPEVAR
                || component.getKind() == TypeKind.WILDCARD) {
            reject(element, "GSE006 generic array fields are not supported");
        }
        return component.getKind().isPrimitive()
                ? component + "[]"
                : sourceType(element, component) + "[]";
    }

    private String declaredType(Element element, DeclaredType declared) {
        if (!declared.getTypeArguments().isEmpty()) {
            reject(element, "GSE006 parameterized field types require the runtime "
                    + "reflection factory: " + declared);
        }
        TypeElement type = (TypeElement) declared.asElement();
        ensureAccessibleValueType(element, type);
        return type.getQualifiedName().toString();
    }

    private void ensureAccessibleValueType(Element member, TypeElement valueType) {
        for (Element current = valueType;
             current instanceof TypeElement type;
             current = current.getEnclosingElement()) {
            if (type.getModifiers().contains(Modifier.PRIVATE)) {
                reject(member, "GSE006 private field value types are not accessible to "
                        + "a generated companion: " + valueType.getQualifiedName());
            }
        }
    }

    private void rejectNameCollisions(
            TypeElement document,
            List<MemberModel> members
    ) {
        Set<String> logicalNames = new HashSet<>();
        Set<String> constantNames = new HashSet<>();
        for (MemberModel member : members) {
            if (!logicalNames.add(member.logicalName())) {
                reject(document, "GSE007 duplicate generated field name: "
                        + member.logicalName());
            }
            if (!constantNames.add(member.constantName())) {
                reject(document, "GSE008 generated constant-name collision: "
                        + member.constantName());
            }
        }
    }

    private void validateIndex(TypeElement document, MemberModel member) {
        if (member.indexType() == null) {
            return;
        }
        if ("PREFIX".equals(member.indexType())
                && !"java.lang.String".equals(member.valueTypeName())) {
            reject(member.element(), "GSE011 PREFIX index requires a String field: "
                    + member.logicalName());
        }
        if ("RANGE".equals(member.indexType())) {
            TypeElement comparable = processingEnv.getElementUtils()
                    .getTypeElement("java.lang.Comparable");
            if (comparable == null
                    || !processingEnv.getTypeUtils().isAssignable(
                            processingEnv.getTypeUtils().erasure(member.originalType()),
                            processingEnv.getTypeUtils().erasure(comparable.asType()))) {
                reject(member.element(), "GSE011 RANGE index requires a Comparable "
                        + "field: " + member.logicalName());
            }
        }
        if (!Set.of("EQUALITY", "RANGE", "PREFIX").contains(member.indexType())) {
            reject(document, "GSE011 unsupported index type: " + member.indexType());
        }
    }

    private String source(DocumentModel model) {
        StringBuilder source = new StringBuilder(4_096);
        source.append("package ").append(model.packageName()).append(";\n\n")
                .append('@').append(Generated.class.getCanonicalName())
                .append("(\"").append(getClass().getName()).append("\")\n")
                .append("public final class ").append(model.generatedSimpleName())
                .append(" {\n");
        for (MemberModel member : model.members()) {
            source.append("    public static final ").append(FIELD).append('<')
                    .append(model.documentType()).append(", ")
                    .append(member.valueTypeName()).append("> ")
                    .append(member.constantName()).append(" =\n")
                    .append("            ").append(FIELD).append(".of(\"")
                    .append(escape(member.logicalName())).append("\", ")
                    .append(member.classLiteral()).append(", ")
                    .append(member.extractor()).append(");\n");
        }
        source.append("\n    public static final ").append(SCHEMA).append('<')
                .append(model.documentType()).append(", ")
                .append(model.id().valueTypeName()).append("> SCHEMA = createSchema();\n")
                .append("\n    public static final java.util.List<")
                .append(INDEX_DEFINITION).append('<').append(model.documentType())
                .append(">> INDEX_DEFINITIONS = ");
        appendIndexes(source, model);
        source.append(";\n\n    private ").append(model.generatedSimpleName())
                .append("() {}\n\n")
                .append("    private static ").append(SCHEMA).append('<')
                .append(model.documentType()).append(", ")
                .append(model.id().valueTypeName()).append("> createSchema() {\n")
                .append("        ").append(SCHEMA).append(".Builder<")
                .append(model.documentType()).append(", ")
                .append(model.id().valueTypeName()).append("> builder = ")
                .append(SCHEMA).append(".builder(")
                .append(model.documentType()).append(".class, ")
                .append(model.id().constantName()).append(");\n");
        for (MemberModel member : model.members()) {
            if (!member.id()) {
                source.append("        builder.field(")
                        .append(member.constantName()).append(");\n");
            }
        }
        source.append("        return builder.build();\n")
                .append("    }\n")
                .append("}\n");
        return source.toString();
    }

    private void appendIndexes(StringBuilder source, DocumentModel model) {
        List<MemberModel> indexed = model.members().stream()
                .filter(member -> member.indexType() != null)
                .toList();
        if (indexed.isEmpty()) {
            source.append("java.util.List.of()");
            return;
        }
        source.append("java.util.List.of(\n");
        for (int index = 0; index < indexed.size(); index++) {
            MemberModel member = indexed.get(index);
            source.append("            ").append(INDEX_DEFINITION).append('.')
                    .append(member.indexType().toLowerCase(Locale.ROOT))
                    .append('(').append(member.constantName()).append(')');
            source.append(index + 1 == indexed.size() ? "\n" : ",\n");
        }
        source.append("    )");
    }

    private boolean hasAnnotation(Element element, String annotationName) {
        return element.getAnnotationMirrors().stream()
                .anyMatch(annotation -> annotation.getAnnotationType()
                        .toString().equals(annotationName));
    }

    private String indexType(Element element) {
        for (AnnotationMirror annotation : element.getAnnotationMirrors()) {
            if (!annotation.getAnnotationType().toString().equals(SEARCH_INDEX)) {
                continue;
            }
            for (Map.Entry<? extends ExecutableElement, ? extends AnnotationValue> entry
                    : processingEnv.getElementUtils()
                            .getElementValuesWithDefaults(annotation).entrySet()) {
                if (entry.getKey().getSimpleName().contentEquals("value")
                        && entry.getValue().getValue() instanceof VariableElement value) {
                    return value.getSimpleName().toString();
                }
            }
        }
        return null;
    }

    private String propertyName(ExecutableElement method) {
        String name = method.getSimpleName().toString();
        if (name.startsWith("get") && name.length() > 3) {
            return decapitalize(name.substring(3));
        }
        if (name.startsWith("is") && name.length() > 2
                && (method.getReturnType().getKind() == TypeKind.BOOLEAN
                || method.getReturnType().toString().equals("java.lang.Boolean"))) {
            return decapitalize(name.substring(2));
        }
        return name;
    }

    private String decapitalize(String value) {
        if (value.length() > 1
                && Character.isUpperCase(value.charAt(0))
                && Character.isUpperCase(value.charAt(1))) {
            return value;
        }
        return Character.toLowerCase(value.charAt(0)) + value.substring(1);
    }

    private String constantName(String logicalName) {
        StringBuilder constant = new StringBuilder(logicalName.length() + 4);
        for (int index = 0; index < logicalName.length(); index++) {
            char character = logicalName.charAt(index);
            if (!Character.isLetterOrDigit(character)) {
                if (constant.isEmpty() || constant.charAt(constant.length() - 1) != '_') {
                    constant.append('_');
                }
                continue;
            }
            if (Character.isUpperCase(character)
                    && !constant.isEmpty()
                    && constant.charAt(constant.length() - 1) != '_'
                    && Character.isLowerCase(logicalName.charAt(index - 1))) {
                constant.append('_');
            }
            constant.append(Character.toUpperCase(character));
        }
        return constant.toString();
    }

    private String generatedQualifiedName(TypeElement document) {
        String packageName = processingEnv.getElementUtils()
                .getPackageOf(document).getQualifiedName().toString();
        return packageName + "." + generatedSimpleName(document);
    }

    private String generatedSimpleName(TypeElement document) {
        List<String> nesting = new ArrayList<>();
        for (Element current = document;
             current instanceof TypeElement type;
             current = current.getEnclosingElement()) {
            nesting.add(type.getSimpleName().toString());
        }
        java.util.Collections.reverse(nesting);
        return String.join("_", nesting) + "SearchFields";
    }

    private String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private void reject(Element element, String message) {
        error(element, message);
        throw new InvalidModel();
    }

    private void error(Element element, String message) {
        processingEnv.getMessager().printMessage(
                Diagnostic.Kind.ERROR,
                message,
                element);
    }

    private record DocumentModel(
            String packageName,
            String generatedSimpleName,
            String generatedQualifiedName,
            String documentType,
            List<MemberModel> members,
            MemberModel id
    ) {}

    private record MemberModel(
            String logicalName,
            String constantName,
            String valueTypeName,
            String classLiteral,
            String extractor,
            boolean id,
            String indexType,
            TypeMirror originalType,
            Element element
    ) {}

    private static final class InvalidModel extends RuntimeException {}
}
