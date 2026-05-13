from machine import I2C, Pin

i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=100000)

print("I2C scan...")
gevonden = i2c.scan()
if gevonden:
    for adres in gevonden:
        print("  0x{:02X}".format(adres))
else:
    print("  geen apparaten gevonden")
