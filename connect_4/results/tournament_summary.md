### Headline numbers

- 80 of 140 planned games played (60 skipped as exact replays), 0 aborted, 3.0 min on 12 cores. Tables below count distinct games only: 55 (25 played games were byte-identical replays of another).
- Depth vs depth (12 distinct games): deeper agent 3 wins, shallower agent 7 wins, 2 ties -> deeper agent wins 30% of decided games.
- Move order, all non-mirror games (each played both ways): first mover 28 wins, second mover 21 wins, 2 ties -> first mover wins 57%, second mover 43%.
- Mirror games, identical agent on both sides (4 distinct games): first mover 1 wins, second mover 1 wins, 2 ties.
- Depth vs random (39 distinct games): depth won 38, random won 1, 0 ties.

### Move order per matchup

| matchup | deeper moves 1st | deeper moves 2nd | verdict |
| --- | --- | --- | --- |
| ab2 vs ab3 | deeper | shallower | first mover won both |
| ab2 vs ab4 | shallower | shallower | shallower wins both orders |
| ab2 vs ab5 | deeper | tie | mixed |
| ab3 vs ab4 | tie | shallower | mixed |
| ab3 vs ab5 | deeper | shallower | first mover won both |
| ab4 vs ab5 | shallower | shallower | shallower wins both orders |

6 matchups: 2 x first mover won both, 2 x mixed, 2 x shallower wins both orders. With deterministic agents these are the only two distinct games a matchup has, so a verdict of 'first/second mover won both' means the result flipped purely on the move order -- depth cannot explain it.

### Depth vs depth (deeper agent's record, then split by move order)

| matchup | games | deeper W-L-D | deeper win% | deeper as 1st | deeper as 2nd | ties | aborted | shallower W-L-D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ab2 vs ab3 | 2 | 1-1-0 | 50% | 1/1 (100%) | 0/1 (0%) | 0 | 0 | 1-1-0 |
| ab2 vs ab4 | 2 | 0-2-0 | 0% | 0/1 (0%) | 0/1 (0%) | 0 | 0 | 2-0-0 |
| ab2 vs ab5 | 2 | 1-0-1 | 100% | 1/1 (100%) | 0/0 (-) | 1 | 0 | 0-1-1 |
| ab3 vs ab4 | 2 | 0-1-1 | 0% | 0/0 (-) | 0/1 (0%) | 1 | 0 | 1-0-1 |
| ab3 vs ab5 | 2 | 1-1-0 | 50% | 1/1 (100%) | 0/1 (0%) | 0 | 0 | 1-1-0 |
| ab4 vs ab5 | 2 | 0-2-0 | 0% | 0/1 (0%) | 0/1 (0%) | 0 | 0 | 2-0-0 |

### Each depth's record (mirror games excluded)

| agent | games | W-L-D | win% | as 1st | as 2nd | vs depth W-L-D | vs depth win% | vs random W-L-D | vs random win% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ab2 | 15 | 12-2-1 | 86% | 6/6 (100%) | 6/8 (75%) | 3-2-1 | 60% | 9-0-0 | 100% |
| ab3 | 16 | 12-3-1 | 80% | 8/8 (100%) | 4/7 (57%) | 3-2-1 | 60% | 9-1-0 | 90% |
| ab4 | 16 | 12-3-1 | 80% | 6/7 (86%) | 6/8 (75%) | 2-3-1 | 40% | 10-0-0 | 100% |
| ab5 | 16 | 12-3-1 | 80% | 7/8 (88%) | 5/7 (71%) | 2-3-1 | 40% | 10-0-0 | 100% |

### Depth difference vs result

| depth gap | games | deeper W-L-D | deeper win% | aborted |
| --- | --- | --- | --- | --- |
| +1 | 6 | 1-4-1 | 20% | 0 |
| +2 | 4 | 1-3-0 | 25% | 0 |
| +3 | 2 | 1-0-1 | 100% | 0 |

Pearson r(depth gap, deeper win%) = 0.89 over 3 gaps.

### Mirror games: identical agents, only the move order differs

| depth | games | 1st W - 2nd W - ties | first mover win% | p |
| --- | --- | --- | --- | --- |
| ab2 | 1 | 0-0-1 | - | 1.00 |
| ab3 | 1 | 0-1-0 | 0% | 1.00 |
| ab4 | 1 | 0-0-1 | - | 1.00 |
| ab5 | 1 | 1-0-0 | 100% | 1.00 |
| **all** | 4 | **1-1-2** | **50%** | **1.00** |

Each mirror game is depth d against itself (one side named `ab0d`), so strength cannot explain the result. p is a two-sided sign test on wins vs losses. A deterministic agent replays the same game under both move orders, so each row holds just one distinct game and this experiment has almost no power; it needs a stochastic agent (mcts) to become a real sample.

### Correlation of depth with win rate

| relationship | n depths | Pearson r |
| --- | --- | --- |
| depth vs win% (all non-mirror games) | 4 | -0.77 |
| depth vs win% (depth opponents only) | 4 | -0.89 |
| depth vs win% (vs random) | 4 | 0.26 |

n is the number of depths compared, so these r values describe this ladder only; treat them as a summary, not a significance test (with 4 depths a single flipped matchup moves r a lot).
