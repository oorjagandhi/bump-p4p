package com.example;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.StreamReadConstraints;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * ADAPTED code — the real client fix (dotCMS/core, cibseven, ESSI-Lab/DAB, mats3): build the
 * ObjectMapper on a JsonFactory whose StreamReadConstraints raise the limit the 2.15 default
 * now enforces. StreamReadConstraints is a 2.15-only API, so this variant is compiled only
 * under the 'adapted' profile (state 3), against jackson 2.15.
 */
public class JsonLoaderAdapted {
    public JsonNode load(String json) throws Exception {
        JsonFactory factory = JsonFactory.builder()
                .streamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(5000).build())
                .build();
        return new ObjectMapper(factory).readTree(json);
    }
}
