# EXPERIMENT 6: PRIME NUMBER AND FACTORIAL PROGRAMS


def check_prime():
    number = int(input("Enter a number: "))
    if number <= 1:
        print(number, "is not a prime number.")
        return

    is_prime = True
    for i in range(2, int(number ** 0.5) + 1):
        if number % i == 0:
            is_prime = False
            break

    if is_prime:
        print(number, "is a prime number.")
    else:
        print(number, "is not a prime number.")


def calculate_factorial():
    number = int(input("Enter a non-negative number: "))
    if number < 0:
        print("Factorial is not defined for negative numbers.")
        return

    factorial = 1
    for i in range(1, number + 1):
        factorial *= i
    print("Factorial of", number, "is:", factorial)


while True:
    print("\n1. Check Prime Number")
    print("2. Calculate Factorial")
    print("3. Exit")
    choice = input("Enter your choice: ")
    try:
        if choice == "1":
            check_prime()
        elif choice == "2":
            calculate_factorial()
        elif choice == "3":
            break
        else:
            print("Invalid choice!")
    except ValueError:
        print("Please enter a valid integer.")
