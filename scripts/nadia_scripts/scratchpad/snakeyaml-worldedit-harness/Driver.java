import com.sk89q.util.yaml.YAMLProcessor;

import java.io.File;
import java.io.FileWriter;

/**
 * Drives WorldEdit's OWN production path -- new YAMLProcessor(File, boolean).load() --
 * over a config file larger than snakeyaml 1.32's 3 MiB code-point limit.
 *
 *   1  parent code  + snakeyaml 1.26  -> loads   (their ACTUAL previous version)
 *   2  parent code  + snakeyaml 1.33  -> THROWS  (3 MiB default limit)
 *   3  adapted code + snakeyaml 1.33  -> loads   (their fix sets 64 MB)
 *
 * Unlike every other case in this study the baseline is not a stand-in: EngineHub bumped
 * 1.26 -> 1.33 and applied the fix in the SAME commit (0ef38b52), so 1.26 is precisely
 * what they were running before.
 */
public class Driver {

    public static void main(String[] args) throws Exception {
        int mb = args.length > 0 ? Integer.parseInt(args[0]) : 4;
        File f = File.createTempFile("worldedit-bbc-", ".yml");
        f.deleteOnExit();
        // A valid WorldEdit-style config: many scalar keys until the file exceeds `mb`.
        try (FileWriter w = new FileWriter(f)) {
            w.write("limits:\n");
            long target = (long) mb * 1024 * 1024;
            long written = 8;
            for (int i = 0; written < target; i++) {
                String line = "  key-" + i + ": \"" + "x".repeat(200) + "\"\n";
                w.write(line);
                written += line.length();
            }
        }
        System.out.println("config size: " + (f.length() / (1024 * 1024)) + " MB");
        try {
            YAMLProcessor p = new YAMLProcessor(f, false);
            p.load();
            Object v = p.getProperty("limits.key-0");
            System.out.println("RESULT: LOADED (limits.key-0 length "
                    + String.valueOf(v).length() + ")");
        } catch (Throwable t) {
            Throwable root = t;
            while (root.getCause() != null && root.getCause() != root) {
                root = root.getCause();
            }
            String m = String.valueOf(root.getMessage()).replace('\n', ' ');
            System.out.println("RESULT: THREW " + root.getClass().getName() + ": "
                    + (m.length() > 120 ? m.substring(0, 120) : m));
        }
    }
}
