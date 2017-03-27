#!/usr/bin/env python

# REQUIRES the canon sdk extracted to this folder with the heirarchy intact
# starting with the Windows directory. See the error_file path for specifics.

eds_err = {} # this will be dictionary of edsdk errors

# Load Errors from EDSDKErrors.h
error_file = open("Windows/EDSDK/Header/EDSDKErrors.h", "rb")

header = 20 # ignore the first header lines

line_num = 0  # The current line number as we walk through the file
for line in error_file:
    t0 = line.split("#define")

    if ( line_num > header) and ( len(t0) > 1 ):
        err_type = "EDS_" + t0[1].split("EDS_")[1].split(' ')[0]
        err_code = "0x" + t0[1].split("0x")[-1].split("L")[0]
        
        eds_err[ int(err_code,16) ] = err_type

    line_num += 1

error_file.close()

if __name__ == "__main__":
    # Print a list of the errors in numerical order
    for s in sorted( ((v,k) for v,k in eds_err.iteritems())): print s