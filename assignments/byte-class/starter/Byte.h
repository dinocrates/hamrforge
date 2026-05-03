#ifndef BYTE_H
#define BYTE_H

#include <string>

class Byte {
public:
    Byte();
    void setValue(int value);
    int at(int index);
    std::string toString();
    int toInt() const;

private:
    int bits[8];
    int bitsToInt() const;
};

#endif
