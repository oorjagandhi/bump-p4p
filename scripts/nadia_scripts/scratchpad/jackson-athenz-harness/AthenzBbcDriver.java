package com.yahoo.athenz.zms_aws_domain_syncer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Drives AthenZ's OWN adaptation -- ZmsSyncer.setupJsonParserLimits() -- and then parses a
 * JSON string larger than jackson-core 2.15's 20 MB maxStringLength default.
 *
 *   1  parent code  + jackson-core 2.14.2  -> parses   (no constraint exists yet)
 *   2  parent code  + jackson-core 2.15.2  -> THROWS   (20 MB default)
 *   3  adapted code + jackson-core 2.15.2  -> parses   (their override raises it to 200 MB)
 *
 * setupJsonParserLimits() is package-private and uses no instance state, and their
 * three-arg constructor skips the AWS setup the no-arg one performs -- so this runs their
 * real method, reading their own Config default of 200000000, with nothing substituted.
 * The override is JVM-global, which is why a plain ObjectMapper afterwards sees it, exactly
 * as their servers rely on.
 */
public class AthenzBbcDriver {

    public static void main(String[] args) throws Exception {
        boolean applyAdaptation = args.length > 0 && args[0].equals("adapt");
        int mb = args.length > 1 ? Integer.parseInt(args[1]) : 25;

        if (applyAdaptation) {
            new ZmsSyncer(null, null, null).setupJsonParserLimits();
            System.out.println("applied AthenZ setupJsonParserLimits()");
        }

        StringBuilder sb = new StringBuilder("{\"v\":\"");
        sb.append("x".repeat(mb * 1024 * 1024));
        sb.append("\"}");
        System.out.println("json string field: " + mb + " MB");
        try {
            JsonNode n = new ObjectMapper().readTree(sb.toString());
            System.out.println("RESULT: PARSED (len " + n.get("v").asText().length() + ")");
        } catch (Throwable t) {
            Throwable root = t;
            while (root.getCause() != null && root.getCause() != root) root = root.getCause();
            String m = String.valueOf(root.getMessage()).replace('\n', ' ');
            System.out.println("RESULT: THREW " + root.getClass().getSimpleName() + ": "
                    + (m.length() > 110 ? m.substring(0, 110) : m));
        }
    }
}
