#include "Byte.h"

#include <iostream>
#include <string>

int main() {
    Byte b;
    b.setValue(99);
    std::cout << std::string(90000, 'x') << "\n";
    return 0;
}
