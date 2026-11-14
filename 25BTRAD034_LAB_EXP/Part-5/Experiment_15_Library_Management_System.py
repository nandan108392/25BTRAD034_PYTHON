# EXPERIMENT 15: LIBRARY MANAGEMENT SYSTEM USING OOP

class Book:
    def __init__(self, name):
        self.name = name
        self.available = True

    def issue(self):
        if self.available:
            self.available = False
            print("Book issued successfully!")
        else:
            print("Book not available!")

    def return_book(self):
        if not self.available:
            self.available = True
            print("Book returned successfully!")
        else:
            print("Book was not issued!")

    def display(self):
        status = "Available" if self.available else "Issued"
        print("Book:", self.name)
        print("Status:", status)


book = Book("Python Programming")
book.display()
book.issue()
book.display()
book.return_book()
book.display()
