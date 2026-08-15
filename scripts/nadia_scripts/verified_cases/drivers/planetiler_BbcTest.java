package bbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.onthegomap.planetiler.util.YAML;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * SEAM_A driver — snakeyaml-engine-2.4-to-2.5-codepointlimit on onthegomap/planetiler.
 *
 * <p>Drives planetiler's OWN production YAML entry point ({@code YAML.load}), which is the
 * single place the project builds its {@code Load}, and is exactly what the adaptation
 * commit ("Load large yaml files", #1039) changed:
 *
 * <pre>
 * - new Load(LoadSettings.builder().build())
 * + new Load(LoadSettings.builder().setCodePointLimit(Integer.MAX_VALUE).build())
 * </pre>
 *
 * <p>The fixture is a single-key document whose scalar pushes the whole document just past
 * the 3 MiB (3145728 code point) ceiling snakeyaml-engine 2.5 began imposing by default. It
 * is not a copy of any planetiler schema: the break is about SIZE, and the smallest document
 * that crosses the ceiling is the one that isolates it from everything else the parser does.
 */
public class BbcTest {

  @Test
  void loadsYamlLargerThanTheDefaultCodePointLimit() {
    int target = 4 * 1024 * 1024;   // comfortably over the 3145728 code point default
    StringBuilder doc = new StringBuilder(target + 32).append("schema_name: ");
    while (doc.length() < target) {
      doc.append('x');
    }
    doc.append('\n');

    Map<?, ?> parsed = YAML.load(doc.toString(), Map.class);

    assertEquals(1, parsed.size());
    assertEquals(target - "schema_name: ".length(),
        ((String) parsed.get("schema_name")).length());
  }
}
