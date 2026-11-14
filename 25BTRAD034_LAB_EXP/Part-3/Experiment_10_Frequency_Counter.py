# EXPERIMENT 10: FREQUENCY COUNTER USING DICTIONARIES
import re


def word_frequency():
    sentence = input("Enter a sentence: ").lower()
    words = re.findall(r"[a-zA-Z0-9']+", sentence)
    frequency = {}
    for word in words:
        frequency[word] = frequency.get(word, 0) + 1
    print("\n----- WORD FREQUENCY -----")
    for word, count in frequency.items():
        print(word, ":", count)


def list_frequency():
    elements = input("Enter list elements separated by commas: ")
    items = [item.strip().lower() for item in elements.split(",") if item.strip()]
    frequency = {}
    for item in items:
        frequency[item] = frequency.get(item, 0) + 1
    print("\n----- ELEMENT FREQUENCY -----")
    for item, count in frequency.items():
        print(item, ":", count)


while True:
    print("\n===== FREQUENCY COUNTER =====")
    print("1. Count Word Frequency")
    print("2. Count Element Frequency")
    print("3. Exit")
    choice = input("Enter your choice: ")
    if choice == "1":
        word_frequency()
    elif choice == "2":
        list_frequency()
    elif choice == "3":
        print("Thank you for using Frequency Counter!")
        break
    else:
        print("Invalid choice! Please try again.")
