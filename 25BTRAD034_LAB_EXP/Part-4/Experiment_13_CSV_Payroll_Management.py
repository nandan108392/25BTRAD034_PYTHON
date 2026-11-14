# EXPERIMENT 13: CSV PAYROLL MANAGEMENT
import csv
from pathlib import Path

employee_file = Path(__file__).with_name("employees.csv")

try:
    total = 0.0
    with employee_file.open("r", newline="", encoding="utf-8") as file:
        for employee in csv.DictReader(file):
            basic = float(employee["Basic"])
            hra = basic * 0.20
            da = basic * 0.10
            gross = basic + hra + da
            deduction = gross * 0.10
            net = gross - deduction
            total += net
            print("\nEmployee:", employee["Name"])
            print("Gross Salary:", gross)
            print("Deduction:", deduction)
            print("Net Salary:", net)
    print("\nTotal Salary:", total)
except FileNotFoundError:
    print("Employee file not found! Place employees.csv in this folder.")
except (ValueError, KeyError):
    print("Invalid salary data! Check the CSV columns and salary values.")
