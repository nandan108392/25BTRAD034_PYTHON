# EXPERIMENT 12: STUDENT DATA MANAGER USING CSV FILE HANDLING
import csv
from pathlib import Path

DATA_FILE = Path(__file__).with_name("students.csv")
FIELDS = ["USN", "Name", "Marks"]


def read_records():
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_records(records):
    with DATA_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)


def display():
    records = read_records()
    if not records:
        print("No records found!")
        return
    for record in records:
        print(record)


def add():
    usn = input("Enter USN: ").strip()
    name = input("Enter Name: ").strip()
    marks_text = input("Enter Marks: ").strip()
    try:
        marks = float(marks_text)
        if not 0 <= marks <= 100:
            raise ValueError
    except ValueError:
        print("Invalid marks! Enter a value from 0 to 100.")
        return
    records = read_records()
    if any(record["USN"] == usn for record in records):
        print("Student already exists!")
        return
    records.append({"USN": usn, "Name": name, "Marks": str(marks)})
    write_records(records)
    print("Record added!")


def search():
    usn = input("Enter USN: ").strip()
    for record in read_records():
        if record["USN"] == usn:
            print("Student Found:", record)
            return
    print("Student not found!")


def update():
    usn = input("Enter USN: ").strip()
    records = read_records()
    for record in records:
        if record["USN"] == usn:
            new_name = input("Enter new name: ").strip()
            marks_text = input("Enter new marks: ").strip()
            try:
                marks = float(marks_text)
                if not 0 <= marks <= 100:
                    raise ValueError
            except ValueError:
                print("Invalid marks!")
                return
            record["Name"] = new_name
            record["Marks"] = str(marks)
            write_records(records)
            print("Record updated!")
            return
    print("Student not found!")


while True:
    print("\n1. Add  2. Display  3. Search  4. Update  5. Exit")
    choice = input("Enter choice: ")
    if choice == "1":
        add()
    elif choice == "2":
        display()
    elif choice == "3":
        search()
    elif choice == "4":
        update()
    elif choice == "5":
        break
    else:
        print("Invalid choice!")
