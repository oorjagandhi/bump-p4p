# Top-library recent-major-release — bump + adaptation candidates

Discovery-first mining (`mine_major_bumps.py`) over the curated top / simple / non-Android libraries in `specs/top_maven_majors.json`. Every row has BOTH a **bump commit** (crosses the major boundary in the client's own build file) and an **adaptation commit** (same sha = bump-and-fix in one; or a later sha = separate fix).

Ranked: test-breaking upgrades first, then Maven-verifiable, then production, then same-commit. `dist` = commits between bump and adaptation (0 = same commit).

| # | library | repo | bump→ | dist | touches | signal | bump | adaptation |
|---|---|---|---|---|---|---|---|---|
