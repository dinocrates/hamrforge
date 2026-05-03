#include "Byte.h"

Byte::Byte() : bits{0, 0, 0, 0, 0, 0, 0, 0} {}

void Byte::setValue(int value) {
    for (int i = 0; i < 8; ++i) {
        bits[i] = (value >> i) & 1;
    }
}

int Byte::at(int index) {
    return bits[index]
}

std::string Byte::toString() {
    return "";
}

int Byte::toInt() const {
    return bitsToInt();
}

int Byte::bitsToInt() const {
    return 0;
}
