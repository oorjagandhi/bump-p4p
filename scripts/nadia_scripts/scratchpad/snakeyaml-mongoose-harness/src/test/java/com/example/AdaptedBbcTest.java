package com.example;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Test;

/**
 * ADAPTED-code state of the differential (compiled+run under the 'adapted' profile;
 * uses the 2.0-only setTagInspector API, so it is only built against snakeyaml 2.0).
 *   STATE 3: adapted + snakeyaml 2.0 -> PASS  (re-permitted types load again)
 */
public class AdaptedBbcTest {

    static final String YAML =
            "nodes:\n" +
            "  - !!com.example.MyNode {name: hello}\n" +
            "  - !!com.example.MyNode {name: world}\n";

    @Test
    public void adaptedLoadsFqnTaggedYaml() {
        Cfg cfg = new YamlLoaderAdapted().load(YAML);
        assertNotNull(cfg);
        assertEquals(2, cfg.nodes.size());
        assertEquals("world", cfg.nodes.get(1).name);
    }
}
