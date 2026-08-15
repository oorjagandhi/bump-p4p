package bbc;

import java.io.StringReader;

import org.junit.Test;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertEquals;

import com.marklogic.contentpump.DocumentMetadata;
import com.thoughtworks.xstream.XStream;

public class BbcTest {

    @Test
    public void bbcCase() {
        // Build a deterministic DocumentMetadata fixture and serialize it to XML
        // using only API common to xstream 1.4.17 and 1.4.19.
        DocumentMetadata md = new DocumentMetadata();
        md.addCollection("collectionA");
        String xml = new XStream().toXML(md);

        // Drive the client's REAL production deserialization path.
        // On 1.4.19 the default security framework forbids DocumentMetadata unless
        // the production code has whitelisted it (the adaptation).
        DocumentMetadata result = DocumentMetadata.fromXML(new StringReader(xml));

        assertNotNull(result);
        assertEquals("collectionA", result.getCollections()[0]);
    }
}
