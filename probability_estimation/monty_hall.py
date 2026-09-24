import random

games = 100000000

def next_door(door_num):
    if door_num == 2:
        return 0
    return door_num + 1

def play_game(switch):
    doors = ['c', 'g', 'g']

    random.shuffle(doors)

    choice = random.randint(0, 2)

    reveal = random.randint(0, 2)

    if doors[reveal] == 'c':
        reveal = next_door(reveal)
    if reveal == choice:
        reveal = next_door(reveal)
        if doors[reveal] == 'c':
            reveal = next_door(reveal)

    if switch:
        choice = next_door(choice)
        if choice == reveal:
            choice = next_door(choice)

    if doors[choice] == 'c':
        # print("You win!")
        return 1
    else:
        # print("You lose!")
        return 0

switch_wins = 0
stay_wins = 0

for _ in range(games):
    switch_wins += play_game(switch=True)

print(f"Switch wins: {switch_wins} out of {games} games ({switch_wins / games * 100:.2f}%)")


for _ in range(games):
    stay_wins += play_game(switch=False)

print(f"Stay wins: {stay_wins} out of {games} games ({stay_wins / games * 100:.2f}%)")