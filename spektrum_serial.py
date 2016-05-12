#!/usr/bin/python

import os
import sys
import struct
import serial
import argparse
from struct import pack
from time import time


class SpektrumFrame(object):
    def __init__(self, data):
        self.frames = 1
        self.dropped = data[0]
        self.tx_data = data[1]
        self.channel_data = data[2:]
        self.channel_values = {}
        self.highest_channel = 0

    def add_frame(self, frame):
        self.channel_data.extend(frame[2:])

    @property
    def channel_bits(self):
        return 10 if self.tx_data & 0x10 == 0 else 11

    @property
    def frames_required(self):
        return 2
        # This would appear to be what should give the correct value,
        # but it seems to fail too frequently!
        # return self.tx_data & 0x03

    @property
    def tx_number(self):
        return self.tx_data >> 2

    def upper_3(self):
        return (self.tx_data & 0xe0) >> 5

    def lower_2(self):
        return (self.tx_data & 0x0c) >> 2

    def decode_channels(self):
        for n in range(0, len(self.channel_data) - 1, 2):
            if self.channel_data[n] == 0xff:
                continue
            val = (self.channel_data[n] << 8) + self.channel_data[n + 1]
            f = self.channel_data[n] & 0x80 == 0x80
            if self.channel_bits == 11:
                chan = (self.channel_data[n] & 0x78) >> 3
                val &= 0x7ff
            else:
                chan = (self.channel_data[n] & 0x3c) >> 2
                val &= 0x3ff
            if chan > self.highest_channel:
                self.highest_channel = chan
            #print("f = {}, chan = {}, val = {}".format(f, chan, val))
            self.channel_values[chan] = val

    def is_complete(self):
        return len(self.channel_data) == self.frames_required * 14

    def summary(self):
        return """
Dropped:              {}
Tansmitter data byte: 0x{:02x}  {}
Bits per channel:     {}
Frames Required:      {}
Highest Channel:      {}
  TX Number:          {}
  Upper 3 buts        0x{:02x}
  Lower 2 bits        0x{:02x}""".format(self.dropped,
                                         self.tx_data,
                                         bin(self.tx_data)[2:],
                                         self.channel_bits,
                                         self.frames_required,
                                         self.highest_channel,
                                         self.tx_number,
                                         self.upper_3(),
                                         self.lower_2())

    def channel_value_string(self):
        chans = range(self.highest_channel + 1)
        title = "".join(["  {:2d} ".format(x) for x in chans])
        title += "\n" + "".join(["---- " for x in chans])
        title += "\n" + "".join(["{:4d} ".format(self.channel_values.get(x, 0)) for x in chans])
        return title


def read_bytes(inp, out=None):
    bytes = map(ord, inp.read(16))
    if out is not None and len(bytes) > 0:
        out.write(pack("{}B".format(len(bytes)), *bytes))
    return bytes if len(bytes) == 16 else None


def read_loop(inp, out=None, summary=False):
    total_frames = 0


    if hasattr(inp, 'inWaiting'):
        print("Waiting for data to be available...")
        try:
            while inp.inWaiting() == 0:
                pass
        except KeyboardInterrupt:
            return
        print("Reading data...\n")

    last = time()
    while True:
        try:
            if time() - last > 5 and total_frames > 0:
                print("Break in reception detected. Resetting frame counter.")
                total_frames = 0

            bytes = read_bytes(inp, out)
            if bytes is None:
                continue

            if bytes[1] & 0x03 == 0:
                print("Likely invalid frame detected.")
                continue

            if bytes[2] & 0x80 == 0x80:
                print("    probable second frame detected! [0x{:02X}]...".format(bytes[2]))
                continue

            sf = SpektrumFrame(bytes)
            for extra in range(1, sf.frames_required):
                bytes = read_bytes(inp, out)
                if bytes is None:
                    break
                sf.add_frame(bytes)

            if not sf.is_complete():
                continue

            sf.decode_channels()
            if total_frames == 0:
                print("\n{}\n".format(sf.summary()))
                if summary:
                    return
            else:
                print("\033[F\033[F\033[F\033[F")        
                print(sf.channel_value_string())
            total_frames += sf.frames_required
            last = time()
        except KeyboardInterrupt:
            break

    print("\n\nTotal of {} frames received and processed.".format(total_frames))


def main():
    parser = argparse.ArgumentParser(description='Spektrum Satellite Receiver test app')
    parser.add_argument('--serial', help='Serial device to use')
    parser.add_argument('--file', help='File to analyse')
    parser.add_argument('--output', help='File to store serial output into')
    parser.add_argument('--summary-only', action='store_true', help='Print summary of stream only')
    args = parser.parse_args()
    
    if args.serial is None and args.file is None:
        print("You need to specify a filename or serial device to use.")
        sys.exit(0)
    
    if args.output is not None and args.serial is None:
        print("Output files can only be created when using serial devices.")
    
    if args.serial:
        if not os.path.exists(args.serial):
            print("The supplied serial path does not exist.")
            sys.exit(0)
            
        ser = serial.Serial(port=args.serial,
                            baudrate=115200,
                            parity='N',
                            stopbits=1,
                            bytesize=8,
                            timeout=1)

        if not ser.isOpen():
            print("Unable to open the device.")
            sys.exit(0)

        print("Opened serial port...")
        if args.output:
            output_fh = open(args.output, 'wb')
            read_loop(ser, output_fh)
            output_fh.close()
        else:
            read_loop(ser)

        # should we flush any remaining bytes?
        ser.close()

    elif args.file:
        if not os.path.exists(args.file):
            print("The supplied filename does not exist.")
            sys.exit(0)
        with open(args.file, 'rb') as fh:
            read_loop(fh, summary=args.summary_only)


main()


