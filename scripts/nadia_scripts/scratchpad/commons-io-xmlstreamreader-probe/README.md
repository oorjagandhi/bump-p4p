# commons-io 2.13.0 -> 2.14.0 — boundary probe

The empirical pin for `commons-io-2.13-to-2.14-xmlstreamreader-encoding`. Run each probe
against both jars and compare:

```bash
curl -sSO https://repo.maven.apache.org/maven2/commons-io/commons-io/2.13.0/commons-io-2.13.0.jar
curl -sSO https://repo.maven.apache.org/maven2/commons-io/commons-io/2.14.0/commons-io-2.14.0.jar
for v in 2.13.0 2.14.0; do
  javac -cp commons-io-$v.jar -d out_$v Probe.java
  java  -cp "commons-io-$v.jar;out_$v" Probe      # ';' on Windows, ':' elsewhere
done
```

`Probe.java` covers malformed declarations — three of five flip.
`Probe2.java` covers well-formed ones — eight of eight are identical.

That pair is the whole finding: the behaviour change is real but confined to XML
declarations that are invalid per the spec, and there is no API to restore the old
behaviour. See the catalog entry's `assessment` block.

Kept because a negative result is only reusable if someone can re-run it.
