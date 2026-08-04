package com.example;

import java.util.ArrayList;
import java.util.List;

/** Root config the loader deserializes, mirroring EventHandlerLoader.EventProcessorYamlCfg:
 *  a container whose entries are user node objects referenced by FQN global tags. */
public class Cfg {
    public List<MyNode> nodes = new ArrayList<>();
}
