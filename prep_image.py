#!/usr/bin/env python
###############################################################################
###                                                                         ###
###                                 Imports                                 ###
###                                                                         ###
###############################################################################
import argparse
import cv2
import ctypes
import numpy as np
import sys
import time

###############################################################################
###                                                                         ###
###                             Global Variables                            ###
###                                                                         ###
###############################################################################
debug   = False
r_image = '' # Raw image (input)
t_image = '' # Converted image
verbose = False

###############################################################################
###                                                                         ###
###                                 Classes                                 ###
###                                                                         ###
###############################################################################


###############################################################################
###                                                                         ###
###                                Functions                                ###
###                                                                         ###
###############################################################################
def ArgParser():
    """ This function will handle the input arguments while keeping the main
        function tidy. """

    usage = """
    script_name.py flags

    This script is for .

            """

    parser = argparse.ArgumentParser( description = "Description",
                                      usage = usage)

    parser.add_argument( "--debug",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "debug",
                         help    = "Run in debug mode." )

    parser.add_argument( "file",
                         action  = "store",
                         default = "",
                         help    = "The image file to process." )

    parser.add_argument( "-v",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "verbose",
                         help    = "Make this script a chatterbox." )

    args = parser.parse_args()

    global debug, r_image, t_image, verbose
    debug   = args.debug
    r_image = args.file; r_image.replace('\\','/')
    t_image = r_image + ".tiff"
    verbose = args.verbose

def ConvertRAW_TIFF(file_path):
    PROG = "libraw/unprocessed_raw.exe"
    flags = [PROG, "-T", file_path]
    o,e = sp.Popen(flags, stdout=sp.PIPE, stderr=sp.PIPE).communicate()

    # print o

    return 

def Normalize(image, new_max=255):
    min_i = np.min(image)
    max_i = np.max(image)

    image = (image-min_i) / float( max_i ) * new_max

    return image.astype(np.uint8)

def PrepImage(image):
    i0 = cv2.Canny( image.copy(), 255, 255 )


    lines = cv2.HoughLinesP( i0,
                             rho = 1,
                             theta = np.pi/180.,
                             threshold = 80,
                             minLineLength = 50,
                             maxLineGap = 5 )[0]

    num_lines = len(lines)

    print "Found %i lines" % num_lines
    sys.stdout.flush()

    slopes = np.zeros(num_lines)
    for i in range(num_lines):

        dy = lines[i][3] - lines[i][1]
        dx = lines[i][2] - lines[i][0]

        if dx != 0: slopes[i] = np.arctan( dy / float(dx) ) / np.pi * 180.
        else: slopes[i] = 0

    i1 = im1.copy()
    for i,line in enumerate(lines):
        t0 = np.abs(slopes[i])

        if t0 > 5 or t0 < 0.05:
            cv2.line( i1, (line[0],line[1]), (line[2],line[3]), (0,255,0), 3 )

            cv2.putText( i1,
                         "%.4f" % slopes[i],
                         (line[0],line[1]),
                         cv2.FONT_HERSHEY_PLAIN,
                         3,
                         (0,0,255),
                         2 )

    print slopes
    sys.stdout.flush()

    # i_small = cv2.resize( i1,
    #                       None,
    #                       fx=0.25,
    #                       fy=0.25,
    #                       interpolation=cv2.INTER_NEAREST )
    # 4032 3024
    # cv2.imshow("i0", i1[756:2268,1008:3024])
    # cv2.waitKey(0)

    # cv2.imwrite(DIR + "temp.png", i1)
    return i1

def Timer(text="Segment"):
    """ Use for evaluating performance. Call in pairs to print out elapsed
        times: Once before the code segment and once after the code segment to
        time the segment. """
    import time
    import sys
    global tracker; global e1
    if tracker:
        elapsed_time = time.time() - e1
        if elapsed_time > 10:  print "%s took %.1fs" % (text,elapsed_time)
        elif elapsed_time > 1: print "%s took %.2fs" % (text,elapsed_time)
        else:                  print "%s took %.3fs" % (text,elapsed_time)
        sys.stdout.flush()
        tracker = False
    else:
        e1 = time.time()
        tracker = True

if __name__ == "__main__":
    ArgParser()

    # ConvertRAW_TIFF(r_image)

    im0 = cv2.imread( t_image, -1 )

    out_image = Normalize(im0)

    # im1 = np.rot90(im0,k=2)

    # im1 = cv2.cvtColor(im0, cv2.cv.CV_BGR2GRAY)

    # out_image = PrepImage( im1 )
    # RotateImage(im0)

    out_image = cv2.resize( out_image,
                        None,
                        fx=0.5,
                        fy=0.5,
                        interpolation=cv2.INTER_NEAREST )

    while True:
        # Timer()



        cv2.imshow( "live view", out_image )
        k = cv2.waitKey(0)

        if k == 27 or k == ord('x'): break

        # Timer()
