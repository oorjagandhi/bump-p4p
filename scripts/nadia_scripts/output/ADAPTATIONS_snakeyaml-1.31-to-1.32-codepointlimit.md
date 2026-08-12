# Adaptations to `snakeyaml-1.31-to-1.32-codepointlimit`

Commits touching `setCodePointLimit`, classified by the VALUE they set. The library's own default is taken as 3,145,728.

**RAISE is the only verdict that can yield a case.** A knob left at the library's default behaves identically before and after for every input size, so it cannot produce a pass/fail/pass differential; LOWER is security hardening. Measured five for five on snakeyaml, the split follows what the project is: applications raise, libraries and plugins expose a knob.

0 distinct commit(s) after fork collapse; **0 worth reading**.

| verdict | value | repo | date | commit | forks |
|---|---:|---|---|---|---:|

## Worth reading

