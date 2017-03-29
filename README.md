# record_labels
Python to capture text on record labels using a Canon Rebel xsi (450D) and the Tesseract OCR engine.

Requires:
    - Windows (because of precompiled Canon libraries)

    - (Optional?) Cygwin 64-bit (that was the environment used for development)

    - Python 2.7x 32-bit (tested with 2.7.13)
        - Have to use 32-bit in order to load the Canon precompiled dlls
        - opencv-python (tested with 3.2.0.6)
        - numpy (tested with 1.12.0)

    - Canon EDSDK (tested with 3.4)
        - Governed by Canon license so cannot provide; user needs to request
          from Canon directly.
        - Assumes a directory called "edsdk" containing the dlls from the sdk
        - Assumes the EDSDK directory structure starting from "Windows" (used
          to import the error messages from the sdk header)

    - Tesseract OCR compiled for windows (not included but assumed in path):
        $ tesseract -v
         tesseract 3.05.00dev
         leptonica-1.73
         libgif 4.1.6(?) : libjpeg 8d (libjpeg-turbo 1.4.2) : libpng 1.6.20 :
         libtiff 4.0.6 : zlib 1.2.8 : libwebp 0.4.3 : libopenjp2 2.1.0
