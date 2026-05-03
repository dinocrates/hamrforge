# Unit 02 - Byte Class Construction

## Objective

Build a C++ `Byte` class that stores and reports the eight bits of a byte. The class should show that you understand constructors, encapsulation, private helper functions, and basic bitwise operations.

## Required Files

- `Byte.h`
- `Byte.cpp`
- `main.cpp`

## Class Requirements

Create a class named `Byte`.

The private section should include:

- `int bits[8]`
- `int bitsToInt() const`

The public section should include:

- `Byte()`
- `void setValue(int value)`
- `int at(int index)`
- `std::string toString()`
- `int toInt() const`

## Behavior

`setValue` should use bitwise operations to store each bit of an integer value in the `bits` array.

`at(index)` should return the bit at the requested index.

`toString()` should return the binary string representation of the byte in normal display order. For example, value `99` should display as `01100011`.

`toInt()` should return the integer value represented by the bits.

## Example

For value `99`, the expected bit values from `at(0)` through `at(7)` are:

```text
1
1
0
0
0
1
1
0
```

The expected integer and string output are:

```text
Int:    99
String: 01100011
```

## Testing

Use `main.cpp` to test your class thoroughly, including boundary values such as `0` and `255`.
