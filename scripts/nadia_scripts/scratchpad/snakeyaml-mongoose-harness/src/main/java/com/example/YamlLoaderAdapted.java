package com.example;

import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.Constructor;

/**
 * ADAPTED code — the exact fix telaminai/mongoose-plugins applied in commit 9e5916e1
 * ("TagInspector permits FQN tags"): install a permissive tag inspector on LoaderOptions
 * so the loader's own node classes are re-permitted under snakeyaml 2.0's default-deny.
 *
 * The single added line `opts.setTagInspector(tag -> true)` is the whole adaptation, and is
 * the direct YAML analogue of xstream's `allowTypes(...)` allowlist.
 */
public class YamlLoaderAdapted {
    public Cfg load(String yaml) {
        LoaderOptions opts = new LoaderOptions();
        opts.setTagInspector(tag -> true);          // <-- the adaptation
        Constructor ctor = new Constructor(Cfg.class, opts);
        return new Yaml(ctor).loadAs(yaml, Cfg.class);
    }
}
