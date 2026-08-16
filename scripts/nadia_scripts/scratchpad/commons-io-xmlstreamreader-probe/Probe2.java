import org.apache.commons.io.input.XmlStreamReader;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
public class Probe2 {
    static void t(String label, String xml) {
        try (XmlStreamReader r = new XmlStreamReader(
                new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)))) {
            System.out.printf("  %-52s -> %s%n", label, r.getEncoding());
        } catch (Exception e) {
            System.out.printf("  %-52s -> THREW %s%n", label, e.getClass().getSimpleName());
        }
    }
    public static void main(String[] a) {
        // all of these are WELL-FORMED per the XML spec: VersionInfo EncodingDecl? SDDecl?
        t("version + encoding, both single-quoted", "<?xml version='1.0' encoding='ISO-8859-1'?><r/>");
        t("newline between version and encoding",   "<?xml version=\"1.0\"\n      encoding=\"ISO-8859-1\"?><r/>");
        t("tab between version and encoding",       "<?xml version=\"1.0\"\tencoding=\"ISO-8859-1\"?><r/>");
        t("XML 1.1",                                "<?xml version=\"1.1\" encoding=\"ISO-8859-1\"?><r/>");
        t("encoding + standalone (spec order)",     "<?xml version=\"1.0\" encoding=\"ISO-8859-1\" standalone=\"yes\"?><r/>");
        t("encoding name with digits/underscore",   "<?xml version=\"1.0\" encoding=\"windows-1252\"?><r/>");
        t("mixed quotes: version', encoding\"",     "<?xml version='1.0' encoding=\"ISO-8859-1\"?><r/>");
        t("leading comment before decl (invalid)",  "<!-- c --><?xml version=\"1.0\" encoding=\"ISO-8859-1\"?><r/>");
    }
}
