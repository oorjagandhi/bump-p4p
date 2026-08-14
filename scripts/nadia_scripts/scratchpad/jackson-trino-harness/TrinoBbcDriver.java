import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import io.trino.plugin.prometheus.PrometheusQueryResponseParse;

/**
 * Trigger for the jackson-core 2.15 StreamReadConstraints break against trinodb/trino's
 * OWN Prometheus response parser.
 *
 * WHY THIS CLASS AND NOT JsonUtils, WHICH IS THE FILE THE CODE SEARCH HIT.
 * The adaptation ADDS the helpers JsonUtils.jsonFactory()/jsonFactoryBuilder(), which build
 * a JsonFactory with the limits disabled -- but JsonUtils' own parseJson() path was never
 * broken. parseJson uses OBJECT_MAPPER, built from airlift's ObjectMapperProvider, and
 * trino's commit message says why that is safe: "Airlift is already disabling those limits
 * when ObjectMapperProvider is used." The break bites at the call sites that construct a
 * JsonFactory DIRECTLY, and the same commit migrates six of them onto the new helper.
 *
 * PrometheusQueryResponseParse is one of those six, and the cleanest to drive: a single
 * public constructor taking an InputStream, parsing immediately. The diff at this site is
 * exactly one line --
 *
 *     parent   JsonParser parser = new JsonFactory().createParser(response);
 *     adapted  JsonParser parser = jsonFactory().createParser(response);
 *
 * -- so the differential isolates the adaptation to a single expression.
 *
 * THE PAYLOAD IS A REALISTIC PROMETHEUS RESPONSE. PrometheusMetricResult binds `metric` to
 * a Map<String,String> of label names to label values, so an oversized LABEL VALUE is both
 * valid input and the natural place for a large string to appear -- Prometheus labels
 * routinely carry URLs, queries and error text. The value here is 10,000,000 characters,
 * above jackson 2.15.0's 5,000,000 default. The document is otherwise well-formed, so
 * states 1 and 3 parse it to completion rather than merely avoiding the throw.
 *
 *   state 1  parent code + jackson 2.14.2  -> PARSED (no constraints exist before 2.15)
 *   state 2  parent code + jackson 2.15.0  -> THROWS StreamConstraintsException
 *   state 3  adapted code + jackson 2.15.0 -> PARSED (their Integer.MAX_VALUE restoration)
 */
public class TrinoBbcDriver {

    public static void main(String[] args) throws Exception {
        int size = 10_000_000;                  // > 5,000,000, the 2.15.0 default

        StringBuilder label = new StringBuilder(size);
        for (int i = 0; i < size; i++) {
            label.append('x');
        }

        String json = "{\"status\":\"success\",\"data\":{\"resultType\":\"matrix\",\"result\":["
                + "{\"metric\":{\"__name__\":\"up\",\"instance\":\"" + label + "\"},"
                + "\"values\":[[1435781430.781,\"1\"]]}]}}";

        InputStream in = new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8));

        System.out.println("[driver] jackson-core loaded from: "
                + locationOf("com.fasterxml.jackson.core.JsonFactory"));
        System.out.println("[driver] maxStringLength in force: " + maxStringLength());
        System.out.println("[driver] label value length: " + size);

        try {
            PrometheusQueryResponseParse parsed = new PrometheusQueryResponseParse(in);
            int got = parsed.getResults().get(0).getMetricHeader().get("instance").length();
            System.out.println("RESULT=PARSED results=" + parsed.getResults().size()
                    + " labelLen=" + got);
        } catch (Throwable t) {
            System.out.println("RESULT=THREW " + describe(t));
        }
    }

    /** trino wraps parse failures, so the jackson cause can sit a level or two down. */
    private static String describe(Throwable t) {
        StringBuilder sb = new StringBuilder();
        for (Throwable c = t; c != null && sb.length() < 600; c = c.getCause()) {
            if (sb.length() > 0) {
                sb.append("  <- caused by: ");
            }
            String line = String.valueOf(c.getMessage()).split("\n")[0];
            if (line.length() > 200) {
                line = line.substring(0, 200) + "...[" + line.length() + " chars]";
            }
            sb.append(c.getClass().getName()).append(": ").append(line);
            if (c.getCause() == c) {
                break;
            }
        }
        return sb.toString();
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

    /**
     * The cap a bare `new JsonFactory()` carries in this state -- which is what the parent
     * code builds. Reflection is required rather than stylistic: StreamReadConstraints does
     * not exist before 2.15, so naming the type would make this driver uncompilable against
     * the baseline. "n/a (pre-2.15)" is itself the baseline's signature.
     */
    private static String maxStringLength() {
        try {
            Class.forName("com.fasterxml.jackson.core.StreamReadConstraints");
        } catch (Throwable t) {
            return "n/a (pre-2.15: StreamReadConstraints does not exist)";
        }
        try {
            Object factory = Class.forName("com.fasterxml.jackson.core.JsonFactory")
                    .getDeclaredConstructor().newInstance();
            Object src = factory.getClass().getMethod("streamReadConstraints").invoke(factory);
            return String.valueOf(src.getClass().getMethod("getMaxStringLength").invoke(src))
                    + " (default JsonFactory, as the parent code builds)";
        } catch (Throwable t) {
            return "unreadable (" + t.getClass().getSimpleName() + ")";
        }
    }
}
