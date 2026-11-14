# EXPERIMENT 7: FIBONACCI SERIES USING RECURSION

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


try:
    terms = int(input("Enter the number of terms: "))
    if terms < 0:
        print("Please enter a non-negative number.")
    else:
        print("Fibonacci Series:")
        for i in range(terms):
            print(fibonacci(i), end=" ")
        print()
except ValueError:
    print("Please enter a valid integer.")
