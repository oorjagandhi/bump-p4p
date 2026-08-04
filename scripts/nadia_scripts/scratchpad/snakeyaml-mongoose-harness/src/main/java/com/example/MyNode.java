package com.example;

/** A node type a user references from YAML by its fully-qualified name (a global tag),
 *  mirroring how telaminai/mongoose-plugins users reference processor node classes via
 *  `!!com.telamin...SomeNode` in the loader's YAML. */
public class MyNode {
    public String name;

    @Override
    public String toString() {
        return "MyNode(" + name + ")";
    }
}
