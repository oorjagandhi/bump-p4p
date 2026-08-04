package com.example;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.Test;

/**
 * PARENT-code state (compiled+run under the 'parent' profile).
 *   STATE 1: jackson 2.14.2 -> PASS  (deeply-nested JSON parses)
 *   STATE 2: jackson 2.15.0 -> FAIL  (StreamConstraintsException: nesting depth exceeds 1000)
 */
public class ParentBbcTest {

    // 1001 levels of array nesting — one past jackson 2.15's default maxNestingDepth (1000).
    static String deeplyNested() {
        int depth = 1001;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < depth; i++) sb.append('[');
        for (int i = 0; i < depth; i++) sb.append(']');
        return sb.toString();
    }

    @Test
    public void parentParsesDeeplyNestedJson() throws Exception {
        JsonNode node = new JsonLoaderParent().load(deeplyNested());  // throws on jackson 2.15
        assertNotNull(node);
        assertTrue(node.isArray());
    }
}
