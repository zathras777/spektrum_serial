Spektrum Serial
===============

This small script aims to read data from a serial port (or file) and parse it into channel
values from a Spektrum radio controller.

To run, attach your staellite receiver to a serial port (this is left as an exercise for the reader) and then point the script at it.

```
./spektrum_serial.py --serial /dev/ttyAMA0
```

The channels will be shown in pseudo real time.

To record the data being collected, 

```
./spektrum_serial.py --serial /dev/ttyAMA0 --output spektrum.bin
```

To then replay the data

```
./spektrum_serial.py --file sepktrum.bin
```

That's all there is to it :-)


Issues
------
- Presently unless the frame starts at byte 0 of the stream them odd things happen and the data isn't usable.
- Due to some odd frame required values, it's forced to 2 for now

Feel free to send me pull reqeusts for improvements and changes.

