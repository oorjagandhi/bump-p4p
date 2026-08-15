# ledger/ — the live count

`census.py` regenerates the census from the artifacts on disk:

```
python ledger/census.py > output/reports/CENSUS.md
```

**Quote the census, never a number from prose.** It is rebuilt from the files each time, so it
cannot drift. A number written into a document can, and does.

It distinguishes a **measured zero** from an **absent measurement**: `--` means the stage never
ran. That distinction is the entire point of the ledger — "we looked and found none" and "we
never looked" are different claims, and only the first supports a rarity argument.
