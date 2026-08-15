package bbc;

import junit.framework.TestCase;

import com.thoughtworks.xstream.XStream;

import org.collectionspace.services.id.IDGeneratorSerializer;
import org.collectionspace.services.id.SettableIDGenerator;
import org.collectionspace.services.id.StringIDGeneratorPart;
import org.collectionspace.services.id.YearIDGeneratorPart;

/**
 * BBC driver for collectionspace/services @ 6593d7fb ("Bump xstream from 1.4.10 to 1.4.19
 * in /services/id/service").
 *
 * Shape A: IDGeneratorSerializer.serialize/deserialize both exist at the parent commit; the
 * adaptation only added two allowTypeHierarchy() calls INSIDE deserialize(). So the same
 * driver compiles and runs at both commits, and uses only API present in xstream 1.4.10 and
 * 1.4.18 (in fact it needs no xstream API at all beyond reading the jar's version for the
 * log -- the whitelist calls live in production code, where the client put them).
 *
 * JUnit 3 style (extends junit.framework.TestCase) deliberately: services/pom.xml puts
 * testng 6.1.1 on every services module's test classpath, so surefire selects the TestNG
 * provider, and that provider silently executes zero JUnit-4-annotated tests. Every test in
 * this module (IDGeneratorSerializerTest, BaseIDGeneratorTest, ...) extends TestCase, so the
 * driver does too. The method is therefore named testBbcCase() rather than bbcCase(): JUnit 3
 * discovery only picks up methods whose name starts with "test".
 */
public class BbcTest extends TestCase {

    public void testBbcCase() throws Exception {
        System.out.println("[bbc] xstream jar version = "
                + XStream.class.getPackage().getImplementationVersion());

        // A generator the ID service really produces: a literal prefix plus a year part.
        SettableIDGenerator generator = new SettableIDGenerator();
        generator.add(new StringIDGeneratorPart("BBC-"));
        generator.add(new YearIDGeneratorPart("2023"));
        assertEquals("BBC-2023", generator.getCurrentID());

        // Marshalling is unaffected by the security framework; this is the client's own
        // production writer, and it is how a generator gets into the database.
        String xml = IDGeneratorSerializer.serialize(generator);
        System.out.println("[bbc] serialized:\n" + xml);
        assertTrue(xml.contains("org.collectionspace.services.id.SettableIDGenerator"));

        // The read path is the one that breaks at 1.4.18.
        SettableIDGenerator roundTripped;
        try {
            roundTripped = IDGeneratorSerializer.deserialize(xml);
        } catch (Exception e) {
            StringBuilder chain = new StringBuilder();
            for (Throwable t = e; t != null; t = t.getCause()) {
                chain.append(t.getClass().getName()).append(": ").append(t.getMessage())
                     .append(" || ");
            }
            System.out.println("[bbc] IDGeneratorSerializer.deserialize threw: " + chain);
            throw e;
        }

        // The pre-break outcome: the generator survives the round trip intact.
        assertNotNull(roundTripped);
        assertEquals("BBC-2023", roundTripped.getCurrentID());
        assertEquals(xml, IDGeneratorSerializer.serialize(roundTripped));
    }
}
