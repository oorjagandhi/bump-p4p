#!/usr/bin/env python3
"""
Sweep the BUMP TEST_FAILURE corpus and classify each break by the KIND of failure,
to surface the production-forcing SEMANTIC breaks (like xstream 1.4.18) worth mining
for client adaptations. Output: a ranked markdown report + a JSON shortlist.

Classification (from the reproduction log's dominant exception):
  semantic      - a runtime exception thrown from the library's own logic on a normal
                  production path (parser got stricter, default-deny, cap, validation).
                  THIS is what we want (adaptable in client production code).
  test_assertion- AssertionError / ComparisonFailure: output changed, adapted in tests.
  syntactic     - NoSuchMethod/Field/AbstractMethodError, InvalidClassException: API/serial break.
  missing_class - ClassNotFoundException/NoClassDefFoundError: relocation/namespace/classpath.
  jvm_version   - UnsupportedClassVersionError: library needs newer Java (BUMP ran Java 11).
  binding_init  - ClassCastException/ExceptionInInitializerError at logger/provider init.
  other/no_log
"""
import json, glob, os, re, collections, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = glob.glob(os.path.join(ROOT, 'data/benchmark_test_failures/*.json')) + \
        glob.glob(os.path.join(ROOT, 'data/benchmark_test_failures_merged/*.json'))
LOGDIR = os.path.join(ROOT, 'reproductionLogs/successfulReproductionLogs')

# exceptions that indicate a genuine production-domain semantic break (not framework plumbing)
SEMANTIC_HINTS = ('ForbiddenClassException', 'RecordFormatException', 'ParseException',
                  'SqlException', 'SQLException', 'ScriptBuilderException',
                  'ConstraintViolation', 'ValidationException', 'JsonParseException',
                  'ConfigurationParsingException', 'IllegalArgumentException',
                  'IllegalStateException')

def read_log(sha):
    p = os.path.join(LOGDIR, sha + '.log')
    if not os.path.exists(p): return None
    return re.sub(r'\x1b\[[0-9;]*m', '', open(p, encoding='utf-8', errors='ignore').read())

def dominant_exc(t):
    m = re.findall(r'([a-z][\w.]*\.[A-Z]\w*(?:Exception|Error))', t)
    m = [x for x in m if not any(s in x for s in ('junit', 'surefire', 'maven', 'AssertionError'))]
    return collections.Counter(m).most_common(1)

def classify(t):
    if t is None: return 'no_log', ''
    if 'UnsupportedClassVersionError' in t: return 'jvm_version', 'UnsupportedClassVersionError'
    if 'ForbiddenClassException' in t: return 'semantic', 'ForbiddenClassException'
    if 'RecordFormatException' in t: return 'semantic', 'RecordFormatException'
    if re.search(r'NoSuchMethodError|NoSuchFieldError|AbstractMethodError|InvalidClassException', t):
        return 'syntactic', dominant_exc(t)[0][0] if dominant_exc(t) else ''
    exc = dominant_exc(t)
    excname = exc[0][0] if exc else ''
    if re.search(r'ClassNotFoundException|NoClassDefFoundError', t) and not any(h in excname for h in SEMANTIC_HINTS):
        return 'missing_class', 'ClassNotFoundException/NoClassDefFoundError'
    if re.search(r'ExceptionInInitializer|ClassCastException', t) and not any(h in excname for h in SEMANTIC_HINTS[:6]):
        return 'binding_init', excname or 'init'
    if any(h in excname for h in SEMANTIC_HINTS):
        return 'semantic', excname
    if 'AssertionError' in t or 'ComparisonFailure' in t:
        return 'test_assertion', 'AssertionError'
    if excname.endswith('Exception'):
        return 'semantic?', excname
    return 'other', excname

def main():
    rows = []
    for f in FILES:
        d = json.load(open(f)); dep = d.get('updatedDependency', {})
        lib = dep.get('dependencyGroupID', '?') + ':' + dep.get('dependencyArtifactID', '?')
        t = read_log(d['breakingCommit'])
        kind, exc = classify(t)
        rows.append(dict(lib=lib, prev=dep.get('previousVersion'), new=dep.get('newVersion'),
                         utype=dep.get('versionUpdateType'), kind=kind, exc=exc,
                         sha=d['breakingCommit'], project=d.get('project')))
    # aggregate
    bykind = collections.Counter(r['kind'] for r in rows)
    print('=== BUMP TEST_FAILURE sweep:', len(rows), 'entries ===')
    for k, c in bykind.most_common(): print(f'  {c:3}  {k}')
    print('\n=== SEMANTIC candidates (production-forcing), by library ===')
    sem = [r for r in rows if r['kind'] in ('semantic', 'semantic?')]
    bylib = collections.defaultdict(list)
    for r in sem: bylib[r['lib']].append(r)
    for lib, rs in sorted(bylib.items(), key=lambda x: -len(x[1])):
        excs = collections.Counter(r['exc'] for r in rs)
        vers = sorted(set(f"{r['prev']}->{r['new']}" for r in rs))
        print(f"  {len(rs):2}  {lib}")
        print(f"        exc={dict(excs)}")
        print(f"        {', '.join(vers[:4])}")
    return rows, sem

if __name__ == '__main__':
    main()
