package bbc;

import static org.junit.Assert.assertEquals;

import de.cubeside.globalserver.plugin.PluginDescription;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import org.junit.Test;

/**
 * SEAM_A driver — snakeyaml-1.31-to-1.32-codepointlimit on Brokkonaut/GlobalConnectionServer.
 *
 * <p>Drives the production constructor {@code PluginDescription(File)}, which reads a plugin
 * jar's {@code plugin.yml} through {@code new Yaml(new SafeConstructor())}. That call is
 * exactly what the adaptation changed, to {@code new SafeConstructor(loaderOptions)} with
 * {@code setCodePointLimit(Integer.MAX_VALUE)}.
 *
 * <p>The fixture builds a real jar rather than handing the parser a string, because the
 * production path reads from a {@code JarFile} entry and nothing else — a string-level
 * fixture would be testing snakeyaml, not this client. The document carries the three fields
 * PluginDescription requires after the parse (name, main, version) so that a run which gets
 * PAST the limit fails on nothing else, and one long scalar to push it over the ceiling.
 *
 * <p>JUnit 4 because this project declares no test framework at all; the harness injects
 * junit:junit as a test-scoped dependency (see run_worklist.inject_test_dep for why 4 and
 * not Jupiter).
 */
public class BbcTest {

    @Test
    public void readsPluginYmlLargerThanTheDefaultCodePointLimit() throws Exception {
        int target = 4 * 1024 * 1024;   // over the 3145728 code point default 1.32 imposes
        StringBuilder yml = new StringBuilder(target + 128)
                .append("name: BbcPlugin\n")
                .append("main: de.cubeside.bbc.BbcPlugin\n")
                .append("version: 1.0.0\n")
                .append("description: \"");
        while (yml.length() < target) {
            yml.append('x');
        }
        yml.append("\"\n");

        File jar = File.createTempFile("bbc-plugin", ".jar");
        jar.deleteOnExit();
        try (JarOutputStream out = new JarOutputStream(new FileOutputStream(jar))) {
            out.putNextEntry(new JarEntry("plugin.yml"));
            out.write(yml.toString().getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
        }

        PluginDescription description = new PluginDescription(jar);

        assertEquals("BbcPlugin", description.getName());
    }
}
