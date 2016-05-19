#!/usr/bin/python

import os
import sys
import struct
import serial
import argparse
import fcntl
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
        self.raw = data
        self.final_values = {}

    def add_frame(self, frame):
        self.raw.extend(frame)
        self.channel_data.extend(frame[2:])

    @property
    def channel_bits(self):
        return 10 if self.tx_data & 0x10 == 0 else 11

    @property
    def frames_required(self):
        # Are the bottom 2 bits really used for the frames required?       
        # return self.tx_data & 0x03
        return 2

    @property
    def tx_number(self):
        return self.tx_data >> 2

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
            self.channel_values[chan] = val

        if self.channel_bits == 10:
            for n in range(0, self.highest_channel + 1, 2):
                chan = 0 if n == 0 else n / 2
                if self.channel_values.get(n, 0) == 0:
                    self.final_values[chan] = 1024 + self.channel_values.get(n + 1, 0)
                else:
                    self.final_values[chan] = self.channel_values.get(n, 0)

    def is_complete(self):
        return len(self.channel_data) == self.frames_required * 14

    def summary(self):
        return """
Dropped:              {}
Tansmitter data byte: 0x{:02x}  {}
Bits per channel:     {}
Frames Required:      {}
Highest Channel:      {}
  TX Number:          {}""".format(self.dropped,
                                   self.tx_data,
                                   bin(self.tx_data)[2:],
                                   self.channel_bits,
                                   self.frames_required,
                                   self.highest_channel,
                                   self.tx_number)

    def channel_value_string(self):
        chans = range(self.highest_channel + 1)
        lines = 4
        title = "      " + " ".join(["  {:2d}".format(x) for x in chans]) + "\n"
        title += "      " + " ".join(["----" for x in chans]) + "\nRcvr  "
        title += " ".join(["{:4d}".format(self.channel_values.get(x, 0)) for x in chans])
        title += "\n"
        if self.channel_bits == 10:
            chans2 = range(len(self.final_values))    
            lines = 6
            title += "      " + " ".join(["----" for x in chans2]) + "\nCalc  "
            title += " ".join(["{:4d}".format(self.final_values.get(x, 0)) for x in chans2])            
            title += "\n"
        return '\033[{}A'.format(lines) + title

    def raw_bytes(self):
        s = "  "
        for n in range(len(self.raw)):
            if n > 0 and n % 16 == 0:
                s += "\n  "
            s += "{:02X} ".format(self.raw[n])
        return s


class SpektrumReader(object):
    def __init__(self, inp, outp=None):
        self.input = inp
        self.output = outp
        self.spektrum = None
        self.total_frames = 0

    def sync(self):
        # A full set of data should be transmitted at least every 22ms
        # so when we are looking to sync we want to see a repeating series
        # of 32 bytes (2 16 byte frames seperated by 11ms).
        offs = 0
        done = False
        bytes = self.read_bytes(64)
        if bytes is None:
            return False

        while offs < 32 and bytes[offs] == 0xff:
            bytes.extend(self.read_bytes(1))
            offs += 1
        
        while offs < 32:
            matched = True
            if bytes[offs] != 0xff and bytes[offs] == bytes[offs + 16]:
                for ck in range(32):
                    if bytes[ck + offs] != bytes[ck + offs + 32]:
                        matched = False
                        break

                if matched:
                    if bytes[offs + 2] & 0x80 == 0x80:
                        self.read_bytes(16)
                    return True
            offs += 1
            bytes.extend(self.read_bytes(1))

        return False

    def read_bytes(self, n=16):
        bytes = map(ord, self.input.read(n))
        if len(bytes) == 0:
            return None
        if self.output is not None and len(bytes) > 0:
            self.output.write(pack("{}B".format(len(bytes)), *bytes))
        return bytes if len(bytes) == n else None

    def build_spektrum(self):
        self.spektrum = None
        bytes = self.read_bytes(16)
        if bytes is None:
            return False

        if bytes[2] & 0x80 == 0x80:
            print("Appear to have detected a second frame as initial??? Resyncing...")
            if self.sync() is False:
                print("Unable to resync, aborting...")
                return False
            return self.build_spektrum()

        self.spektrum = SpektrumFrame(bytes)
        for extra in range(1, self.spektrum.frames_required):
            bytes = self.read_bytes(16)
            if bytes is None:
                break
            self.spektrum.add_frame(bytes)
        if not self.spektrum.is_complete():
            return False
        self.spektrum.decode_channels()
        self.total_frames += self.spektrum.frames_required
        return True

    def close_all(self):
       if hasattr(self, 'close_input'):
           self.close_input()
       self.input.close()
       if self.output:
           self.output.close()

    def print_data(self):
        if self.spektrum is None:
            return
        if self.total_frames <= 2:
            print("\n{}\n\n\n\n\n\n\n".format(self.spektrum.summary()))

        print(self.spektrum.channel_value_string())


class SerialReader(SpektrumReader):
    def __init__(self, serial, output=None):
        SpektrumReader.__init__(self, serial, output)
   
    def read_loop(self, summary=False):
        print("Waiting for data to be available...")
        try:
            while self.input.inWaiting() == 0:
                pass
        except KeyboardInterrupt:
            return
        print("Reading data... CTRL + C to exit\n")

        last = time()
        if self.sync() is False:
            print("Unable to sync frames. Exiting...")
            return

        while True:
            try:
                if time() - last > 5 and self.total_frames > 0:
                    print("Break in reception detected. Resetting frame counter.")
                    self.total_frames = 0

                if self.build_spektrum() is False:
                    continue

                self.print_data()
                if summary:
                    return
                        
                last = time()
            except KeyboardInterrupt:
                break

    def close_input(self):
        self.input.flush()


class FileReader(SpektrumReader):
    def __init__(self, serial, output=None):
        SpektrumReader.__init__(self, serial, output)
   
    def read_loop(self, summary=False):
        highest = 0
        if self.sync() is False:
            return

        while True:
            if self.build_spektrum() is False:
                break
            
            if highest > 0 and highest != self.spektrum.highest_channel:
                self.total_frames = 0

            self.print_data()
            if summary:
                return

            highest = self.spektrum.highest_channel


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

    reader = None
    if args.serial:
        if not os.path.exists(args.serial):
            print("The supplied serial path does not exist.")
            sys.exit(0)
        out = None            
        ser = serial.Serial(port=args.serial,
                            baudrate=115200,
                            parity='N',
                            stopbits=1,
                            bytesize=8,
                            timeout=1)

        if not ser.isOpen():
            print("Unable to open the device.")
            sys.exit(0)
        reader = SerialReader(ser)
        print("Opened serial port...")
    elif args.file:
        if not os.path.exists(args.file):
            print("The supplied filename does not exist.")
            sys.exit(0)           
        reader = FileReader(open(args.file, 'rb'))

    if args.output:
        reader.output = open(args.output, 'wb')

    reader.read_loop(args.summary_only)
    print("\nTotal of {} frames read.".format(reader.total_frames))
    reader.close_all()
    
main()


