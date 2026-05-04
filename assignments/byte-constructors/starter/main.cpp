#include "Byte.h"

#include <iostream>

int main() {
    Byte bite(7);
    Byte b1 = bite.add(2);

    std::cout << "Int:    " << b1.toInt() << "\n";
    std::cout << "String: " << b1.toString() << "\n";

    return 0;
}
