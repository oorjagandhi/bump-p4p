package com.example;

import org.yaml.snakeyaml.Yaml;

/**
 * PARENT (pre-adaptation) code — byte-for-byte the shape of telaminai/mongoose-plugins
 * EventHandlerLoader BEFORE commit 9e5916e1: a Constructor rooted at the cfg type with a
 * plain LoaderOptions and NO tag inspector.
 *
 * snakeyaml 1.x: resolves the `!!com.example.MyNode` global tag by instantiating the class.
 * snakeyaml 2.0: the default (restrictive) tag inspector rejects the global tag and throws
 *                ("Global tag is not allowed") -> the behavioural break.
 *
 * Uses plain `new Yaml()` — the idiom that compiles UNCHANGED against both 1.33 and 2.0 (so
 * states 1 and 2 differ only in the library version, isolating the behavioural break from
 * snakeyaml 2.0's separate Constructor-signature compile break). This is also byte-for-byte
 * quarkusio/quarkus's real parent code before commit 06a8c629 (`new Yaml()`). On 2.0 the
 * default restrictive tag inspector rejects the `!!com.example.MyNode` global tag.
 */
public class YamlLoaderParent {
    public Cfg load(String yaml) {
        return new Yaml().loadAs(yaml, Cfg.class);
    }
}
