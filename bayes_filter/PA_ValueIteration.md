
### Code:
https://github.com/tychart/byu-cs470/tree/main/bayes_filter


## Value Iteration Parameters

| Parameter               | Value                                          | Constant / variable |
| ----------------------- | ---------------------------------------------- | ------------------- |
| R(open cell)            | -0.2                                           | `REWARD_EMPTY`      |
| R(stairwell)            | -10.0                                          | `REWARD_STAIRWAY`   |
| R(goal)                 | 10.0                                           | `REWARD_GOAL`       |
| Discount factor γ       | 1.0                                            | `gamma`             |
| Convergence threshold ε | 0.001                                          | `epsilon`           |
| Convergence test        | max over states of \|V_new(s) − V_old(s)\| ≤ ε | `maxDelta`          |
For the reward values, I mostly started with what we used in class, then as I rendered out the mazes, I was able to see the heat map for myself, and I tuned the parameters after that according to what looked like an even gradient between the goal and the stairways. My convergence threshold and my discount factor were chosen as an initial value and seemed to work, so I left them where they were. For further experimentation in the future, I could test to see if those factors matter in the overall outcome of the experiment.
### Approach 2 Parameters

| Parameter | Value | Variable |
|---|---|---|
| Belief confidence threshold | 0.2 | `maxBeliefThreshold` |
| Max homing moves | 20 | `homeingActionLimit` |
For justification for these parameters, see the section on my approach 2 algorithm.
## Observations:

One thing that I noticed when running the tests was that when I set sensor accuracy and movement accuracy to 1, then sometimes the robot would get stuck at the beginning because it didn't yet fully know where it was yet, so the way the math worked out, it chose a direction, and that happened to be into a wall. Since it was into a wall, and there was no randomness, nothing changed the next round and all the subsequent ones, and it kept trying to smash into the wall in an infinite loop. This was one of the things that I hope my approach 2 algorithm solves.

## Approach 2 Algorithm

The algorithm that I decided to use for Part 2 Approach 2 is a relatively simple addition onto the original approach 1 algorithm. I added on an initial homing sequence that will occur for up to the first `homingActionLimit` number of iterations to try to reduce the overall max belief across the `probs` matrix to over `maxBeliefThreshold` value. This way, the robot performs the homing sequence as the first moves that it makes in a round so that it can try to locate itself.

The actual algorithm is extremely simple, it just sees if the current max belief across the `probs` matrix is above a threshold, and if it isn't then it will either choose `SOUTH` or `EAST`, depending on what it last used so it doesn't just repeatedly crash into a wall. This homing sequence will be repeated until the current max belief is above the max belief threshold or the action limit moves run out, then it will just use the approach 1 algorithm after that.

```java
  int automaticAction2() {
    int outAction = -1;

    int homeingActionLimit = 20;
    double maxBeliefThreshold = 0.2;

    if (this.stepCount < homeingActionLimit && maxBelief() < maxBeliefThreshold) {
      if (this.lastAction == SOUTH) {
        outAction = EAST;
      } else {
        outAction = SOUTH;
      }
    } else {
      outAction = automaticAction();
    }
    this.stepCount++;

    this.lastAction = outAction;
    return outAction;
  }
```

A test that I performed with my custom approach 2 algorithm was turning off the homing limit and tuning the max belief threshold. I started out on 0.6, but I don't think any iterations got above that in 5 or even 15 moves. Even with a threshold of 0.3, the version that had 90% sensor and movement accuracy took about 30 moves to locate itself using my approach 2 algorithm. After further experimentation, I decided to put the max belief threshold at 0.2 with a homing action limit of 20 iterations.

Overall, according to the following experiments, it looks like my approach 2 algorithm seemed promising and did perform better than the basic approach 1 algorithm occasionally, especially in overall average moves per game, although this sometimes was because it just died faster, this lead to overall less useless going back and forth. It both took more risks and thus won and lost faster. I noticed this behavior as well in my individual testing when I manually tested myself and compared that against the algorithms in general. I found that the approach 1 algorithm often would get stuck in between walls and stairways, and just go back and forth for dozens of iterations before finally getting to the end or falling into a stairway.


| Config                                                 | Runs | win         | loss        | moves  | moves (win) | moves (no win) | Avg s | Failed |
| :----------------------------------------------------- | :--- | :---------- | :---------- | :----- | :---------- | :------------- | :---- | :----- |
| -w mundo_maze -u -m 0.99 -s 0.99 -a -d 0 --approach 1  | 50   | 50 (100.0%) | 0 (0.0%)    | 25.46  | 25.46       | -              | 1.40  | 0      |
| -w mundo_maze -u -m 0.99 -s 0.99 -a -d 0 --approach 2  | 50   | 50 (100.0%) | 0 (0.0%)    | 27.66  | 27.66       | -              | 1.46  | 0      |
| -w mundo_15_15 -u -m 0.99 -s 0.99 -a -d 0 --approach 1 | 50   | 38 (76.0%)  | 12 (24.0%)  | 479.76 | 463.11      | 532.50         | 1.50  | 0      |
| -w mundo_15_15 -u -m 0.99 -s 0.99 -a -d 0 --approach 2 | 50   | 47 (94.0%)  | 3 (6.0%)    | 52.10  | 55.28       | 2.33           | 1.40  | 0      |
| -w mundo_15_15 -u -m 0.90 -s 0.90 -a -d 0 --approach 1 | 50   | 31 (62.0%)  | 19 (38.0%)  | 77.30  | 89.65       | 57.16          | 1.40  | 0      |
| -w mundo_15_15 -u -m 0.90 -s 0.90 -a -d 0 --approach 2 | 50   | 21 (42.0%)  | 29 (58.0%)  | 53.78  | 86.67       | 29.97          | 1.70  | 0      |
| -w mundo_15_15 -u -m 0.50 -s 0.50 -a -d 0 --approach 1 | 50   | 0 (0.0%)    | 50 (100.0%) | 45.96  | -           | 45.96          | 2.56  | 0      |
| -w mundo_15_15 -u -m 0.50 -s 0.50 -a -d 0 --approach 2 | 50   | 0 (0.0%)    | 50 (100.0%) | 21.44  | -           | 21.44          | 2.59  | 0      |

When I tested myself manually, I followed my own standard method of solving the algorithm, and I think the difference was that I was able to better approximate where the robot was after moving back and forth a couple of times, then try to plot out the safest route to the end being able to look from above. I didn't always get a smaller number of moves, but I almost never got stuck going back and forth in an endless loop like some of the algorithm based runs did. One thing that the the algorithm did that I didn't do was always give 100% effort on every run. On some of the runs, I was board, and just button mashed for a couple of iterations, even holding down a key at times to better try to locate myself, which often lead to wasting iterations or even falling off a stairwell.

## List of Flags in the Video
```
./run.sh -w mundo_maze -u --move-prob 0.99 --sensor-prob 0.99 -a -d 50 --approach 1
```
```
./run.sh -w mundo_maze -u --move-prob 0.99 --sensor-prob 0.99 -a -d 50 --approach 2
```
```
./run.sh -w mundo_15_15 -u --move-prob 0.99 --sensor-prob 0.99 -a -d 50 --approach 1
```
```
./run.sh -w mundo_15_15 -u --move-prob 0.99 --sensor-prob 0.99 -a -d 50 --approach 2
```
```
./run.sh -w mundo_15_15 -u --move-prob 0.90 --sensor-prob 0.90 -a -d 50 --approach 1
```
```
./run.sh -w mundo_15_15 -u --move-prob 0.90 --sensor-prob 0.90 -a -d 50 --approach 2
```