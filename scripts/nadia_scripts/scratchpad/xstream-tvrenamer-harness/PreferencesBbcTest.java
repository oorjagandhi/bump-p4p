package org.tvrenamer.controller;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.Test;
import org.tvrenamer.model.UserPreferences;

/**
 * BBC round-trip test for the xstream 1.4.18 default-deny break, exercising
 * TVRenamer's REAL PRODUCTION persistence path
 * ({@link UserPreferencesPersistence#persist} / {@link UserPreferencesPersistence#retrieve}).
 *
 * <p>Authored for the 3-state differential (this file is not in the repo). It is
 * derived from the BUMP failing test
 * {@code org.apache.log4j.chainsaw.LogPanelPreferenceModelTest#testLogPanelPreferenceModelSerialization}:
 * same shape — mutate a preferences object, serialize, deserialize, assert the
 * value survives.
 *
 * <p>The break surfaces on {@code retrieve()} → {@code xstream.fromXML(...)}:
 * under xstream ≥1.4.18 without an allowlist it throws
 * {@code com.thoughtworks.xstream.security.ForbiddenClassException}
 * (a runtime exception; retrieve() catches only IOException, so it propagates
 * and fails this test). All XStream security config lives in the production
 * class, never here.
 */
public class PreferencesBbcTest {

    @Test
    public void preferencesDeserializeFromXml() throws Exception {
        // A realistic preferences file (root alias "preferences" -> UserPreferences).
        // No <pcs> element: XStream instantiates UserPreferences by bypassing the
        // constructor, so the PropertyChangeSupport field is simply left null. This
        // isolates the ACTUAL break — the default-deny security check on the domain
        // type UserPreferences — from unrelated listener-field serialization quirks.
        String xml = "<preferences>\n"
                   + "  <seasonPrefix>BBC-S</seasonPrefix>\n"
                   + "</preferences>\n";

        Path file = Files.createTempFile("tvrenamer-bbc", ".xml");
        Files.write(file, xml.getBytes(StandardCharsets.UTF_8));
        try {
            UserPreferences loaded =
                UserPreferencesPersistence.retrieve(file);        // unmarshal -> break point

            assertNotNull("retrieve() returned null / threw — deserialization blocked", loaded);
            assertEquals("BBC-S", loaded.getSeasonPrefix());
        } finally {
            Files.deleteIfExists(file);
        }
    }
}
