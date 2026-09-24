import random
import time

time_start = time.time()
games = 1_000_000_0

flips_arr = []

for i in range(games):
    flips_until_tails = 0
    while True:
        flip = random.randint(0, 1)
        if flip == 1: # Tails
            break
        flips_until_tails += 1
    flips_arr.append(flips_until_tails)

seconds_proccessing = time.time() - time_start

# print(f"Flips until tails arr: {flips_arr}")
print(f"Total games: {games:,.0f}")
print(f"Max flips until tails: {max(flips_arr)} = ${2**max(flips_arr):,.2f}")
print(f"Min flips until tails: {min(flips_arr)} = ${2**min(flips_arr):,.2f}")
print(f"Average flips until tails: {sum(flips_arr) / len(flips_arr)} = ${2**(sum(flips_arr) / len(flips_arr)):,.2f}")
print(f"{games / seconds_proccessing:,.0f} games/s in {seconds_proccessing:.2f} seconds")
