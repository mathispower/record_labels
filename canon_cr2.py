#!/usr/bin/env python
""" Useful things for reading a RAW image from the Canon Xsi. """
import binascii
import cv2
import numpy as np

class CR2():

    def __init__(self):
        self.b_image = None # Will contain the bayer image information


if __name__ == "__main__":
    
    f = open("IMG_4679.CR2", "rb")
    
    f.seek(0x0C)

    raw_address = binascii.hexlify(f.read(1))
    raw_address = binascii.hexlify(f.read(1)) + raw_address
    
    f.seek(int(raw_address,16))

    print "%r" % binascii.hexlify(f.read(1))


    f.close()