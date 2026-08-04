package com.example;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * PARENT (pre-adaptation) code: plain `new ObjectMapper().readTree(json)`.
 * Compiles UNCHANGED against jackson 2.14 and 2.15, so states 1 and 2 differ only in the
 * library version (isolating the behavioural break).
 *
 * jackson-core 2.14: parses deeply-nested JSON.
 * jackson-core 2.15: default StreamReadConstraints (maxNestingDepth=1000) rejects it ->
 *                    StreamConstraintsException at parse time = the behavioural break.
 */
public class JsonLoaderParent {
    public JsonNode load(String json) throws Exception {
        return new ObjectMapper().readTree(json);
    }
}
