# STUDENT GRADING SYSTEM USING DICTIONARIES

# Empty dictionary to store student names and marks
students = {}


# Function to add student details
def add_student():
    name = input("Enter Student Name: ").strip()

    if not name:
        print("Student name cannot be empty!")
        return

    if name in students:
        print("Student already exists!")
        return

    try:
        marks = float(input("Enter Student Marks (0-100): "))

        if marks < 0 or marks > 100:
            print("Invalid marks! Enter marks between 0 and 100.")
            return

        students[name] = marks
        print("Student details added successfully!")

    except ValueError:
        print("Invalid input! Please enter numeric marks.")


# Function to calculate grade
def calculate_grade(marks):
    if marks >= 90:
        return "O"
    elif marks >= 80:
        return "A+"
    elif marks >= 70:
        return "A"
    elif marks >= 60:
        return "B+"
    elif marks >= 50:
        return "B"
    elif marks >= 40:
        return "C"
    else:
        return "F"


# Function to display student results
def display_results():
    if not students:
        print("No student records available!")
        return

    print("\n========== STUDENT RESULTS ==========")

    for name, marks in students.items():
        grade = calculate_grade(marks)

        if marks >= 40:
            result = "PASS"
        else:
            result = "FAIL"

        print("-------------------------------------")
        print("Student Name:", name)
        print("Marks:", marks)
        print("Grade:", grade)
        print("Result:", result)

    print("-------------------------------------")


# Main menu
while True:
    print("\n===== STUDENT GRADING SYSTEM =====")
    print("1. Add Student")
    print("2. Display Student Results")
    print("3. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        add_student()
    elif choice == "2":
        display_results()
    elif choice == "3":
        print("Thank you for using Student Grading System!")
        break
    else:
        print("Invalid choice! Please try again.")
