import com.opentext.ia.yaml.core.YamlMap;

/**
 * Drives infoarchive-sip-sdk's OWN production path -- YamlMap.from(String) -- with a YAML
 * document larger than snakeyaml 1.32's new 3 MB code-point limit.
 *
 * This is the differential the project's own tests cannot perform: a >3 MB fixture is not
 * something anyone checks into a repo, so the break only ever showed up against real data.
 *
 * Expected across the three states:
 *   1  parent code + snakeyaml 1.31   -> loads      (limit does not exist yet)
 *   2  parent code + snakeyaml 2.0    -> THROWS     (3 MB default limit)
 *   3  adapted code + snakeyaml 2.0   -> loads      (their fix raises it to 10 MB)
 */
public class Driver {

  public static void main(String[] args) {
    int mb = args.length > 0 ? Integer.parseInt(args[0]) : 4;
    String yaml = "key: " + "a".repeat(mb * 1024 * 1024) + "\n";
    System.out.println("document size: " + mb + " MB");
    try {
      YamlMap map = YamlMap.from(yaml);
      Object v = map.get("key").toString();
      System.out.println("RESULT: LOADED (value length " + String.valueOf(v).length() + ")");
    } catch (Throwable t) {
      Throwable root = t;
      while (root.getCause() != null && root.getCause() != root) {
        root = root.getCause();
      }
      String msg = String.valueOf(root.getMessage()).replace('\n', ' ');
      if (msg.length() > 130) {
        msg = msg.substring(0, 130) + "...";
      }
      System.out.println("RESULT: THREW " + root.getClass().getName() + ": " + msg);
    }
  }
}
