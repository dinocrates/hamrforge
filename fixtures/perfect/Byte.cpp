#include "Byte.h"

Byte::Byte(int value) : value(value) {}

int Byte::toInt() const {
    return value;
}

Byte Byte::operator+(const Byte& other) const {
    return Byte(value + other.value);
}
