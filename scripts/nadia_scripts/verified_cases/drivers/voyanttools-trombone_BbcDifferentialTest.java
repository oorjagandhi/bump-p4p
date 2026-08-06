package org.voyanttools.trombone.util;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.io.File;

import org.junit.Test;

/**
 * BBC differential driver for xstream 1.4.16 -> 1.4.18.
 *
 * Drives the production round trip the adaptation commit (c84fc06c) touched:
 * FlexibleParameters.saveFlexibleParameters(File) / .loadFlexibleParameters(File).
 * Before the adaptation both built a bare `new XStream()`; the adaptation routes both
 * through a new private secureXStream(...) helper that installs an explicit allowlist.
 *
 * This source is used UNCHANGED in all three states, so the differential measures the
 * library swap and the production fix and nothing else:
 *
 *   1_baseline          parent code + 1.4.16   expect PASS
 *   2_new_lib_old_code  parent code + 1.4.18   expect FAIL (ForbiddenClassException)
 *   3_adapted           c84fc06c    + 1.4.18   expect PASS
 *
 * Note: the parent commit ALREADY declares xstream 1.4.18 -- the bump landed one commit
 * earlier and this commit is the post-merge fix. State 1 therefore requires an explicit
 * downgrade to 1.4.16 to establish the pre-boundary baseline.
 */
public class BbcDifferentialTest {

    @Test
    public void flexibleParametersRoundTripThroughXStream() throws Exception {
        FlexibleParameters params = new FlexibleParameters();
        params.setParameter("bbc-key", "bbc-value");

        File f = File.createTempFile("bbc-flexible-params", ".xml");
        f.deleteOnExit();

        // Serialization is not the break -- saving always succeeds.
        params.saveFlexibleParameters(f);

        // Loading is the discriminating operation: it deserializes FlexibleParameters
        // through XStream, which 1.4.18 denies by default.
        FlexibleParameters back = FlexibleParameters.loadFlexibleParameters(f);

        assertNotNull("loadFlexibleParameters returned null", back);
        assertEquals("value did not survive the round trip",
                "bbc-value", back.getParameterValue("bbc-key"));
    }
}
