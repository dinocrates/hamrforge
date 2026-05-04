# Unit 03 - Byte Overloaded Constructors

## Objective

Extend your `Byte` class from Unit 02 by adding overloaded constructors and arithmetic helper functions. This assignment continues the same `Byte` class that we will use through the semester.

## Required Files

- `Byte.h`
- `Byte.cpp`
- `main.cpp`

## Constructors

Add these constructors to your `Byte` class:

- `Byte()` - default constructor that sets all bits to `0`. Delegate this constructor so it calls `Byte(int val)`.
- `Byte(int val)` - sets the bits correctly for the integer value.
- `Byte(int ar[])` - stores values from the array into the bits. If any array value is not `0` or `1`, set all bits to `0`.

## Functionality

Add these public functions:

- `Byte add(int value)`
- `Byte sub(int value)`
- `Byte mul(int value)`
- `Byte div(int value)`

Each function should return a `Byte` containing the result.

## Example

```cpp
int main()
{
    Byte bite(7);

    Byte b1 = bite.add(2);

    cout << "Int:    " << b1.toInt() << endl;
    cout << "String: " << b1.toString() << endl;

    return 0;
}
```

Expected output:

```text
Int:    9
String: 00001001
```

## Required Header Comments

You must have your name, ID, date, assignment number, and a brief description of what the file is in comments at the top of each page. In the real course rubric, missing this information may result in points being deducted.

## Notes

Avoid code duplication. If you have already written functions that help with the answer, use them.
