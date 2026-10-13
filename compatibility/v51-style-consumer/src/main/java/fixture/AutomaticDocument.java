package fixture;

/** Application-owned immutable document, independent of engine test fixtures. */
public record AutomaticDocument(int id, String body) { }
