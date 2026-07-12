package mimic;

/**
 * Root object. {@code holder} is declared {@code Object}, so under default typing
 * Jackson writes/reads a type id for its concrete value ({@link Balance}) — which
 * is exactly what the PolymorphicTypeValidator gates on deserialization.
 */
public class Account {
    public String owner;
    public Object holder;

    public Account() {}

    public Account(String owner, Object holder) {
        this.owner = owner;
        this.holder = holder;
    }
}
