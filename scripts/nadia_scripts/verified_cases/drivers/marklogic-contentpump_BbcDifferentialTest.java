package com.marklogic.contentpump;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.io.StringReader;

import org.junit.Test;

import com.marklogic.xcc.ContentCapability;
import com.marklogic.xcc.ContentPermission;

/**
 * BBC differential driver for xstream 1.4.16 -> 1.4.18.
 *
 * Drives the exact production path the adaptation commit (3736c971) touched:
 * DocumentMetadata.toXML() / DocumentMetadata.fromXML(Reader), both of which use the
 * class's own `static XStream xstream = new XStream()` field.
 *
 * This one source file is used UNCHANGED in all three states, so the differential
 * measures the library swap and the production fix and nothing else:
 *
 *   1_baseline          parent code + 1.4.16   expect PASS
 *   2_new_lib_old_code  parent code + 1.4.18   expect FAIL (ForbiddenClassException)
 *   3_adapted           3736c971    + 1.4.18   expect PASS
 *
 * The adaptation adds, inside fromXML:
 *     xstream.allowTypes(new Class[] {DocumentMetadata.class});
 *     xstream.allowTypes(new Class[] {ContentPermission.class});
 * so the round trip below deliberately carries a ContentPermission as well as the
 * DocumentMetadata itself -- exercising BOTH allowTypes calls rather than only the first.
 */
public class BbcDifferentialTest {

    @Test
    public void documentMetadataRoundTripsThroughXStream() {
        DocumentMetadata meta = new DocumentMetadata();
        meta.setQuality(7);
        meta.addPermission(new ContentPermission(ContentCapability.READ, "bbc-role"));

        String xml = meta.toXML();
        assertNotNull("toXML produced nothing", xml);

        // The break is on DESERIALIZATION -- toXML always succeeds, so fromXML is the
        // discriminating operation.
        DocumentMetadata back = DocumentMetadata.fromXML(new StringReader(xml));

        assertNotNull("fromXML returned null", back);
        assertEquals("quality did not survive the round trip", 7, back.getQuality());
    }
}
