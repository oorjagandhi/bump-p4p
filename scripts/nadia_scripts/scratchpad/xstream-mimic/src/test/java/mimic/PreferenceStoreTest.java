package mimic;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/**
 * Derived from the BUMP failing test
 * {@code org.apache.log4j.chainsaw.LogPanelPreferenceModelTest#testLogPanelPreferenceModelSerialization}
 * (breaking commit 19e20b0d in apache/logging-chainsaw). Same shape: mutate a
 * model, round-trip it through XStream, assert the properties survive.
 *
 * <p>Crucially, this test contains NO XStream security configuration. All XStream
 * setup — including the allowTypes adaptation — lives in the production class
 * {@link PreferenceStore}. So a green run here means production code, not the
 * test, was adapted.
 */
public class PreferenceStoreTest {

    @Test
    public void testPreferenceModelSerialization() {
        PreferenceModel model = new PreferenceModel();
        model.setLevelIcons(true);
        model.setDateFormatPattern("yyyy-MM-dd HH:mm:ss");
        model.setLoggerPrecision(3);
        model.setLogTreePanelVisible(false);
        model.setScrollToBottom(false);
        model.setToolTips(true);

        PreferenceStore store = new PreferenceStore();

        String xml = store.save(model);                 // marshal (always allowed)
        PreferenceModel restored = store.load(xml);      // unmarshal -> break point

        assertEquals(model.isLevelIcons(), restored.isLevelIcons());
        assertEquals(model.getDateFormatPattern(), restored.getDateFormatPattern());
        assertEquals(model.getLoggerPrecision(), restored.getLoggerPrecision());
        assertEquals(model.isLogTreePanelVisible(), restored.isLogTreePanelVisible());
        assertEquals(model.isScrollToBottom(), restored.isScrollToBottom());
        assertEquals(model.isToolTips(), restored.isToolTips());
    }
}
