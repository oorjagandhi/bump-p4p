package bbc;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.io.Reader;
import java.io.StringReader;

import org.junit.Test;

import com.marklogic.contentpump.DocumentMetadata;

/**
 * Shape A: the production entry point DocumentMetadata.fromXML(Reader) existed
 * at the parent commit; the adaptation diff only added xstream.allowTypes(...)
 * inside its body. The SAME test compiles and runs at both parent and adapted
 * code, using only API common to xstream 1.4.17 and 1.4.19.
 *
 * Differential:
 *   parent  + 1.4.17 -> PASS (default security permissive)
 *   parent  + 1.4.19 -> FAIL (ForbiddenClassException / no security framework)
 *   adapted + 1.4.19 -> PASS (allowTypes whitelists DocumentMetadata)
 */
public class BbcTest {

    @Test
    public void bbcCase() {
        // XStream-style XML for the client's own domain type.
        // Fields left unspecified keep their Java defaults; quality is set so
        // we can assert the pre-break outcome (the object that survives).
        String xml =
                "<com.marklogic.contentpump.DocumentMetadata>"
              + "  <quality>7</quality>"
              + "</com.marklogic.contentpump.DocumentMetadata>";

        Reader reader = new StringReader(xml);

        // Drive the client's REAL production path.
        DocumentMetadata md = DocumentMetadata.fromXML(reader);

        assertNotNull(md);
        assertEquals(7, md.getQuality());
    }
}
