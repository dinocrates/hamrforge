#include "Byte.h"

#include <iostream>

int main() {
    int choice = 0;
    int left = 0;
    int right = 0;

    std::cin >> choice;
    if (choice == 1) {
        std::cin >> left >> right;
        Byte result = Byte(left) + Byte(right);
        std::cout << result.toInt() << "\n";
    }
    return 0;
}
