# EXPERIMENT 8: CONTACT BOOK USING LISTS AND DICTIONARIES
contacts = []


def add_contact():
    name = input("Enter Name: ").strip()
    phone = input("Enter Phone Number: ").strip()
    email = input("Enter Email: ").strip()
    if not name or not phone:
        print("Name and phone number are required.")
        return
    if any(contact["phone"] == phone for contact in contacts):
        print("Contact with this phone number already exists!")
        return
    contacts.append({"name": name, "phone": phone, "email": email})
    print("Contact added successfully!")


def search_contact():
    name = input("Enter name to search: ").strip()
    found = [c for c in contacts if c["name"].lower() == name.lower()]
    if not found:
        print("Contact not found!")
    for contact in found:
        print("\nContact Found!")
        print("Name:", contact["name"])
        print("Phone:", contact["phone"])
        print("Email:", contact["email"])


def update_contact():
    name = input("Enter name to update: ").strip()
    for contact in contacts:
        if contact["name"].lower() == name.lower():
            new_name = input("New Name: ").strip()
            new_phone = input("New Phone: ").strip()
            new_email = input("New Email: ").strip()
            if any(other is not contact and other["phone"] == new_phone for other in contacts):
                print("Phone number already exists!")
                return
            contact.update({"name": new_name, "phone": new_phone, "email": new_email})
            print("Contact updated successfully!")
            return
    print("Contact not found!")


def delete_contact():
    name = input("Enter name to delete: ").strip()
    for contact in contacts:
        if contact["name"].lower() == name.lower():
            contacts.remove(contact)
            print("Contact deleted successfully!")
            return
    print("Contact not found!")


def display_contacts():
    if not contacts:
        print("Contact Book is empty!")
        return
    print("\n----- CONTACT LIST -----")
    for contact in contacts:
        print("-----------------------")
        print("Name:", contact["name"])
        print("Phone:", contact["phone"])
        print("Email:", contact["email"])


while True:
    print("\n===== CONTACT BOOK =====")
    print("1. Add Contact")
    print("2. Search Contact")
    print("3. Update Contact")
    print("4. Delete Contact")
    print("5. Display All Contacts")
    print("6. Exit")
    choice = input("Enter your choice: ")
    if choice == "1":
        add_contact()
    elif choice == "2":
        search_contact()
    elif choice == "3":
        update_contact()
    elif choice == "4":
        delete_contact()
    elif choice == "5":
        display_contacts()
    elif choice == "6":
        print("Thank you for using Contact Book!")
        break
    else:
        print("Invalid choice! Please try again.")
