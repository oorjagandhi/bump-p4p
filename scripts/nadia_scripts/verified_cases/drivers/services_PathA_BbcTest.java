package bbc;

import static org.junit.Assert.assertNotNull;

import org.collectionspace.services.id.IDGeneratorSerializer;
import org.collectionspace.services.id.SettableIDGenerator;
import org.junit.Test;

/**
 * Shape A: the production method IDGeneratorSerializer.deserialize(...) already
 * existed at the parent commit; the adaptation only added allowTypeHierarchy(...)
 * calls inside its body.
 *
 * Differential:
 *   parent code + xstream 1.4.17  -> PASS  (default blacklist permits the type)
 *   parent code + xstream 1.4.19  -> FAIL  (default whitelist rejects the type;
 *                                           BadRequestException caused by
 *                                           ForbiddenClassException  == SIGNAL)
 *   adapted code + xstream 1.4.19 -> PASS  (allowTypeHierarchy whitelists it)
 */
public class BbcTest {

  @Test
  public void bbcCase() throws Exception {
    // Build a fixture using only API common to both 1.4.17 and 1.4.19.
    SettableIDGenerator generator = new SettableIDGenerator();

    // serialize() does not perform any security check, so it succeeds on both versions.
    String xml = IDGeneratorSerializer.serialize(generator);
    assertNotNull(xml);

    // deserialize() is the real production path under test.
    // On 1.4.19 without the whitelist this throws a BadRequestException whose cause
    // is a ForbiddenClassException (the SIGNAL); with the whitelist it succeeds.
    SettableIDGenerator roundTripped = IDGeneratorSerializer.deserialize(xml);

    // Assert the pre-break outcome: the object loads.
    assertNotNull(roundTripped);
  }
}
