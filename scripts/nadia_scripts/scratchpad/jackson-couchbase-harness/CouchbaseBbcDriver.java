import java.util.Map;

import com.couchbase.client.core.json.Mapper;

/**
 * Trigger for the jackson-core 2.15 StreamReadConstraints break against
 * couchbase/couchbase-jvm-clients' OWN production JSON entry point.
 *
 * Mapper.decodeInto(String, Class) is the static decode path core-io parses through, and
 * Mapper's private static `mapper` field is exactly the object their fix reconfigures --
 * the adaptation replaces `new ObjectMapper()` with `newObjectMapper()`, which sets
 * maxStringLength. Nothing of theirs is reconstructed here: this calls their Mapper. The
 * oversized document and this main() are the only outside additions.
 *
 * SIZING IS LOAD-BEARING, and this case differs from the other two for this break.
 * json-compare and datashare both set an effectively unlimited cap, so any oversized
 * document separated their states. Couchbase raised the cap to a FINITE 20 MiB
 * (20,971,520), so the trigger has to land in the window between jackson 2.15.0's new
 * default (5,000,000) and their chosen ceiling:
 *
 *     5,000,000  <  10,000,000  <  20,971,520
 *
 * A document above 20 MiB would throw in the adapted state too, and would prove nothing.
 *
 *   state 1  parent code + jackson 2.14.2  -> PARSED  (no constraints exist before 2.15)
 *   state 2  parent code + jackson 2.15.0  -> THROWS  (5 MB default)
 *   state 3  adapted code + jackson 2.15.0 -> PARSED  (their 20 MiB raise)
 *
 * State 2 is COUNTERFACTUAL: couchbase bumped jackson and adapted in the same commit, so
 * "their code on 2.15.0 without the fix" never existed in their history. It is what would
 * have shipped had they not read the release notes.
 *
 * Jackson is SHADED into com.couchbase.client.core.deps.*, so this driver deliberately
 * imports none of it -- the only couchbase type named here is Mapper, and the decode
 * target is java.util.Map. The jar-location and cap diagnostics go through reflection so
 * that the driver text is identical in all three states.
 */
public class CouchbaseBbcDriver {

    public static void main(String[] args) throws Exception {
        int size = 10_000_000;                  // > 5,000,000 (2.15.0 default), < 20,971,520 (their cap)
        StringBuilder sb = new StringBuilder(size + 32);
        sb.append("{\"content\":\"");
        for (int i = 0; i < size; i++) {
            sb.append('x');
        }
        sb.append("\"}");
        String json = sb.toString();

        System.out.println("[driver] shaded jackson-core loaded from: " + jacksonLocation());
        System.out.println("[driver] maxStringLength in force: " + maxStringLength());
        System.out.println("[driver] string field length: " + size);

        try {
            Map<?, ?> decoded = Mapper.decodeInto(json, Map.class);
            Object content = decoded.get("content");
            System.out.println("RESULT=PARSED len=" + String.valueOf(content).length());
        } catch (Throwable t) {
            System.out.println("RESULT=THREW " + describe(t));
        }
    }

    /**
     * Their Mapper wraps every failure in MapperException, so the real cause is one level down.
     *
     * Messages are TRUNCATED because MapperException embeds the entire input document it
     * failed on (via redactUser). Printing it whole turns a one-line result into a 9.5 MB
     * log, since the input here is 10,000,000 characters by construction.
     */
    private static String describe(Throwable t) {
        StringBuilder sb = new StringBuilder();
        for (Throwable c = t; c != null; c = c.getCause()) {
            if (sb.length() > 0) {
                sb.append("  <- caused by: ");
            }
            sb.append(c.getClass().getName()).append(": ").append(clip(c.getMessage()));
            if (c.getCause() == c) {
                break;
            }
        }
        return sb.toString();
    }

    private static String clip(String s) {
        String line = String.valueOf(s).split("\n")[0];
        return line.length() <= 160 ? line : line.substring(0, 160) + "...[" + line.length() + " chars]";
    }

    /** Where the shaded jackson actually came from, so a state cannot silently run the wrong version. */
    private static String jacksonLocation() {
        try {
            Class<?> c = Class.forName(
                "com.couchbase.client.core.deps.com.fasterxml.jackson.core.JsonFactory");
            return String.valueOf(c.getProtectionDomain().getCodeSource().getLocation());
        } catch (Throwable t) {
            return "unknown (" + t + ")";
        }
    }

    /**
     * The cap the run is actually operating under, read off their own mapper by reflection.
     * Prints "n/a (pre-2.15)" when the class does not exist, which is itself the baseline's
     * signature: StreamReadConstraints was introduced BY 2.15.0.
     */
    private static String maxStringLength() {
        try {
            Class.forName("com.couchbase.client.core.deps.com.fasterxml.jackson.core.StreamReadConstraints");
        } catch (Throwable t) {
            return "n/a (pre-2.15: StreamReadConstraints does not exist)";
        }
        try {
            java.lang.reflect.Field f = Mapper.class.getDeclaredField("mapper");
            f.setAccessible(true);
            Object om = f.get(null);
            Object factory = om.getClass().getMethod("getFactory").invoke(om);
            Object src = factory.getClass().getMethod("streamReadConstraints").invoke(factory);
            Object max = src.getClass().getMethod("getMaxStringLength").invoke(src);
            return String.valueOf(max);
        } catch (Throwable t) {
            return "unreadable (" + t.getClass().getSimpleName() + ")";
        }
    }
}
