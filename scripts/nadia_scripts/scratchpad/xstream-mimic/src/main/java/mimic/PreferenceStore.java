package mimic;

import com.thoughtworks.xstream.XStream;
import com.thoughtworks.xstream.io.xml.DomDriver;

/**
 * PRODUCTION component that persists a {@link PreferenceModel} to/from XML via
 * XStream — the shape of chainsaw's real usage (e.g.
 * {@code ApplicationPreferenceModelSaver}), where the XStream instance is built
 * and used by production code rather than a test.
 *
 * <p>This is where the ADAPTATION belongs. XStream 1.4.18 switched to a
 * default-deny security model: {@code fromXML} on a class that is not on the
 * allowlist throws {@code ForbiddenClassException}. The fix is to allowlist the
 * deserialized type on the XStream instance used by production code.
 *
 * <p>The adaptation is gated on the {@code mimic.adapt} system property purely so
 * the same build can demonstrate the pre- and post-adaptation states; in a real
 * client the {@code allowTypes(...)} call would simply be present.
 */
public class PreferenceStore {

    private XStream newXStream() {
        XStream stream = new XStream(new DomDriver());
        if (Boolean.getBoolean("mimic.adapt")) {
            // ── ADAPTATION (production code) ──
            // Satisfies XStream >= 1.4.18 default-deny for our own domain type.
            stream.allowTypes(new Class[]{ PreferenceModel.class });
        }
        return stream;
    }

    /** Serialize (marshal) — allowed under all XStream versions. */
    public String save(PreferenceModel model) {
        return newXStream().toXML(model);
    }

    /** Deserialize (unmarshal) — throws ForbiddenClassException under >=1.4.18
     *  unless the type has been allowlisted. */
    public PreferenceModel load(String xml) {
        return (PreferenceModel) newXStream().fromXML(xml);
    }
}
