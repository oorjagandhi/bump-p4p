package com.example;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.Test;

/**
 * ADAPTED-code state (compiled+run under the 'adapted' profile; uses the 2.15-only
 * StreamReadConstraints API, built only against jackson 2.15).
 *   STATE 3: adapted + jackson 2.15.0 -> PASS  (raised maxNestingDepth admits the input again)
 */
public class AdaptedBbcTest {

    static String deeplyNested() {
        int depth = 1001;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < depth; i++) sb.append('[');
        for (int i = 0; i < depth; i++) sb.append(']');
        return sb.toString();
    }

    @Test
    public void adaptedParsesDeeplyNestedJson() throws Exception {
        JsonNode node = new JsonLoaderAdapted().load(deeplyNested());
        assertNotNull(node);
        assertTrue(node.isArray());
    }
}
