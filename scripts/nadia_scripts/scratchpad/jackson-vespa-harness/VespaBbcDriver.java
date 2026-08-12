import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import com.yahoo.document.DataType;
import com.yahoo.document.DocumentPut;
import com.yahoo.document.DocumentType;
import com.yahoo.document.DocumentTypeManager;
import com.yahoo.document.Field;
import com.yahoo.document.json.JsonFeedReader;
import com.yahoo.vespaxmlparser.FeedOperation;

/**
 * Trigger for the jackson-core 2.15 StreamReadConstraints break against vespa-engine/vespa's
 * OWN document-feed reader.
 *
 * JsonFeedReader is the class vespa reads JSON feed files through, and its private static
 * `jsonFactory` is exactly what their fix reconfigures. Nothing of theirs is reconstructed:
 * this constructs a JsonFeedReader over their real JsonReader and asks it for the next
 * operation. Only the document, the document type, and this main() are ours.
 *
 * WHY JsonFeedReader AND NOT JsonWriter, which is the file the code search actually hit:
 * JsonWriter's factory produces GENERATORS, so the maxStringLength read constraint their
 * commit sets there is never exercised by writing -- it is defensive, for the factory's
 * shared use. The break is a PARSE-time failure, so demonstrating it needs the read path.
 * Both files were changed in the same commit, and JsonFeedReader is the one where the
 * constraint bites.
 *
 * The document type and the feed JSON follow their own JsonReaderTestCase idioms: a
 * DocumentTypeManager with one registered type, and the array-of-operations feed format.
 *
 * The field is 10,000,000 characters, above jackson 2.15.0's 5,000,000 default -- 2.15.0
 * being the exact version vespa bumped to six days before this commit.
 *
 *   state 1  parent code + jackson 2.14.2  -> PARSED (no constraints exist before 2.15)
 *   state 2  parent code + jackson 2.15.0  -> THROWS StreamConstraintsException
 *   state 3  adapted code + jackson 2.15.0 -> PARSED (their Integer.MAX_VALUE raise)
 */
public class VespaBbcDriver {

    public static void main(String[] args) throws Exception {
        int size = 10_000_000;                  // > 5,000,000, the 2.15.0 default

        DocumentTypeManager types = new DocumentTypeManager();
        DocumentType smoke = new DocumentType("smoke");
        smoke.addField(new Field("something", DataType.STRING));
        types.registerDocumentType(smoke);

        StringBuilder sb = new StringBuilder(size + 128);
        sb.append("[{\"put\":\"id:unittest:smoke::doc1\",\"fields\":{\"something\":\"");
        for (int i = 0; i < size; i++) {
            sb.append('x');
        }
        sb.append("\"}}]");
        InputStream in = new ByteArrayInputStream(sb.toString().getBytes(StandardCharsets.UTF_8));

        System.out.println("[driver] jackson-core loaded from: "
                + locationOf("com.fasterxml.jackson.core.JsonFactory"));
        System.out.println("[driver] maxStringLength in force: " + maxStringLength());
        System.out.println("[driver] string field length: " + size);

        try {
            FeedOperation op = new JsonFeedReader(in, types).read();
            DocumentPut put = op.getDocumentPut();
            int len = put.getDocument().getFieldValue("something").toString().length();
            System.out.println("RESULT=PARSED type=" + op.getType() + " len=" + len);
        } catch (Throwable t) {
            System.out.println("RESULT=THREW " + describe(t));
        }
    }

    /** vespa wraps parse failures, so the jackson cause can sit a level or two down. */
    private static String describe(Throwable t) {
        StringBuilder sb = new StringBuilder();
        for (Throwable c = t; c != null && sb.length() < 600; c = c.getCause()) {
            if (sb.length() > 0) {
                sb.append("  <- caused by: ");
            }
            String line = String.valueOf(c.getMessage()).split("\n")[0];
            if (line.length() > 200) {
                line = line.substring(0, 200) + "...[" + line.length() + " chars]";
            }
            sb.append(c.getClass().getName()).append(": ").append(line);
            if (c.getCause() == c) {
                break;
            }
        }
        return sb.toString();
    }

    /** Where jackson actually came from, so a state cannot silently run the wrong version. */
    private static String locationOf(String className) {
        try {
            Class<?> c = Class.forName(className);
            return String.valueOf(c.getProtectionDomain().getCodeSource().getLocation());
        } catch (Throwable t) {
            return "unknown (" + t + ")";
        }
    }

    /**
     * The cap in force on THEIR factory, read off JsonFeedReader's own static field.
     *
     * Reflection is required rather than stylistic: StreamReadConstraints does not exist
     * before 2.15, so naming the type would make this driver uncompilable against the
     * baseline. "n/a (pre-2.15)" is itself the baseline's signature.
     */
    private static String maxStringLength() {
        try {
            Class.forName("com.fasterxml.jackson.core.StreamReadConstraints");
        } catch (Throwable t) {
            return "n/a (pre-2.15: StreamReadConstraints does not exist)";
        }
        try {
            java.lang.reflect.Field f = JsonFeedReader.class.getDeclaredField("jsonFactory");
            f.setAccessible(true);
            Object factory = f.get(null);
            Object src = factory.getClass().getMethod("streamReadConstraints").invoke(factory);
            return String.valueOf(src.getClass().getMethod("getMaxStringLength").invoke(src));
        } catch (Throwable t) {
            return "unreadable (" + t.getClass().getSimpleName() + ")";
        }
    }
}
