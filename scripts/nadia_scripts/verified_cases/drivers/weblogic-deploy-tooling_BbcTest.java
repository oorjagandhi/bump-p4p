package bbc;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import oracle.weblogic.deploy.yaml.YamlTranslator;
import org.junit.jupiter.api.Test;
import org.python.core.PyDictionary;

/**
 * SEAM_A driver — snakeyaml-1.31-to-1.32-codepointlimit on oracle/weblogic-deploy-tooling.
 *
 * <p>Drives WDT's real production entry point for reading a model file: {@code
 * YamlTranslator(fileName, useOrderedDict).parse()}, which is what the adaptation commit
 * ("Snakeyaml 1.33 and exit handling refactor", #1208) threads the new code-point limit
 * through. The shape of the call is copied from WDT's own YamlTranslatorTest, so the driver
 * exercises the same path their suite does, only with a model file over the ceiling.
 *
 * <p>The TWO-ARGUMENT constructor is used deliberately. It exists at the parent and at the
 * adaptation, so one source compiles in all three states — and it is the overload every
 * existing caller uses. At the adaptation it forwards {@code maxCodePoints = 0}, which
 * AbstractYamlTranslator reads as "leave snakeyaml's default alone", so this driver also
 * answers whether the adaptation restored the DEFAULT path or only exposed a knob.
 */
public class BbcTest {

  @Test
  void parsesModelFileLargerThanTheDefaultCodePointLimit() throws Exception {
    int target = 4 * 1024 * 1024;   // over the 3145728 code point default 1.32 imposes
    StringBuilder doc = new StringBuilder(target + 32).append("domainInfo: ");
    while (doc.length() < target) {
      doc.append('x');
    }
    doc.append('\n');

    Path model = Files.createTempFile("bbc-wdt-model", ".yaml");
    model.toFile().deleteOnExit();
    Files.write(model, doc.toString().getBytes(StandardCharsets.UTF_8));

    PyDictionary parsed = new YamlTranslator(model.toAbsolutePath().toString(), true).parse();

    assertNotNull(parsed, "a 4 MB model file should parse into a dict");
  }
}
