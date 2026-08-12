import org.icij.datashare.json.JsonObjectMapper;

/**
 * Trigger for the jackson-core 2.15 StreamReadConstraints break against ICIJ/datashare's
 * OWN production mapper.
 *
 * JsonObjectMapper.MAPPER is the public static ObjectMapper the whole application parses
 * through, and it is exactly the object their fix configures -- the adaptation lives in
 * that class's static initializer. Nothing of theirs is reconstructed here: this calls
 * their mapper. The oversized document and this main() are the only outside additions.
 *
 * The field is 25,000,000 characters, above 2.15.1's default maxStringLength of
 * 20,000,000. datashare indexes documents, so a text field past that cap is their ordinary
 * workload rather than a contrived input -- which is presumably why they raised the limit
 * to 1,000,000,000 rather than nudging it.
 *
 *   state 1  parent code + jackson 2.12.2  -> PARSED  (no constraints exist before 2.15)
 *   state 2  parent code + jackson 2.15.1  -> THROWS  StreamConstraintsException
 *   state 3  adapted code + jackson 2.15.1 -> PARSED  (their 1e9 raise)
 */
public class DatashareBbcDriver {

    public static void main(String[] args) throws Exception {
        int size = 25_000_000;                      // > the 20,000,000 default of 2.15.1
        StringBuilder sb = new StringBuilder(size + 32);
        sb.append("{\"content\":\"");
        for (int i = 0; i < size; i++) {
            sb.append('x');
        }
        sb.append("\"}");
        String json = sb.toString();

        System.out.println("[driver] jackson-core loaded from: "
                + locationOf("com.fasterxml.jackson.core.JsonFactory"));
        System.out.println("[driver] string field length: " + size);

        try {
            Object node = JsonObjectMapper.MAPPER.readTree(json);
            System.out.println("RESULT=PARSED len=" + node.toString().length());
        } catch (Throwable t) {
            System.out.println("RESULT=THREW " + t.getClass().getName() + ": "
                    + String.valueOf(t.getMessage()).split("\n")[0]);
        }
    }

    /** Where jackson actually came from, so a state cannot silently run the wrong version. */
    private static String locationOf(String className) {
        try {
            Class<?> c = Class.forName(className);
            return String.valueOf(c.getProtectionDomain().getCodeSource().getLocation());
        } catch (Throwable t) {
            return "unknown (" + t + ")";
        }
    }
}
