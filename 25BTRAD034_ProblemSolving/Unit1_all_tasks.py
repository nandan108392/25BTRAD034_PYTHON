# Python Programming - Unit 1 Assignment
# Name: Gokul nandan A | USN: 25BTRAD034
# Department: B.Tech CSE (AI & Data Engineering) | College: Jain University

# ============================================================
# Task 1: Print Name, Department, College (each on a separate line)
print("kumar")
print("Computer Science Engineering (AI & Data Engineering)")
print("Jain University")

# ============================================================
# Task 2: Print a Pattern
print("*******")
print("*******")
print("*******")

# ============================================================
# Task 3: Print using a single print() statement
print("Python is Easy")

# ============================================================
# Task 4: Print the Number Triangle Pattern
for i in range(1, 6):
    line = ""
    for j in range(1, i + 1):
        line += str(j)
    print(line)

# ============================================================
# Task 5: Use the newline escape to print Computer / Science / Engineering
print("Computer\nScience\nEngineering")

# ============================================================
# Task 6: Use the tab escape to print Name, Age, City
print("Name\tAge\tCity")

# ============================================================
# Task 7: Program with a Single-Line Comment
# This program prints a simple welcome message
print("Welcome to Python Programming")

# ============================================================
# Task 8: Program with Multi-line Comments
'''
This is a multi-line comment. This program demonstrates how to write
multi-line comments in Python.
'''
print("Python Basics Program")

# ============================================================
# Task 9: Program with Three Comments and Three Print Statements
# Comment 1: This prints the student's name
print("ADIII")
# Comment 2: This prints the department
print("Computer Science Engineering")
# Comment 3: This prints the college
print("Jain University")

# ============================================================
# Task 10: Create a Variable 'name' and Print It
name = "kumar"
print(name)

# ============================================================
# Task 11: Store 10, 20, 30 in Three Variables and Print Them
a = 10
b = 20
c = 30
print(a)
print(b)
print(c)

# ============================================================
# Task 12: Convert String 100 into Integer
num_str = "100"
num_int = int(num_str)
print(num_int)
print(type(num_int))

# ============================================================
# Task 13: Convert Integer 25 into Float
num_int = 25
num_float = float(num_int)
print(num_float)
print(type(num_float))

# ============================================================
# Task 14: Accept Age using input() and Display It
age = input("Enter your age: ")
age = int(age)
print("Age:", age)

# ============================================================
# Task 15: Accept Two Numbers and Display Their Sum
num1 = int(input("Enter first number: "))
num2 = int(input("Enter second number: "))
sum_result = num1 + num2
print("Sum:", sum_result)

# ============================================================
# Task 16: Accept Name, Age, CGPA and Display Using f-string
name = input("Enter your name: ")
age = int(input("Enter your age: "))
cgpa = float(input("Enter your CGPA: "))
print(f"My name is {name}. I am {age} years old and my CGPA is {cgpa}.")

# ============================================================
# Task 17: Convert Celsius to Fahrenheit
celsius = float(input("Enter temperature in Celsius: "))
fahrenheit = (celsius * 9 / 5) + 32
print(f"Temperature in Fahrenheit: {fahrenheit:.2f}")

# ============================================================
# Task 18: Check Even or Odd using % Operator
num = int(input("Enter number: "))
if num % 2 == 0:
    print(f"{num} is Even")
else:
    print(f"{num} is Odd")
