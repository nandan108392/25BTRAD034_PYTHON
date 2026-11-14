# EXPERIMENT 16: DICE SIMULATOR USING RANDOM MODULE
import random

try:
    rolls = int(input("Enter number of rolls: "))
    if rolls < 0:
        print("Please enter zero or a positive number of rolls.")
    else:
        count = [0] * 6
        for i in range(rolls):
            dice = random.randint(1, 6)
            print("Roll", i + 1, ":", dice)
            count[dice - 1] += 1

        print("\nFrequency:")
        for i in range(6):
            print(i + 1, ":", count[i])
except ValueError:
    print("Please enter a valid whole number.")
