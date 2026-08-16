import org.apache.commons.io.input.XmlStreamReader;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

public class Probe {
    static void t(String label, String xml) {
        try (XmlStreamReader r = new XmlStreamReader(
                new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)))) {
            System.out.printf("  %-46s -> %s%n", label, r.getEncoding());
        } catch (Exception e) {
            System.out.printf("  %-46s -> THREW %s%n", label, e.getClass().getSimpleName());
        }
    }
    public static void main(String[] a) {
        System.out.println("commons-io " + org.apache.commons.io.IOUtils.class.getPackage().getImplementationVersion());
        t("version + encoding (canonical)",  "<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?><r/>");
        t("encoding only, NO version",       "<?xml encoding=\"ISO-8859-1\"?><r/>");
        t("single quotes, no version",       "<?xml encoding='ISO-8859-1'?><r/>");
        t("version + encoding, extra spaces","<?xml  version = \"1.0\"  encoding = \"ISO-8859-1\" ?><r/>");
        t("standalone between the two",      "<?xml version=\"1.0\" standalone=\"yes\" encoding=\"ISO-8859-1\"?><r/>");
    }
}
