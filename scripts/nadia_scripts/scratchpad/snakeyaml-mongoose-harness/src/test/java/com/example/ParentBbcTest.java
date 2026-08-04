package com.example;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Test;

/**
 * PARENT-code state of the differential (compiled+run under the 'parent' profile).
 *   STATE 1: snakeyaml 1.33 -> PASS  (global tag resolved, nodes populated)
 *   STATE 2: snakeyaml 2.0  -> FAIL  (YAMLException: Global tag is not allowed)
 */
public class ParentBbcTest {

    static final String YAML =
            "nodes:\n" +
            "  - !!com.example.MyNode {name: hello}\n" +
            "  - !!com.example.MyNode {name: world}\n";

    @Test
    public void parentLoadsFqnTaggedYaml() {
        Cfg cfg = new YamlLoaderParent().load(YAML);   // throws on snakeyaml 2.0
        assertNotNull(cfg);
        assertEquals(2, cfg.nodes.size());
        assertEquals("hello", cfg.nodes.get(0).name);
    }
}
