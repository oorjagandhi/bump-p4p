package bbc;

import static org.junit.Assert.assertNotNull;

import de.cubeside.globalserver.plugin.PluginDescription;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import org.junit.Test;

public class BbcTest {

    @Test
    public void bbcCase() throws Exception {
        // Build a jar containing a plugin.yml whose YAML content exceeds
        // snakeyaml 1.32's default 3MB code point limit but is otherwise valid.
        File jar = File.createTempFile("bbc-plugin", ".jar");
        jar.deleteOnExit();

        StringBuilder sb = new StringBuilder();
        sb.append("name: TestPlugin\n");
        sb.append("main: com.example.Main\n");
        sb.append("version: 1.0.0\n");
        sb.append("description: ");
        int payload = 4 * 1024 * 1024; // 4MB > default 3MB code point limit
        for (int i = 0; i < payload; i++) {
            sb.append('a');
        }
        sb.append('\n');
        byte[] yml = sb.toString().getBytes(StandardCharsets.UTF_8);

        try (JarOutputStream jos = new JarOutputStream(new FileOutputStream(jar))) {
            JarEntry entry = new JarEntry("plugin.yml");
            jos.putNextEntry(entry);
            jos.write(yml);
            jos.closeEntry();
        }

        // Drives the client's real production path. On snakeyaml 1.32 with the
        // pre-adaptation code the default code point limit trips and the
        // constructor surfaces a YAMLException ("exceeds the limit" / "code points").
        // With the override (setCodePointLimit) it loads successfully.
        PluginDescription pd = new PluginDescription(jar);
        assertNotNull(pd);
    }
}
