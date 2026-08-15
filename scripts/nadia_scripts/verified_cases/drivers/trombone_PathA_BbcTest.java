package bbc;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.io.File;

import org.junit.Test;
import org.voyanttools.trombone.util.FlexibleParameters;

/**
 * Reproduces the XStream 1.4.17 -> 1.4.19 behavioural break through Trombone's
 * own production (de)serialization path.
 *
 * Shape A: FlexibleParameters.loadFlexibleParameters(File) already existed at the
 * parent commit; the fix only hardened its body by whitelisting types. The same
 * test compiles and runs at both parent (unhardened) and adapted (hardened) code.
 *
 * Differential:
 *   parent code  + xstream 1.4.17  -> PASS  (no default security framework)
 *   parent code  + xstream 1.4.19  -> FAIL  (ForbiddenClassException / NoTypePermission)
 *   adapted code + xstream 1.4.19  -> PASS  (production code adds the whitelist)
 */
public class BbcTest {

    @Test
    public void bbcCase() throws Exception {
        // Build a deterministic fixture using only API common to both library versions.
        FlexibleParameters params = new FlexibleParameters();
        params.setParameter("greeting", "hello");
        params.setParameter("count", "42");

        File file = File.createTempFile("bbc-flexparams", ".xml");
        file.deleteOnExit();

        // Serialize via the client's real production method (marshalling is not gated).
        params.saveFlexibleParameters(file);

        // Deserialize via the client's real production method. On xstream >= 1.4.18
        // the default security framework forbids the custom types unless the
        // production code (adapted state) has whitelisted them.
        FlexibleParameters loaded = FlexibleParameters.loadFlexibleParameters(file);

        // Assert the pre-break outcome: the object loads and the values survive.
        assertNotNull(loaded);
        assertEquals("hello", loaded.getParameterValue("greeting"));
        assertEquals("42", loaded.getParameterValue("count"));
    }
}
