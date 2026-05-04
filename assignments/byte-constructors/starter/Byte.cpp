#include "Byte.h"

Byte::Byte() : Byte(0) {}

Byte::Byte(int value) : bits{0, 0, 0, 0, 0, 0, 0, 0} {
    setValue(value);
}

Byte::Byte(int inputBits[]) : bits{0, 0, 0, 0, 0, 0, 0, 0} {
    bool valid = true;
    for (int i = 0; i < 8; ++i) {
        if (inputBits[i] != 0 && inputBits[i] != 1) {
            valid = false;
        }
    }
    if (!valid) {
        return;
    }
    for (int i = 0; i < 8; ++i) {
        bits[i] = inputBits[i];
    }
}

void Byte::setValue(int value) {
    for (int i = 0; i < 8; ++i) {
        bits[i] = (value >> i) & 1;
    }
}

int Byte::at(int index) {
    if (index < 0 || index >= 8) {
        return 0;
    }
    return bits[index];
}

std::string Byte::toString() {
    std::string result;
    for (int i = 7; i >= 0; --i) {
        result += bits[i] ? '1' : '0';
    }
    return result;
}

int Byte::toInt() const {
    return bitsToInt();
}

Byte Byte::add(int value) {
    return Byte(toInt() + value);
}

Byte Byte::sub(int value) {
    return Byte(toInt() - value);
}

Byte Byte::mul(int value) {
    return Byte(toInt() * value);
}

Byte Byte::div(int value) {
    return Byte(toInt() / value);
}

int Byte::bitsToInt() const {
    int value = 0;
    for (int i = 0; i < 8; ++i) {
        value += bits[i] << i;
    }
    return value;
}
