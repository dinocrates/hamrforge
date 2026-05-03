#include "Byte.h"

Byte::Byte() : bits{0, 0, 0, 0, 0, 0, 0, 0} {}

void Byte::setValue(int value) {
    for (int i = 0; i < 8; ++i) {
        bits[i] = (value >> (7 - i)) & 1;
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

int Byte::bitsToInt() const {
    int value = 0;
    for (int i = 0; i < 8; ++i) {
        value += bits[i] << i;
    }
    return value;
}
