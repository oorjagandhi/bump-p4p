import re, sys
# Force EVERY dependency under <groupId> to version <newv> in a Maven pom (covers
# multi-artifact libraries, e.g. poi + poi-ooxml + poi-scratchpad).
pom, group, newv = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(pom, encoding="utf-8").read()
pat = re.compile(r"(<groupId>\s*" + re.escape(group) +
                 r"\s*</groupId>\s*<artifactId>[^<]+</artifactId>\s*<version>\s*)([^<]+?)(\s*</version>)", re.S)
n = len(pat.findall(s))
open(pom, "w", encoding="utf-8").write(pat.sub(lambda m: m.group(1) + newv + m.group(3), s))
print(f"[set-baseline] {group}:* -> {newv} at {n} site(s)")
