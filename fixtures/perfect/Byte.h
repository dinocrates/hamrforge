#ifndef BYTE_H
#define BYTE_H

class Byte {
public:
    explicit Byte(int value);
    int toInt() const;
    Byte operator+(const Byte& other) const;

private:
    int value;
};

#endif
