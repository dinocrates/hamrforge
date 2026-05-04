#ifndef BYTE_H
#define BYTE_H

#include <string>

class Byte {
public:
    Byte();
    Byte(int value);
    Byte(int bits[]);

    void setValue(int value);
    int at(int index);
    std::string toString();
    int toInt() const;

    Byte add(int value);
    Byte sub(int value);
    Byte mul(int value);
    Byte div(int value);

private:
    int bits[8];
    int bitsToInt() const;
};

#endif
