# Our numbers — v2 (additive body-floor + production; expect iteration)

> `docs/scratch/gen_our_numbers_v2.js`. **Grounded constants:** BV=2.2/HP · ATK=2/pt · R=4/3≈1.33 · THREAT=0.1/atk · P=perpetuity=1/(1−1/R)=4.
> Resources (WILL): gold 1 · green 1.33 (Conduit) · blue 1.67 (Blastforge) · red 1 (Animus) — **producer-derived** = gold-cost/(output × 1/(R−1)=3). energy 0.3 = **hedged** (Engineer's body shares its 2g cost; body-adjusted ~0.1, naive 0.667; real value board-dependent).
> **value = block_floor + production.** block_floor = HP·BV (PERMANENT; lifespan==1→0). net = attack·ATK − abilityCost − **abilitySac PRODUCTION** (Odin→Treant, Plasmafier→Drone; body excluded — the sacced unit isn't a prompt defender, ~10-turn soak ≈ 0).
> production: **auto** = net·P (no tap/penalty) · **click** = net·(P−1)+THREAT·atk (taps → forgoes the one death-eve soak attack; threat residual) ·
> **charge** = net·geom(ch) (preserved STOCK → no penalty) · **doomed** = net·geom(life−1)+THREAT·atk · **economy** = resource·{auto P / click P−1}.
> **block**/**atk** columns sum to **OURS**. Charge units at FULL charge (per-charge breakdown + convergence below).
> **New mechanics (tunable):** self-sac = max(block,burst)+opt (atk-burst 1 / token-burst 0.5) · token-spawn = production stream of created tokens (own = +ours(token), discounted by build-time; opponent = −block) · chill = +targetAmount·ATK·0.5 (flat, board-aware later) · drone-kill = +denied-drone PRODUCTION (Deadeye charge) · **undef −0.5/HP block** · **fragile −0.1 block**. Heal: effective soak HP = **current HP + one heal, capped at max** (buy-state in the table; matches the impl rule). Xaetron's HP-funded click ignored (→pure block).

## In-scope — sorted by OURS
| Unit | HP | type | flags | block | atk | rule | **OURS** | Q | Q/O | C++ | sDef | sTot |
|---|--:|---|---|--:|--:|---|--:|--:|--:|--:|--:|--:|
| Barrier | 1 | pure-block | life=1 | 0 | 0 | terminal→0 | **0** | 7 | — | 0 | 2.37 | 2.37 |
| Plexo Cell | 4 | pure-block | life=1 | 0 | 0 | terminal→0 | **0** | 14 | — | 0 | 9.47 | 9.47 |
| Husk | 1 | pure-block |  | 2.2 | 0 | block | **2.2** | 7 | 3.18 | 1.875 | 2.37 | 2.37 |
| Nitrocybe | 1 | self-sac | burst=2,opt=1 | 2.2 | 1 | max(block,burst)+opt | **3.2** | 9.83 | 3.07 | 2.43 | 1.21 | 1.91 |
| Engineer | 1 | economy-auto |  | 2.2 | 1.2 | block+econ | **3.4** | 7.3 | 2.15 | 1.875 | 1.69 | 1.69 |
| Forcefield | 2 | pure-block | fragile−0.1 | 4.3 | 0 | block | **4.3** | 13.75 | 3.2 | 3.75 | 4.73 | 4.73 |
| Doomed Drone | 1 | economy-click | life=4 | 2.2 | 2.31 | block+econ(doom) | **4.51** | 10.24 | 2.27 | 2.5 | 1.69 | 2.2 |
| Immolite | 1 | click-atk(1) | exhaust2 | 2.2 | 2.67 | block+click/2 | **4.87** | 15.36 | 3.15 | 3.9 |  | 4.08 |
| Drone | 1 | economy-click |  | 2.2 | 3 | block+econ | **5.2** | 11 | 2.12 | 3.5 | 1.69 | 2.5 |
| Photonic Fibroid | 2 | self-sac | burst=4,opt=1 | 4.4 | 1 | max(block,burst)+opt | **5.4** | 16 | 2.96 | 4.51 | ? | ? |
| Shiver Yeti | 2 | chill | chill2 | 4.4 | 2 | block+chill | **6.4** | 18 | 2.81 | 5.22 | 4.73 |  |
| Wall | 3 | pure-block |  | 6.6 | 0 | block | **6.6** | 21 | 3.18 | 5.75 | 7.1 | 7.1 |
| Corpus | 2 | charge-create(0A) | charge=2 | 4.4 | 2.8 | block+charge | **7.2** | 16.67 | 2.32 | 6.9 | 7.1 | 12.78 |
| Perforator | 2 | click-atk(1) |  | 4.4 | 3.1 | block+click | **7.5** | 15.36 | 2.05 | 3.9 | 3.38 | 4 |
| Rhino | 2 | charge-click-atk(1) | charge=2 | 4.4 | 3.5 | block+charge | **7.9** | 18.67 | 2.36 | 5.22 | 4.73 | 5.15 |
| Innervi Field | 3 | pure-block | life=3,heal→4,fragile−0.1 | 8.7 | 0 | block | **8.7** | 26.5 | 3.05 | 5.66 | ? | ? |
| Doomed Wall | 4 | pure-block | life=3 | 8.8 | 0 | block | **8.8** | 26 | 2.95 | 7.52 | 9.47 | 12.36 |
| Grimbotch | 2 | click-atk(1) | life=4 | 4.4 | 4.72 | block+doomed | **9.13** | 19.2 | 2.1 | 4.9 | 3.38 | 5.89 |
| Infusion Grid | 4 | self-sac | burst=7.8,opt=0.5 | 8.8 | 0.5 | max(block,burst)+opt | **9.3** | 28 | 3.01 | 6.5 | 6.76 | 10.99 |
| Electrovore | 2 | click-atk(1) |  | 4.4 | 5.2 | block+click | **9.6** | 19.2 | 2 | 4.9 | 3.38 | 7 |
| Protoplasm | 4 | self-sac | burst=8,opt=1,fragile−0.1 | 8.7 | 1 | max(block,burst)+opt | **9.7** | 35 | 3.61 | 9.91 | 9.47 | 12.39 |
| Polywall | 6 | pure-block | undef−3 | 10.2 | 0 | block | **10.2** | 35 | 3.43 | 10.18 | 14.2 | 14.2 |
| Ossified Drone | 2 | economy-auto+create |  | 4.4 | 6.3 | block+econ+create×1 | **10.7** | 17 | 1.59 | 6.4 |  |  |
| Aegis | 5 | pure-block | fragile−0.1 | 10.9 | 0 | block | **10.9** | 32.5 | 2.98 | 8.5 | 11.83 | 11.83 |
| Energy Matrix | 5 | pure-block |  | 11 | 0 | block | **11** | 34 | 3.09 | 9.73 | 11.83 | 23.66 |
| Scorchilla | 3 | click-atk(3) | exhaust3,fragile−0.1 | 6.5 | 4.68 | block+click/3 | **11.18** | 33.55 | 3 | 8.36 | 2.59 | 4.82 |
| Deadeye Operative | 2 | drone-kill(x3) | charge=3 | 4.4 | 6.94 | block+kill | **11.34** | 32 | 2.82 | 8 |  | 5.93 |
| Borehole Patroller | 2 | auto-atk(1) |  | 4.4 | 8 | block+auto | **12.4** | 23 | 1.85 | 8.7 |  | 9 |
| Feral Warden | 3 | click-atk(1) | fragile−0.1 | 6.5 | 6.1 | block+click | **12.6** | 22 | 1.75 | 6.28 | 7.1 | 9.03 |
| Steelsplitter | 3 | click-atk(1) |  | 6.6 | 6.1 | block+click | **12.7** | 26 | 2.05 | 7.5 | 5.07 | 7 |
| Odin | 3 | click-atk(4) | sac:Treant | 6.6 | 6.1 | block+click | **12.7** | 96 | 7.56 | 24.5 | 21.97 | 39.99 |
| Shredder | 4 | click-atk(1) | undef−2 | 6.8 | 6.1 | block+click | **12.9** | 25.6 | 1.98 | 6.5 | 6.76 | 7.33 |
| Urban Sentry | 3 | auto-atk(1) |  | 6.6 | 8 | block+auto | **14.6** | 28.01 | 1.92 | 7.7 | ? | ? |
| Cauterizer | 3 | click-atk(2) |  | 6.6 | 8.6 | block+click | **15.2** | 27 | 1.78 | 14.3 | 11.83 | 14 |
| Xeno Guardian | 4 | auto-atk(1) |  | 8.8 | 8 | block+auto | **16.8** | 37.12 | 2.21 | 9.2 | 8.76 | 17.99 |
| Sentinel | 3 | charge-create(1A) | charge=3,fragile−0.1 | 6.5 | 10.52 | block+charge | **17.02** | 32 | 1.88 | 8.1 | 6.76 | 9.6 |
| Xaetron | 4 | pure-block | heal→8,fragile−0.1 | 17.5 | 0 | block | **17.5** | 53 | 3.03 | 15.04 |  | 21.97 |
| Bombarder | 4 | charge-click-atk(3) | charge=2 | 8.8 | 10.5 | block+charge | **19.3** | 49 | 2.54 | 11.9 | ? | ? |
| Mega Drone | 4 | economy-click |  | 8.8 | 12 | block+econ | **20.8** | 57.6 | 2.77 | 15.5 | ? | ? |
| Lancetooth | 4 | click-atk(2) |  | 8.8 | 12.2 | block+click | **21** | 57.34 | 2.73 | 15.36 |  | 10 |
| Doomed Mech | 5 | click-atk(2) | life=5 | 11 | 11.14 | block+doomed | **22.14** | 47.36 | 2.14 | 12 | 8.45 | 12.85 |
| Chieftain | 7 | click-atk(2) | life=3,fragile−0.1 | 15.3 | 7.2 | block+doomed | **22.5** | 48.3 | 2.15 | 11.9 | 11.83 | 14.25 |
| Mahar Rectifier | 5 | click-atk(2) | heal→5,fragile−0.1 | 10.9 | 12.2 | block+click | **23.1** | 52.48 | 2.27 | 13.4 | 8.45 | 18.03 |
| Valkyrion | 4 | create(4A) |  | 8.8 | 14.5 | block+click | **23.3** | 66.56 | 2.86 | 16.8 |  | 22.58 |
| Plasmafier | 4 | click-atk(4) | sac:Drone,fragile−0.1 | 8.7 | 15.4 | block+click | **24.1** | 67.84 | 2.81 | 17.1 |  | 21.75 |
| Hannibull | 7 | auto(1)+click-atk(1) | undef−3.5 | 11.9 | 14.1 | block+auto+click | **26** | 48.64 | 1.87 | 12.4 | 13.83 | 14.4 |
| Redeemer | 4 | click-atk(3) |  | 8.8 | 18.3 | block+click | **27.1** | 68 | 2.51 | 12.7 |  | 13.76 |
| Defense Grid | 7 | auto-create | life=7 | 15.4 | 13.52 | block+auto | **28.92** | 80.64 | 2.79 | 20.5 | 11.83 | 32.15 |
| Centurion | 6 | auto-atk(2) |  | 13.2 | 16 | block+auto | **29.2** | 77 | 2.64 | 21.5 | 18.2 | 45.95 |
| Omega Splitter | 6 | click-atk(3) |  | 13.2 | 18.3 | block+click | **31.5** | 76.8 | 2.44 | 19.5 |  | 28.82 |
| Colossus | 8 | click-atk(3) | fragile−0.1 | 17.5 | 18.3 | block+click | **35.8** | 83.2 | 2.32 | 21 | 13.52 | 26.61 |
| Thunderhead | 11 | auto-atk(4) | life=3,undef−5.5 | 18.7 | 18.5 | block+auto | **37.2** | 89.6 | 2.41 | 22.5 |  |  |
| Arka Sodara | 7 | click-atk(4) |  | 15.4 | 24.4 | block+click | **39.8** | 76 | 1.91 | 23.58 | 16.57 | 48.23 |
| Tia Thurnax | 4 | charge-click-atk(7) | charge=3,fragile−0.1 | 8.7 | 32.38 | block+charge | **41.08** | 78 | 1.9 | 31.86 |  | 35.54 |

> **Q/O ratio: mean 2.61** (Q ≈ 2.61× OURS on average). **Lowest** (OURS rich vs Q): Ossified Drone 1.59, Feral Warden 1.75, Cauterizer 1.78, Borehole Patroller 1.85. **Highest** (OURS lean vs Q): Odin 7.56, Protoplasm 3.61, Polywall 3.43, Forcefield 3.2. Outliers from the mean are the rows to justify.

## Charge breakdown (ch0=spent .. full)
| Unit | ch0 | ch1 | ch2 | ch3 |
|---|---|---|---|---|
| Rhino | 4.4 | 6.4 | 7.9 |  |
| Tia Thurnax | 8.7 | 22.7 | 33.2 | 41.08 |
| Bombarder | 8.8 | 14.8 | 19.3 |  |

## Convergence check (charge ch→∞ vs the equivalent perpetual click)
Charges are a preserved STOCK (no death-eve penalty), so a charge unit at ch→∞ converges to **body + net·P** — which sits ~1 net-attack ABOVE the equivalent **perpetual click** (which pays the death-eve −1). That gap is the stock-vs-flow distinction (a held-back charge is never lost; a perpetual click forgoes its soak-turn attack).

| Unit | ch2 | ch5 | ch10 | ch50 | ch∞ (=body+net·P) | perp-click (=body+net·(P−1)+THREAT) |
|---|--:|--:|--:|--:|--:|--:|
| Rhino | 7.9 | 10.5 | 11.95 | 12.4 | 12.4 | 10.5 |
| Tia Thurnax | 33.2 | 51.41 | 61.55 | 64.7 | 64.8 | 50.9 |
| Bombarder | 19.3 | 27.1 | 31.45 | 32.8 | 32.8 | 26.9 |

_Electrovore (perpetual **paid** click-1, nets the energy) = **9.6**. A FREE 1A charge unit at ch∞ lands above it (free + stock: no cost, no death-eve penalty)._

## Still deferred
_None — every defaultBlocking type is now modeled (chill / drone-kill / self-sac / token-spawn / heal folded in). The board-aware layer (chill tax, drone-denial value, ability-usable gate) and the undef magnitude remain TUNABLE._
