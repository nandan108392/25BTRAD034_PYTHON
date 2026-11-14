# EXPERIMENT 14: BANK ACCOUNT SYSTEM USING OOP

class BankAccount:
    def __init__(self, name, balance):
        self.name = name
        self.__balance = balance

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            print("Amount deposited!")
        else:
            print("Invalid amount!")

    def withdraw(self, amount):
        if amount <= 0:
            print("Invalid amount!")
        elif amount > self.__balance:
            print("Insufficient balance!")
        else:
            self.__balance -= amount
            print("Withdrawal successful!")

    def display(self):
        print("Name:", self.name)
        print("Balance:", self.__balance)


a = BankAccount("Gokul", 5000)
a.display()
a.deposit(2000)
a.withdraw(1000)
a.display()
