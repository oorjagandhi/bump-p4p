import io.json.compare.util.JsonUtils;

/**
 * Trigger for the jackson-core 2.15.0 StreamReadConstraints break against
 * fslev/json-compare's OWN production path.
 *
 * Nothing here is a reconstruction of their fix. It calls JsonUtils.toJson(String), the
 * public static entry point their library uses to parse every document, on a JSON string
 * whose single field exceeds jackson 2.15.0's default 5,000,000-character cap. That method
 * and the ObjectMapper behind it are theirs; the oversized document and this main() are the
 * only things supplied from outside.
 *
 * Their own suite cannot serve as the differential: JSONLargeCompareTests passes in every
 * state because its "large" fixture sits well under the cap. No project ships a 6 MB string
 * fixture, which is exactly why this break needs an authored trigger.
 *
 *   state 1  parent code + jackson 2.14.2   -> PARSED   (no constraints exist yet)
 *   state 2  parent code + jackson 2.15.0   -> THROWS   StreamConstraintsException
 *   state 3  adapted code + jackson 2.15.0  -> PARSED   (their Integer.MAX_VALUE raise)
 */
public class JsonCompareBbcDriver {

    public static void main(String[] args) {
        int size = 6_000_000;                       // > the 5,000,000 default of 2.15.0
        StringBuilder sb = new StringBuilder(size + 32);
        sb.append("{\"k\":\"");
        for (int i = 0; i < size; i++) {
            sb.append('x');
        }
        sb.append("\"}");
        String json = sb.toString();

        System.out.println("[driver] jackson-core on classpath: "
                + versionOf("com.fasterxml.jackson.core.JsonFactory"));
        System.out.println("[driver] string field length: " + size);

        try {
            Object node = JsonUtils.toJson(json);
            System.out.println("RESULT=PARSED len=" + node.toString().length());
        } catch (Throwable t) {
            System.out.println("RESULT=THREW " + t.getClass().getName() + ": "
                    + String.valueOf(t.getMessage()).split("\n")[0]);
        }
    }

    /** Where the jackson class was actually loaded from, so a state cannot silently lie. */
    private static String versionOf(String className) {
        try {
            Class<?> c = Class.forName(className);
            return String.valueOf(c.getProtectionDomain().getCodeSource().getLocation());
        } catch (Throwable t) {
            return "unknown (" + t + ")";
        }
    }
}
