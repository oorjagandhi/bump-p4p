```java
package bbc;

import java.lang.reflect.Method;

import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;

import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * Reproduces snakeyaml 1.31 -> 1.32 behavioural break: 1.32 imposes a default
 * 3MB (3145728) code-point limit on document loading. A YAML document larger
 * than that limit loads fine on 1.31 but throws
 * org.yaml.snakeyaml.error.YAMLException ("... exceeds the limit ... code points")
 * on 1.32 unless the loader's code-point limit is raised.
 *
 * WDT adapted by wiring a configurable codePointsLimit into
 * AbstractYamlTranslator.getDefaultLoaderOptions() which calls
 * LoaderOptions.setCodePointLimit(...). The adapted() method below mirrors that
 * exact production configuration.
 */
public class BbcTest {

    /**
     * Builds a deterministic YAML mapping whose serialized form comfortably
     * exceeds the 1.32 default code-point limit of 3,145,728 code points.
     */
    private static String buildOversizedYaml() {
        StringBuilder sb = new StringBuilder(5 * 1024 * 1024);
        sb.append("root:\n");
        // ~200000 unique lines, each ~20+ chars -> well over 3,145,728 code points.
        for (int i = 0; i < 200000; i++) {
            sb.append("  key").append(i).append(": value").append(i).append('\n');
        }
        return sb.toString();
    }

    /**
     * Pre-ad
