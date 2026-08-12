import com.fasterxml.jackson.core.StreamReadConstraints;

import org.glassfish.jersey.internal.util.PropertiesHelper;

/**
 * Isolated probe for the jersey exclusion: does the adaptation do ANYTHING when the user
 * has not set the new property?
 *
 * DefaultJacksonJaxbJsonProvider.updateFactoryConstraints (added in "Adopt Jackson 2.15",
 * e79aa535) reads the property and guards the whole fix behind one comparison:
 *
 *     final Object  maxStringLengthObject = commonConfig.getProperty(JSON_MAX_STRING_LENGTH);
 *     final Integer maxStringLength = PropertiesHelper.convertValue(maxStringLengthObject, Integer.class);
 *     if (maxStringLength != StreamReadConstraints.DEFAULT_MAX_STRING_LEN) { ...set constraints... }
 *
 * With the property unset, commonConfig.getProperty returns null. This runs the two steps
 * that follow against jersey's OWN published jersey-common 2.41 and jackson-core 2.15.0,
 * to establish what the guard does with that null -- rather than reasoning about it.
 */
public class JerseyGuardProbe {

    public static void main(String[] args) {
        System.out.println("[probe] jersey-common from : " + locationOf("org.glassfish.jersey.internal.util.PropertiesHelper"));
        System.out.println("[probe] jackson-core from  : " + locationOf("com.fasterxml.jackson.core.StreamReadConstraints"));
        System.out.println("[probe] DEFAULT_MAX_STRING_LEN = " + StreamReadConstraints.DEFAULT_MAX_STRING_LEN);
        System.out.println();

        // Step 1: the property is not set, so getProperty(...) returns null.
        Integer converted = null;
        System.out.print("[step 1] PropertiesHelper.convertValue(null, Integer.class) -> ");
        try {
            converted = PropertiesHelper.convertValue(null, Integer.class);
            System.out.println("returned " + converted);
        } catch (Throwable t) {
            System.out.println("THREW " + t.getClass().getName() + ": " + t.getMessage());
        }

        // Step 2: the guard itself, exactly as written -- Integer vs int, so the Integer
        // is unboxed. Whether step 1 threw or returned null, the fix cannot run.
        System.out.print("[step 2] if (maxStringLength != DEFAULT_MAX_STRING_LEN) -> ");
        try {
            if (converted != StreamReadConstraints.DEFAULT_MAX_STRING_LEN) {
                System.out.println("GUARD PASSED: constraints would be set");
            } else {
                System.out.println("guard false: constraints left at jackson's defaults");
            }
        } catch (Throwable t) {
            System.out.println("THREW " + t.getClass().getName()
                    + " (unboxing a null Integer) -> constraints left at jackson's defaults");
        }

        // Control: with the property actually set, the same two steps do reach the fix.
        System.out.println();
        Integer set = PropertiesHelper.convertValue("2147483647", Integer.class);
        System.out.println("[control] convertValue(\"2147483647\") = " + set
                + "; guard passes = " + (set != StreamReadConstraints.DEFAULT_MAX_STRING_LEN));
    }

    private static String locationOf(String className) {
        try {
            Class<?> c = Class.forName(className);
            return String.valueOf(c.getProtectionDomain().getCodeSource().getLocation());
        } catch (Throwable t) {
            return "unknown (" + t + ")";
        }
    }
}
