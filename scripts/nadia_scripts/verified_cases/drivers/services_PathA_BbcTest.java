package bbc;

import static org.junit.Assert.assertNotNull;

import org.junit.Test;

import org.collectionspace.services.id.IDGeneratorSerializer;
import org.collectionspace.services.id.SettableIDGenerator;

/**
 * Reproduces the XStream 1.4.17 -> 1.4.19 behavioural break through the client's
 * real production serializer.
 *
 * XStream switched from a default blacklist to a default whitelist. The client's
 * deserialize() path drives xstream.fromXML(...), which at 1.4.19 rejects the
 * SettableIDGenerator / IDGenerator hierarchy with a ForbiddenClassException
 * unless the production code explicitly whitelists it (allowTypeHierarchy(...)).
 *
 * Shape A: IDGeneratorSerializer.deserialize(String) already existed at the
 * parent; the adaptation only added the allowTypeHierarchy calls inside it.
 * The SAME test compiles and runs at both parent and adapted code.
 *
 *  - parent code + xstream 1.4.17 -> PASS
 *  - parent code + xstream 1.4.19 -> FAIL (ForbiddenClassException surfaces)
 *  - adapted code + xstream 1.4.19 -> PASS
 */
public class BbcTest {

  @Test
  public void bbcCase() throws Exception {
    // Build the fixture using only API common to 1.4.17 and 1.4.19,
    // by driving the client's own serialize() production method.
    SettableIDGenerator generator = new SettableIDGenerator();

    String serialized = IDGeneratorSerializer.serialize(generator);
    assertNotNull(serialized);

    // Real production deserialization path: this is where the XStream default
    // whitelist trips on 1.4.19 unless the hierarchy is explicitly allowed.
    SettableIDGenerator roundTripped = IDGeneratorSerializer.deserialize(serialized);

    // Pre-break outcome: the generator survives the round trip.
    assertNotNull(roundTripped);
  }
}
