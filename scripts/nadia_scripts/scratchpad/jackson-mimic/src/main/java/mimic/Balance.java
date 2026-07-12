package mimic;

/** An app domain type carried polymorphically inside {@link Account#holder}. */
public class Balance {
    public String currency;
    public int amount;

    public Balance() {}

    public Balance(String currency, int amount) {
        this.currency = currency;
        this.amount = amount;
    }
}
