import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.trino.benchto.service.ServiceApp;

/**
 * Trigger for the jackson-core 2.15 StreamReadConstraints break against trinodb/benchto's
 * OWN production ObjectMapper.
 *
 * ServiceApp.configureObjectMapper() is the @Bean that defines the single
 * Jackson2ObjectMapperBuilder the whole Spring application serialises and deserialises
 * through, and it is exactly the method their fix changes -- the adaptation adds a
 * .postConfigurer(ServiceApp::disableReadWriteConstraints) to that builder. Calling the
 * bean method directly and building it applies that postConfigurer, so this runs their
 * real mapper without starting a Spring context. The method signature is identical at both
 * commits, so this same source compiles in every state.
 *
 * The field is 25,000,000 characters, above the 20,000,000 maxStringLength default that
 * jackson 2.15.1+ (and so their 2.17.2) applies. benchto stores benchmark run data as JSON,
 * so a large document is its ordinary workload.
 *
 *   state 1  parent code + jackson 2.14.2  -> PARSED  (last version before the boundary)
 *   state 1b parent code + jackson 2.15.0  -> THROWS  (boundary probe, see below)
 *   state 2  parent code + jackson 2.17.2  -> THROWS  (their resolved version at the fix)
 *   state 3  adapted code + jackson 2.17.2 -> PARSED  (their Integer.MAX_VALUE restoration)
 *
 * State 1b exists because their crossing jumped 2.13.3 -> 2.17.2 in one move, so their own
 * before/after pair is four minor versions apart. Running the IDENTICAL parent code at
 * 2.14.2 and then 2.15.0 narrows that to a single minor version and shows the failure
 * appears exactly AT the boundary, not somewhere in the 2.16/2.17 range.
 *
 * THE BASELINE IS 2.14.2, NOT THEIR ACTUAL PRE-CROSSING 2.13.3, and not by preference:
 * 2.13.3 cannot be run here at all. Spring Framework 6.1 (via Spring Boot 3.3.5, which
 * this code needs) calls com.fasterxml.jackson.databind.cfg.DatatypeFeature, a class
 * introduced in jackson 2.14, so Jackson2ObjectMapperBuilder.build() dies with
 * NoClassDefFoundError before any parsing happens. Their crossing was delivered BY the
 * framework upgrade, and below 2.14 the two cannot be separated.
 */
public class BenchtoBbcDriver {

    public static void main(String[] args) throws Exception {
        int size = 25_000_000;                  // > 20,000,000, the 2.15.1+ default
        StringBuilder sb = new StringBuilder(size + 32);
        sb.append("{\"content\":\"");
        for (int i = 0; i < size; i++) {
            sb.append('x');
        }
        sb.append("\"}");
        String json = sb.toString();

        ObjectMapper mapper = new ServiceApp().configureObjectMapper().build();

        System.out.println("[driver] jackson-core loaded from: "
                + locationOf("com.fasterxml.jackson.core.JsonFactory"));
        System.out.println("[driver] maxStringLength in force: " + maxStringLength(mapper));
        System.out.println("[driver] string field length: " + size);

        try {
            JsonNode node = mapper.readTree(json);
            System.out.println("RESULT=PARSED len=" + node.get("content").asText().length());
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

    /**
     * The cap this run is actually operating under, read off their own mapper.
     *
     * Reflection is REQUIRED rather than stylistic: StreamReadConstraints does not exist
     * before 2.15, so naming the type would make the driver uncompilable against the
     * baseline. "n/a (pre-2.15)" is itself the baseline's signature.
     */
    private static String maxStringLength(ObjectMapper mapper) {
        try {
            Class.forName("com.fasterxml.jackson.core.StreamReadConstraints");
        } catch (Throwable t) {
            return "n/a (pre-2.15: StreamReadConstraints does not exist)";
        }
        try {
            Object factory = mapper.getFactory();
            Object src = factory.getClass().getMethod("streamReadConstraints").invoke(factory);
            return String.valueOf(src.getClass().getMethod("getMaxStringLength").invoke(src));
        } catch (Throwable t) {
            return "unreadable (" + t.getClass().getSimpleName() + ")";
        }
    }
}
