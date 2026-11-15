"""
OTP GENERATOR USING PYTHON
Python Mini Project - Unit 2

Submitted by: Gokul Nandan A
USN/Roll No.: 25BTRAD034
Class/Semester: AIDE A / 3rd Semester
Subject: Python Programming
Academic Year: 2026-2027

Description:
This program generates a six-digit One-Time Password (OTP) and checks
whether the OTP entered by the user matches the generated OTP.

Note:
This is an educational demonstration. The OTP is displayed on screen
for testing and is not sent through SMS or email.
"""

import random


def generate_otp():
    """Generate and return a six-digit OTP as a string."""
    otp = ""

    for _ in range(6):
        digit = random.randint(0, 9)
        otp += str(digit)

    return otp


def verify_otp(generated_otp, entered_otp):
    """Return True if the entered OTP matches the generated OTP."""
    return entered_otp == generated_otp


def main():
    """Run the OTP generation and verification program."""
    print("=" * 32)
    print("          OTP GENERATOR")
    print("=" * 32)

    otp = generate_otp()

    # Displaying the OTP is only for this educational demonstration.
    print("Your OTP is:", otp)

    entered_otp = input("Enter the OTP: ").strip()

    if not entered_otp.isdigit() or len(entered_otp) != 6:
        print("Invalid OTP! Please enter exactly 6 digits.")
    elif verify_otp(otp, entered_otp):
        print("OTP verified successfully!")
    else:
        print("Invalid OTP!")


if __name__ == "__main__":
    main()
