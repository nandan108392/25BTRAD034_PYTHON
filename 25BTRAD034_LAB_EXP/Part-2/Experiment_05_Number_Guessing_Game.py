# EXPERIMENT 5: NUMBER GUESSING GAME
import random

number = random.randint(1, 100)
attempts = 0

print("================================")
print("       NUMBER GUESSING GAME")
print("================================")
print("Guess a number between 1 and 100")

while True:
    try:
        guess = int(input("Enter your guess: "))
    except ValueError:
        print("Please enter a whole number.")
        continue

    if not 1 <= guess <= 100:
        print("Enter a number between 1 and 100.")
        continue

    attempts += 1
    if guess < number:
        print("Too low! Try again.")
    elif guess > number:
        print("Too high! Try again.")
    else:
        print("Congratulations!")
        print("You guessed the correct number.")
        print("Number of attempts:", attempts)
        break
