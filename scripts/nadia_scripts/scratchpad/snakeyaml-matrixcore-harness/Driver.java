import org.bukkit.configuration.file.YamlConfiguration;

/**
 * Drives MatrixCore/Bukkit's OWN production path -- YamlConfiguration.loadFromString --
 * with a config larger than snakeyaml 1.32's 3 MiB code-point limit.
 *
 *   1  parent code  + snakeyaml 1.31  -> loads   (limit does not exist yet)
 *   2  parent code  + snakeyaml 1.33  -> THROWS  (3 MiB default)
 *   3  adapted code + snakeyaml 1.33  -> loads   (SPIGOT-7161 sets Integer.MAX_VALUE)
 */
public class Driver {
    public static void main(String[] args) throws Exception {
        int mb = args.length > 0 ? Integer.parseInt(args[0]) : 4;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; sb.length() < (long) mb * 1024 * 1024; i++) {
            sb.append("key").append(i).append(": \"").append("x".repeat(200)).append("\"\n");
        }
        System.out.println("config size: " + (sb.length() / (1024 * 1024)) + " MB");
        try {
            YamlConfiguration cfg = new YamlConfiguration();
            cfg.loadFromString(sb.toString());
            System.out.println("RESULT: LOADED (" + cfg.getKeys(false).size() + " keys)");
        } catch (Throwable t) {
            Throwable root = t;
            while (root.getCause() != null && root.getCause() != root) root = root.getCause();
            String m = String.valueOf(root.getMessage()).replace('\n', ' ');
            System.out.println("RESULT: THREW " + root.getClass().getName() + ": "
                    + (m.length() > 115 ? m.substring(0, 115) : m));
        }
    }
}
