debug = False
verbose = True

def ProcessError(message, error=0, dll=None):
    """ Give some feedback to the user when an error is encountered and make
        it pretty; then exit. """
    import sys

    cS = "\033[1;31m"   # Light Red Color
    cE = "\033[0m"      # Reset Color
    cG = "\033[0;32m"   # Green "okay" color

    if error != 0:
        # Decode the error if possible
        code = " (" + str(error) + ")"
        if dll == None: code = str(error)
        else:
            code = dll[error]

        decode = "CODE: " + code

        # levity = " JOKE COMPLETE "

        # declen = levity.__len__()

        # Find the maximum length to determine the message width
        t0 = message.split("\n")
        if len(t0) > 1:
            t1 = 0
            for i in t0:
                if len(i) > t1: t1 = len(i)
            strlen = t1
        else:
            strlen = message.__len__()

        # if strlen < declen: strlen = declen
        if strlen < len(decode): strlen = len(decode)

        # Create some reusable formatted strings
        margin = " " * ( ( 80 - strlen - 2 * 4 ) // 2 )
        startPad = margin + cS + "*** " + cE
        endPad = cS + " ***" + cE

        # Print the header indicating an error
        hdr = "\n"
        hdr += margin
        hdr += cS
        hdr += "*" * (strlen / 2)
        hdr += " ERROR "
        hdr += "*" * ( (strlen / 2) + 1)
        if strlen % 2 != 0: hdr += "*"
        hdr += cE
        print hdr

        # Format the message and the error translation and error code
        blankLine = margin + cS + "*** " + " " * strlen + " ***" + cE
        print blankLine

        for i in t0: print startPad + "%*s"%(-strlen,i) + endPad

        print blankLine

        print startPad + "%*s"%(-(strlen),decode) + endPad

        print blankLine

        print margin + cS + "*" * (strlen + 8) + cE + "\n"
        # print margin + cS + levity + cE + "\n"

        sys.stdout.flush()
        if not debug: sys.exit(1)

    elif verbose:
        strlen = len(message)
        outString = message

        for i in range(77-strlen):
            outString += "."

        outString += cG + "OK" + cE + "\n"

        print outString

        sys.stdout.flush()