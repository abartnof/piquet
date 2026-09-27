# `settle` records

One line per mirrored pair, written by `target/release/settle DEALS WORLDS
--out FILE`; the matching `.txt` is what the run printed. Pair any two with
`settle --compare A B`, and replay one pair with `settle --show FILE STANDING
DEAL`. Each line carries its pack in full, so a record stays usable after the
code has moved on — but the *play* it records is that of the build named here.

| file | build | command | wall time |
|---|---|---|---|
| `w30.tsv` | `0f899e1` (live pique, `79cfc82`) | `settle 120 30` | 21 min, sharing two vCPUs |
| `w90.tsv` | `0f899e1` | `settle 120 90` | 29 min, sharing two vCPUs |
| `w30-prior.tsv` | `148295f` (both agents with `prior::RUNG4`) | `settle 120 30 --prior` | 15 CPU-min, niced, sharing |

`w30-prior` against `w30`: settling +10.53 ± 3.16 a deal against −1.30;
paired, +11.8 ± 4.5 (`settle --compare`).

`w30` reproduces the recorded 266–33–421, −1.30 ± 3.55 exactly.
