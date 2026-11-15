"""
UNIT CONVERTER USING PYTHON
Python Mini Project

Submitted by: Gokul Nandan A
USN/Roll No.: 25BTRAD034
Class/Semester: AIDE A / 3rd sem
Subject: Python Programming
Academic Year: 2026-2027

Description:
A menu-driven unit converter for length, weight, temperature, and time.
"""

# -------------------- INPUT HELPER --------------------

def get_number(prompt):
    """Get a valid numeric value from the user."""
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Invalid input. Please enter a number.")


def get_choice(prompt, valid_choices):
    """Get a valid menu choice from the user."""
    while True:
        try:
            choice = int(input(prompt))
            if choice in valid_choices:
                return choice
            print("Invalid choice. Please select one of the listed options.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")


# -------------------- LENGTH CONVERTER --------------------

def length_converter():
    print("\n--- LENGTH CONVERTER ---")
    print("1. Meter to Kilometer")
    print("2. Kilometer to Meter")
    print("3. Centimeter to Meter")
    print("4. Meter to Centimeter")
    print("5. Back to Main Menu")

    choice = get_choice("Enter your choice: ", [1,  2, 3, 4, 5])

    if choice == 5:
        return

    value = get_number("Enter the value: ")

    if choice == 1:
        result = value / 1000
        print("Result:", result, "kilometers")
    elif choice == 2:
        result = value * 1000
        print("Result:", result, "meters")
    elif choice == 3:
        result = value / 100
        print("Result:", result, "meters")
    elif choice == 4:
        result = value * 100
        print("Result:", result, "centimeters")


# -------------------- WEIGHT CONVERTER --------------------

def weight_converter():
    print("\n--- WEIGHT CONVERTER ---")
    print("1. Kilogram to Gram")
    print("2. Gram to Kilogram")
    print("3. Kilogram to Pound")
    print("4. Pound to Kilogram")
    print("5. Back to Main Menu")

    choice = get_choice("Enter your choice: ", [1, 2, 3, 4, 5])

    if choice == 5:
        return

    value = get_number("Enter the value: ")

    if choice == 1:
        result = value * 1000
        print("Result:", result, "grams")
    elif choice == 2:
        result = value / 1000
        print("Result:", result, "kilograms")
    elif choice == 3:
        result = value * 2.20462
        print("Result:", result, "pounds")
    elif choice == 4:
        result = value / 2.20462
        print("Result:", result, "kilograms")


# -------------------- TEMPERATURE CONVERTER --------------------

def temperature_converter():
    print("\n--- TEMPERATURE CONVERTER ---")
    print("1. Celsius to Fahrenheit")
    print("2. Fahrenheit to Celsius")
    print("3. Back to Main Menu")

    choice = get_choice("Enter your choice: ", [1, 2, 3])

    if choice == 3:
        return

    value = get_number("Enter the temperature: ")

    if choice == 1:
        result = (value * 9 / 5) + 32
        print("Result:", result, "°F")
    elif choice == 2:
        result = (value - 32) * 5 / 9
        print("Result:", result, "°C")


# -------------------- TIME CONVERTER --------------------

def time_converter():
    print("\n--- TIME CONVERTER ---")
    print("1. Hours to Minutes")
    print("2. Minutes to Hours")
    print("3. Minutes to Seconds")
    print("4. Seconds to Minutes")
    print("5. Back to Main Menu")

    choice = get_choice("Enter your choice: ", [1, 2, 3, 4, 5])

    if choice == 5:
        return

    value = get_number("Enter the value: ")

    if choice == 1:
        result = value * 60
        print("Result:", result, "minutes")
    elif choice == 2:
        result = value / 60
        print("Result:", result, "hours")
    elif choice == 3:
        result = value * 60
        print("Result:", result, "seconds")
    elif choice == 4:
        result = value / 60
        print("Result:", result, "minutes")


# -------------------- MAIN PROGRAM --------------------

def main():
    """Display the main menu and run the selected converter."""
    while True:
        print("\n================================")
        print("          UNIT CONVERTER")
        print("================================")
        print("1. Length")
        print("2. Weight")
        print("3. Temperature")
        print("4. Time")
        print("5. Exit")

        choice = get_choice("Enter your choice: ", [1, 2, 3, 4, 5])

        if choice == 1:
            length_converter()
        elif choice == 2:
            weight_converter()
        elif choice == 3:
            temperature_converter()
        elif choice == 4:
            time_converter()
        elif choice == 5:
            print("Thank you for using Unit Converter!")
            break


if __name__ == "__main__":
    main()
