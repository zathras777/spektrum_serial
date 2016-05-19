Spektrum Serial
===============

This small script aims to read data from a serial port (or file) and parse it into channel
values from a Spektrum radio controller satellite receiver.

To run, attach your staellite receiver to a serial port (this is left as an exercise for the reader) and then point the script at it.

```
./spektrum_serial.py --serial /dev/ttyAMA0
Opened serial port...
Waiting for data to be available...
Reading data... CTRL + C to exit



Dropped:              0
Tansmitter data byte: 0x2d  101101
Bits per channel:     10
Frames Required:      2
Highest Channel:      14
  TX Number:          11

         0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15
      ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----
Rcvr   354    0  998    0 1007    0 1009    0  342    0    0  682    0  682  952    8
      ---- ---- ---- ---- ---- ---- ---- ----
Calc   354  998 1007 1009  342 1706 1706  952

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


Feel free to send me pull reqeusts for improvements and changes.

