class Pointer:
    def __init__(self, value):
        self.value = value

# Create an instance of the class
ptr = Pointer(1)

# Assign the instance to both 'a' and 'b'
a = ptr
b = ptr

# Modify the attribute 'value' via 'a'
a.value = 10

# 'b' reflects the change because it references the same instance
print(b.value)  # Output: 10