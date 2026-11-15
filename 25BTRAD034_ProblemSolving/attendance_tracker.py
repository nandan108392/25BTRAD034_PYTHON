"""
STUDENT ATTENDANCE TRACKER
Python Mini Project - Unit 3: Problem Solving Component

Description:
A menu-driven application that stores student attendance records,
allows students to be added, records to be marked or updated, displays
attendance details, calculates attendance percentages, and identifies
students below the required attendance threshold.

Attendance codes:
    P = Present
    A = Absent
"""

# -------------------- DATA STORAGE --------------------

students = {
    "Rahul": ["P", "P", "A", "P"],
    "Priya": ["P", "P", "P", "P"],
    "Kiran": ["P", "A", "A", "P"],
    "Ananya": ["P", "P", "P", "A"],
    "Arjun": ["A", "P", "P", "P"]
}

ATTENDANCE_THRESHOLD = 75.0


# -------------------- HELPER FUNCTIONS --------------------

def get_student_name():
    """Read and return a non-empty student name."""
    return input("Enter student name: ").strip().title()


def calculate_percentage(records):
    """Calculate attendance percentage for one student."""
    if not records:
        return 0.0

    present_count = records.count("P")
    return (present_count / len(records)) * 100


# -------------------- PROJECT FUNCTIONS --------------------

def add_student():
    """Add a new student to the attendance dictionary."""
    name = get_student_name()

    if not name:
        print("Student name cannot be empty.")
    elif name in students:
        print("Student already exists.")
    else:
        students[name] = []
        print(f"{name} added successfully.")


def mark_attendance():
    """Add a Present or Absent record for a student."""
    name = get_student_name()

    if name not in students:
        print("Student not found. Please add the student first.")
        return

    status = input("Enter P for Present or A for Absent: ").strip().upper()

    if status not in ("P", "A"):
        print("Invalid status. Enter only P or A.")
        return

    students[name].append(status)
    print(f"Attendance marked as {status} for {name}.")


def update_attendance():
    """Update an existing attendance record using its class number."""
    name = get_student_name()

    if name not in students:
        print("Student not found.")
        return

    records = students[name]

    if not records:
        print("No attendance records available for this student.")
        return

    print("Current records:", records)

    try:
        class_number = int(input("Enter class number to update: "))
    except ValueError:
        print("Please enter a valid whole number.")
        return

    if not 1 <= class_number <= len(records):
        print("Invalid class number.")
        return

    new_status = input("Enter new status (P/A): ").strip().upper()

    if new_status not in ("P", "A"):
        print("Invalid status. Enter only P or A.")
        return

    records[class_number - 1] = new_status
    print("Attendance updated successfully.")


def display_attendance():
    """Display all student attendance records."""
    print("\n" + "=" * 55)
    print("                 ATTENDANCE RECORDS")
    print("=" * 55)

    if not students:
        print("No student records available.")
        return

    for name, records in students.items():
        print(f"{name:<15} : {records if records else 'No records yet'}")


def display_percentages():
    """Display the attendance percentage of every student."""
    print("\n" + "=" * 55)
    print("              ATTENDANCE PERCENTAGES")
    print("=" * 55)

    for name, records in students.items():
        percentage = calculate_percentage(records)
        print(f"{name:<15} : {percentage:.2f}%")


def identify_low_attendance():
    """List students whose attendance is below the threshold."""
    print("\n" + "=" * 55)
    print(f"       STUDENTS BELOW {ATTENDANCE_THRESHOLD:.0f}% ATTENDANCE")
    print("=" * 55)

    low_attendance_found = False

    for name, records in students.items():
        percentage = calculate_percentage(records)

        if records and percentage < ATTENDANCE_THRESHOLD:
            print(f"{name:<15} : {percentage:.2f}%")
            low_attendance_found = True

    if not low_attendance_found:
        print("No students are below the attendance threshold.")


# -------------------- MAIN MENU --------------------

def main():
    """Run the menu-driven attendance tracker."""
    while True:
        print("\n========== STUDENT ATTENDANCE TRACKER ==========")
        print("1. Add Student")
        print("2. Mark Attendance")
        print("3. Update Attendance")
        print("4. Display Attendance Records")
        print("5. Calculate Attendance Percentage")
        print("6. Identify Low Attendance Students")
        print("7. Exit")

        choice = input("Enter your choice (1-7): ").strip()

        if choice == "1":
            add_student()
        elif choice == "2":
            mark_attendance()
        elif choice == "3":
            update_attendance()
        elif choice == "4":
            display_attendance()
        elif choice == "5":
            display_percentages()
        elif choice == "6":
            identify_low_attendance()
        elif choice == "7":
            print("Thank you for using Student Attendance Tracker!")
            break
        else:
            print("Invalid choice. Please enter a number from 1 to 7.")


if __name__ == "__main__":
    main()
