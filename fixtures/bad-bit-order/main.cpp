#include "Byte.h"

#include <iostream>

int main() {
    Byte bite;
    bite.setValue(99);

    for (int i = 0; i < 8; ++i) {
        std::cout << bite.at(i) << "\n";
    }

    std::cout << "Int:    " << bite.toInt() << "\n";
    std::cout << "String: " << bite.toString() << "\n";
    return 0;
}
