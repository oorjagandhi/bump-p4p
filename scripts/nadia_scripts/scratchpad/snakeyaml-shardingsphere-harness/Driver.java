import org.apache.shardingsphere.infra.util.yaml.YamlEngine;

import java.util.Map;

/**
 * Drives apache/shardingsphere's OWN production path -- YamlEngine.unmarshal(String, Class)
 * -- with a YAML document larger than snakeyaml 1.32's 3 MiB code-point limit.
 *
 * That method is literally `new Yaml(new ShardingSphereYamlConstructor(classType))
 * .loadAs(yamlContent, classType)`, and ShardingSphereYamlConstructor is the class their
 * commit changed.
 *
 *   1  parent code  + snakeyaml 1.31  -> loads   (the limit does not exist yet)
 *   2  parent code  + snakeyaml 1.33  -> THROWS  (3 MiB default)
 *   3  adapted code + snakeyaml 1.33  -> loads   (their fix sets Integer.MAX_VALUE)
 *
 * All three snakeyaml versions carry every constructor this code touches, so nothing is
 * shadowed by a compile break -- checked with javap before running.
 */
public class Driver {

    public static void main(String[] args) {
        int mb = args.length > 0 ? Integer.parseInt(args[0]) : 4;
        StringBuilder sb = new StringBuilder();
        long target = (long) mb * 1024 * 1024;
        for (int i = 0; sb.length() < target; i++) {
            sb.append("key").append(i).append(": \"").append("x".repeat(200)).append("\"\n");
        }
        String yaml = sb.toString();
        System.out.println("document size: " + (yaml.length() / (1024 * 1024)) + " MB");
        try {
            Map<?, ?> out = YamlEngine.unmarshal(yaml, Map.class);
            System.out.println("RESULT: LOADED (" + out.size() + " keys)");
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
