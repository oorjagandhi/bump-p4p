package org.collectionspace.services.id.test;

import junit.framework.TestCase;

import org.collectionspace.services.id.IDGeneratorSerializer;
import org.collectionspace.services.id.NumericIDGeneratorPart;
import org.collectionspace.services.id.SettableIDGenerator;
import org.collectionspace.services.id.StringIDGeneratorPart;

/**
 * BBC differential driver for xstream 1.4.10 -> 1.4.19.
 *
 * Drives the production round trip the adaptation commit (6593d7fb) touched:
 * IDGeneratorSerializer.serialize(SettableIDGenerator) / .deserialize(String), each of
 * which builds `new XStream(new DomDriver())` internally.
 *
 * This source is used UNCHANGED in all three states, so the differential measures the
 * library swap and the production fix and nothing else:
 *
 *   1_baseline          parent code + 1.4.10   expect PASS
 *   2_new_lib_old_code  parent code + 1.4.19   expect FAIL
 *   3_adapted           6593d7fb    + 1.4.19   expect PASS
 *
 * The repo's own IDGeneratorSerializerTest does NOT cover a successful round trip --
 * its testDeserializeIDGenerator body is commented out, and its other deserialize tests
 * pass null or deliberately invalid XML, which throw for unrelated reasons and are
 * expected to. Hence this driver.
 *
 * Note on the expected failure: deserialize() catches XStreamException and rethrows it
 * wrapped in BadRequestException, so under 1.4.19 the ForbiddenClassException appears as
 * the CAUSE rather than as the thrown type. The assertion below therefore walks the
 * cause chain rather than matching on the top-level exception.
 */
public class BbcDifferentialTest extends TestCase {

    public void testIdGeneratorRoundTripsThroughXStream() throws Exception {
        SettableIDGenerator generator = new SettableIDGenerator();
        generator.add(new StringIDGeneratorPart("E"));
        generator.add(new NumericIDGeneratorPart("1"));

        String xml = IDGeneratorSerializer.serialize(generator);
        assertNotNull("serialize produced nothing", xml);

        // The break is on DESERIALIZATION -- serialize always succeeds, so deserialize
        // is the discriminating operation.
        SettableIDGenerator back = IDGeneratorSerializer.deserialize(xml);

        assertNotNull("deserialize returned null", back);
        assertEquals("round trip did not preserve the generated ID",
                generator.getCurrentID("E1"), back.getCurrentID("E1"));
    }
}
