# EXPERIMENT 4: SIMPLE CALCULATOR AND AREA CALCULATION PROGRAMS
import math


def calculator():
    a = float(input("Enter first number: "))
    b = float(input("Enter second number: "))
    print("Addition:", a + b)
    print("Subtraction:", a - b)
    print("Multiplication:", a * b)
    if b == 0:
        print("Division: Cannot divide by zero")
    else:
        print("Division:", a / b)


def circle_area():
    radius = float(input("Enter radius: "))
    print("Area of circle:", math.pi * radius * radius)


def rectangle_area():
    length = float(input("Enter length: "))
    breadth = float(input("Enter breadth: "))
    print("Area of rectangle:", length * breadth)


def triangle_area():
    base = float(input("Enter base: "))
    height = float(input("Enter height: "))
    print("Area of triangle:", 0.5 * base * height)


while True:
    print("\n===== CALCULATOR AND AREA MENU =====")
    print("1. Simple Calculator")
    print("2. Area of Circle")
    print("3. Area of Rectangle")
    print("4. Area of Triangle")
    print("5. Exit")
    choice = input("Enter your choice: ")

    try:
        if choice == "1":
            calculator()
        elif choice == "2":
            circle_area()
        elif choice == "3":
            rectangle_area()
        elif choice == "4":
            triangle_area()
        elif choice == "5":
            print("Program ended.")
            break
        else:
            print("Invalid choice. Please try again.")
    except ValueError:
        print("Please enter valid numeric values.")
