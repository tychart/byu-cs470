import random

import matplotlib.pyplot as plt
import numpy as np
from tabulate import tabulate


def choose_dice_num(army_size, attacker=True, top_attack_rolls=3, top_defend_rolls=2) -> int:
    if attacker:
        if army_size >= 4:
            return top_attack_rolls
        return max(army_size - 1, top_attack_rolls)
    else:
        if army_size >= 3:
            return top_defend_rolls
        return max(army_size, top_defend_rolls)


def roll_num_dice(num_dice) -> list[int]:
    rolls = []

    for _ in range(num_dice):
        rolls.append(random.randint(1, 6))

    rolls.sort(reverse=True)
    return rolls


def evaluate_battle(defend_rolls: list[int], attack_rolls: list[int]) -> tuple[int, int]:
    defend_losses = 0
    attack_losses = 0

    for defend_roll, attack_roll in zip(defend_rolls, attack_rolls, strict=False):
        if defend_roll >= attack_roll:
            attack_losses += 1
        else:
            defend_losses += 1

    return defend_losses, attack_losses


def simulate_battle(
    army_defend: int,
    army_attack: int,
    stages: int = 1000,
    top_attack_rolls: int = 3,
    top_defend_rolls: int = 2,
) -> list[int]:
    stage = 0
    total_defend_losses = 0
    total_attack_losses = 0
    defend_wins = 0
    attack_wins = 0

    while stage < stages:
        army_defend_dice = choose_dice_num(
            army_defend, attacker=False, top_defend_rolls=top_defend_rolls
        )
        army_attack_dice = choose_dice_num(
            army_attack, attacker=True, top_attack_rolls=top_attack_rolls
        )

        defend_rolls = roll_num_dice(army_defend_dice)
        attack_rolls = roll_num_dice(army_attack_dice)

        defend_losses, attack_losses = evaluate_battle(defend_rolls, attack_rolls)

        # print(f"Stage {stage + 1}:")
        # print(f"Defender rolls: {defend_rolls}")
        # print(f"Attacker rolls: {attack_rolls}")
        # print(f"Defender losses: {defend_losses} Defenders:
        #  {army_defend} -> {army_defend - defend_losses}")
        # print(f"Attacker losses: {attack_losses} Attackers:
        # {army_attack} -> {army_attack - attack_losses}")

        total_defend_losses += defend_losses
        total_attack_losses += attack_losses

        army_defend -= defend_losses
        army_attack -= attack_losses
        stage += 1

        if army_defend <= 0 or army_attack <= 1:
            if army_defend <= 0:
                # print("Attacker Wins!")
                attack_wins += 1
            else:
                # print("Defender Wins!")
                defend_wins += 1
            break

    return [total_defend_losses, total_attack_losses, defend_wins, attack_wins]


def simulate_battles(
    army_defend, army_attack, battles=1000, stages=1, top_attack_rolls=3, top_defend_rolls=2
):

    total_defend_losses = 0
    total_attack_losses = 0
    total_defend_wins = 0
    total_attack_wins = 0

    # print(f"\nSimulating {battles} battles with {army_defend}
    # defending armies and {army_attack} attacking armies:")

    for _ in range(battles):
        battle_result = simulate_battle(
            army_defend,
            army_attack,
            stages=stages,
            top_attack_rolls=top_attack_rolls,
            top_defend_rolls=top_defend_rolls,
        )
        total_defend_losses += battle_result[0]
        total_attack_losses += battle_result[1]
        total_defend_wins += battle_result[2]
        total_attack_wins += battle_result[3]

    avg_defend_losses = total_defend_losses / battles
    avg_attack_losses = total_attack_losses / battles
    avg_defend_wins = total_defend_wins / battles
    avg_attack_wins = total_attack_wins / battles

    # print(f"Average Defend Losses: {avg_defend_losses}")
    # print(f"Average Attack Losses: {avg_attack_losses}")

    return [avg_defend_losses, avg_attack_losses, avg_defend_wins, avg_attack_wins]


def part_a():
    battles = 10000
    results_normal = []
    results_limited = []

    for army_defend in range(1, 6):
        for army_attack in range(2, 6):
            simulation_avgs = simulate_battles(
                army_defend, army_attack, battles=battles, top_attack_rolls=3, top_defend_rolls=2
            )
            results_normal.append(
                [
                    len(results_normal) + 1,
                    army_defend,
                    army_attack,
                    simulation_avgs[0],
                    simulation_avgs[1],
                ]
            )

            for top_attack_rolls in range(1, 4):
                for top_defend_rolls in range(1, 3):
                    simulation_avgs = simulate_battles(
                        army_defend,
                        army_attack,
                        battles=battles,
                        top_attack_rolls=top_attack_rolls,
                        top_defend_rolls=top_defend_rolls,
                    )

                    results_limited.append(
                        [
                            len(results_limited) + 1,
                            army_defend,
                            army_attack,
                            simulation_avgs[0],
                            simulation_avgs[1],
                            top_defend_rolls,
                            top_attack_rolls,
                        ]
                    )

    print()
    print()
    print(f"Simulated {battles} battles with armies using the maximum amount of dice:\n")

    print(
        tabulate(
            results_normal,
            headers=[
                "Row",
                "Defending Armies",
                "Attacking Armies",
                "Avg Defend Losses",
                "Avg Attack Losses",
            ],
            tablefmt="pipe",
        )
    )

    print(f"\nSimulated {battles} battles with armies using a limited amount of dice:\n")

    print(
        tabulate(
            results_limited,
            headers=[
                "Row",
                "Defending Armies",
                "Attacking Armies",
                "Avg Defend Losses",
                "Avg Attack Losses",
                "Top Defend Rolls",
                "Top Attack Rolls",
            ],
            tablefmt="pipe",
        )
    )


def part_b():

    results = []
    army_defend = 5
    battles = 1000

    results.append([0, 5, 0, 1, 0])
    results.append([0, 5, 1, 1, 0])

    for army_attack in range(2, 21):
        simulation_avgs = simulate_battles(army_defend, army_attack, battles=battles, stages=1000)

        results.append(
            [
                len(results) + 3,
                army_defend,
                army_attack,
                simulation_avgs[2],
                simulation_avgs[3],
            ]
        )

    print(f"\nSimulated {battles} battles to the death:\n")

    print(
        tabulate(
            results,
            headers=[
                "Row",
                "Defending Armies",
                "Attacking Armies",
                "Avg Defend Wins",
                "Avg Attack Wins",
            ],
            tablefmt="pipe",
        )
    )

    results_np = np.array(results)

    np.set_printoptions(precision=3, suppress=True)
    print(results_np)

    subset = results_np[:, [4]].flatten()

    print(subset)

    plt.plot(subset)
    plt.xlabel("Attacker Army Number")
    plt.ylabel("Win Probibilty")
    plt.show()


# part_a()


part_b()
