# screen/ — is this candidate real?

Two independent reasons a perfectly good-looking candidate is not a case.

## screen_compile_break.py — does the client even reach the runtime change?

If the new version also **removed** the API the break lives behind, the client fails at `javac`
and never reaches the behaviour change. The adaptation is then fixing a signature break, and
the three-state differential can never show the signal, because state 2 fails at compile time.

Verdicts: `behavioural` / `compile_break` / `unknown`. Scope is constructor arity — so
`behavioural` means "no constructor-level compile break found", not "provably compiles".

**To screen a break before mining** (no client needed), skip the script and go straight to the
jars:

```
javap -cp lib-OLD.jar -public com.example.TheClass
javap -cp lib-NEW.jar -public com.example.TheClass
```

An arity present in the old and absent in the new is the whole test. It takes about a minute
and it is what ruled out snakeyaml 2.0, where every `Constructor` overload without a
`LoaderOptions` was removed.

## screen_trigger.py — does the client's own data reach the break?

A client whose YAML contains no global tag cannot experience a tag-restriction break, however
clean its bump and however real its adaptation. Same for a size limit no input ever exceeds.

A related trap worth naming: if the limit did not change but the client's **data grew** past a
limit that was always there, that is not a behavioural breaking change — however genuine the
resulting fix looks in the diff.
