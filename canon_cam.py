#!/cygdrive/c/Python27_32/python
"""
    TODO: - Complete Monochrome RAW image taking
                - Need to figure out how to handle RAW image once taken (not
                  necessarily part of this script but part of OCR script)
          - Add event callbacks to monitor camera status (could improve
            refresh rate and script speed)
          - Add HOUGH lines from OpenCV to give feedback on possible rotation
            needed to square image
          - Take picture and immediately transfer to the computer (current
            behavior saves image on the camera memory card and transferring
            is left up to the user by some other method outside this script)
"""
###############################################################################
###                                                                         ###
###                                 Imports                                 ###
###                                                                         ###
###############################################################################
import cv2
import ctypes
import numpy as np
import sys
import time

# Try to reduce the clutter in this script
import canon_helpers as c_hlp # Our helpers
from canon_errors import eds_err # Error codes and messages from EDSDK.h

###############################################################################
###                                                                         ###
###                             Global Variables                            ###
###                                                                         ###
###############################################################################
# Output image properties (set internal to the camera)
# While it is possible to set these at run time, it's much easier to just set
# it on the camera before plugging the USB in.
depth  = 3    # Color image so 3 channels
height = 2848 # Height and Width are the image format set in the camera;
width  = 4272 # These values are the maximum for the Canon Rebel Xsi

# Initialize the helpers module
c_hlp.debug   = False
c_hlp.verbose = True

# Load the canon library
edsdk_dll = ctypes.WinDLL("EDSDK\\EDSDK.dll")

# Debug Timer stuff
tracker=False; e1=0;

###############################################################################
###                                                                         ###
###                                 Classes                                 ###
###                                                                         ###
###############################################################################

class LivePreviewImage(ctypes.Structure):
        """ We are going to use this structure to store the live view image
            that we get from the camera. Using the Canon libraries we get a
            pointer to memory containing the image from the camera. We know
            the image is a jpeg because that is how the live image is stored
            according to the Canon SDK, however the pointer is a void pointer
            so the computer doesn't know it is a jpeg. We handle this by
            casting the void pointer as a pointer to unsigned byte values which
            is how the jpeg would be stored in a file on the hardrive. This
            makes it easy to save as a file or open as a file (without actually
            saving it).
        """
        _fields_ = [ ( "values", ctypes.POINTER(ctypes.c_ubyte) ) ]

        # we will use this to detect the end of the buffer
        end = "ffd900"

        def __init__(self):
            self.height = 0 # the height of self.image
            self.image  = None # this will contain a numpy array
            self.jpeg   = None # Will be byte string containing the image
            self.length = 0 # Will be the length of the data buffer
            self.label_r= 0 # the radius of the label in the image
            self.width  = 0 # the width of self.image
            self.x_c_p  = 0 # the center of the image
            self.y_c_p  = 0 # the center of the image

            self.h_lines = []
            self.v_lines = []

        def Overlay(self):
            # Draw all over the image so we can square the physical object

            # Grid
            for line_x in self.v_lines:
                cv2.line( self.image,
                          ( line_x, 0 ),
                          ( line_x, self.height ),
                          ( 0, 255, 0 ) )

            for line_y in self.h_lines:
                cv2.line( self.image,
                          ( 0, line_y ),
                          ( self.width, line_y ),
                          ( 0, 255, 0 ) )

            cv2.circle( self.image,
                        ( self.x_c_p, self.y_c_p ),
                        self.label_r,
                        ( 0, 0, 255 ),
                        1 )

        def PopulateImage(self):
            self.image = cv2.imdecode( np.fromstring( self.jpeg, np.uint8 ),
                                       cv2.IMREAD_COLOR )

            self.height,self.width,_ = self.image.shape
            self.x_c_p = self.width // 2
            self.y_c_p = self.height // 2

            self.label_r = int( self.y_c_p * 0.95 )

            # Generate lists of gridlines
            grid_spacing = 100
            # Vertical grid lines
            t0 = self.width // grid_spacing
            t1 = t0 // 2; t0 = ( t0 + 1 ) // 2
            self.v_lines = [(i*grid_spacing+self.x_c_p) for i in range(-t1,t0)]
            # Horizontal grid lines
            t0 = self.height // grid_spacing
            t1 = t0 // 2; t0 = ( t0 + 1 ) // 2
            self.h_lines = [(i*grid_spacing+self.y_c_p) for i in range(-t1,t0)]


class CanonLiveView():

    buffer_size = ctypes.c_ulonglong( depth * width * height )
    camera      = ctypes.c_void_p(None)
    data        = LivePreviewImage()
    device      = ctypes.c_uint(0)
    image_ref   = ctypes.c_void_p(None)
    out_buffer  = ctypes.c_void_p(None)
    stream      = ctypes.c_void_p(None)

    def __init__(self):
        self.Initialize()

    def Cleanup(self):
        if self.stream.value != None:
            status = edsdk_dll.EdsRelease(self.stream)
            self.Error("Release stream", status)

        if self.image_ref.value != None:
            status = edsdk_dll.EdsRelease(self.image_ref)
            self.Error("Release image_ref", status)

        # Close the live stream, then all of the streams, and last the edsdk
        self.device = ctypes.c_uint(0)
        status = edsdk_dll.EdsSetPropertyData( self.camera,
                                               0x500,
                                               0,
                                               ctypes.sizeof(self.device),
                                               ctypes.byref(self.device) )
        self.Error("Disconnect Output Device", status)

        status = edsdk_dll.EdsCloseSession(self.camera)
        self.Error("EdsCloseSession", status)

        status = edsdk_dll.EdsRelease(self.camera)
        self.Error("EdsRelease camera", status)

        status = edsdk_dll.EdsTerminateSDK()
        self.Error("EdsTerminateSDK", status)

    def Error(self, msg, error):
        c_hlp.ProcessError( msg, error, eds_err )

    def GrabImage(self):
        if self.stream.value != None:
            status = edsdk_dll.EdsCreateEvfImageRef(
                self.stream,
                ctypes.byref( self.image_ref ) )
            self.Error("Create image reference", status)

        if self.image_ref.value != None:
            status = edsdk_dll.EdsDownloadEvfImage(self.camera, self.image_ref)
            self.Error("Download image", status)

        status = edsdk_dll.EdsGetPointer( self.stream,
                                          ctypes.byref( self.out_buffer ) )
        self.Error("Get Pointer to Output Buffer", status)

        self.data.values = ctypes.cast( self.out_buffer,
                                        ctypes.POINTER(ctypes.c_ubyte) )

        self.data.jpeg = self.StreamToString(self.data.values)

    def Initialize(self):
        # From the SDK:
        #     When using the EDSDK libraries, you must call this API once
        #     before using EDSDK APIs
        # Sounds like good advice, let's take it
        status = edsdk_dll.EdsInitializeSDK()
        self.Error("EdsInitializeSDK", status)

        # Get a list of all connected cameras
        camera_list = ctypes.c_void_p(None)
        status = edsdk_dll.EdsGetCameraList(ctypes.byref(camera_list))
        self.Error("EdsGetCameraList", status)

        # What are we, rich? We only have one camera so we get the first one
        status = edsdk_dll.EdsGetChildAtIndex( camera_list,
                                               0, # index in the list
                                               ctypes.byref(self.camera) )
        self.Error("EdsGetChildAtIndex", status)

        # We don't need the massive list of our one cameras anymore
        status = edsdk_dll.EdsRelease(camera_list)
        self.Error("EdsRelease camera_list", status)

        # Let's tell the camera we are coming to use it
        status = edsdk_dll.EdsOpenSession(self.camera)
        self.Error("EdsOpenSession", status)

        # Set output device to be the computer if not already (check first)
        status = edsdk_dll.EdsGetPropertyData( self.camera,
                                               0x500,
                                               0,
                                               ctypes.sizeof(self.device),
                                               ctypes.byref(self.device) )
        self.Error("Check output device state", status)

        if self.device.value == 0: # Output device wasn't the computer
            self.device = ctypes.c_uint(2)
            status = edsdk_dll.EdsSetPropertyData( self.camera,
                                                   0x500,
                                                   0,
                                                   ctypes.sizeof(self.device),
                                                   ctypes.byref(self.device) )
            self.Error("Output Device is PC", status)

            # Give time for the mirror to flip up
            time.sleep(2)


        # Create the stream that the live preview data will use
        status = edsdk_dll.EdsCreateMemoryStream( self.buffer_size,
                                                  ctypes.byref(self.stream) )
        self.Error("Create memory stream", status)

    def SavePreviewImage(self):
        f = open("tmp.jpg", "wb")

        f.write( self.StreamToString(self.data.values) )

        f.close()

    def SaveImage_SDK(self):
        # This is the way to save the live preview image using the SDK
        status = edsdk_dll.EdsCreateFileStream( "image.jpg",
                                                1,
                                                1,
                                                ctypes.byref(self.stream) )
        self.Error("Save Image", status)

    def StreamToString(self,data):
        out_string = ''
        exit_alert = 0
        for v in data:
            out_string += chr(v)
            
            # look for the end of the file
            if exit_alert == 0 and v == 255: exit_alert = 1

            elif exit_alert == 1:
                if v == 217: exit_alert = 2
                else: exit_alert = 0

            elif exit_alert == 2:
                if v == 0: exit_alert = 3
                else: exit_alert = 0

            elif exit_alert == 3:
                if v == 0: break
                else: exit_alert = 0

        out_string = out_string[:-2]

        return out_string

    def Take_Picture(self):
        status = edsdk_dll.EdsSendCommand( self.camera,
                                           0, # Take Picture Command
                                           0 )

        # Replace this with a callback check
        time.sleep(6) # Give camera time to finish it's business

    def Take_RAW_Monochrome(self):
        """ Take and save a bayer image with 12-bit resolution. """
        ## Set camera settings to take image
        # Set Image Quality as RAW if it is not already set
        prop = ctypes.c_uint(0x64ff0f); out = ctypes.c_uint(0)
        status = edsdk_dll.EdsGetPropertyData( self.camera,
                                               0x100,
                                               0,
                                               ctypes.sizeof(out),
                                               ctypes.byref(out) )
        if out.value != prop.value:
            status = edsdk_dll.EdsSetPropertyData( self.camera,
                                                   0x100,
                                                   0,
                                                   ctypes.sizeof(prop),
                                                   ctypes.byref(prop) )

        # Set Picture Style to Monochrome (only affects color jpeg in raw)
        # prop = ctypes.c_uint(0x86)
        # status = edsdk_dll.EdsSetPropertyData( self.camera,
        #                                        0x114,
        #                                        0,
        #                                        ctypes.sizeof(prop),
        #                                        ctypes.byref(prop) )

        ## Take picture
        self.Take_Picture()

        ## Reset camera settings for live preview (color)
        # Set Picture Style to Standard
        # prop = ctypes.c_uint(0x81)
        # status = edsdk_dll.EdsSetPropertyData( self.camera,
        #                                        0x114,
        #                                        0,
        #                                        ctypes.sizeof(prop),
        #                                        ctypes.byref(prop) )

###############################################################################
###                                                                         ###
###                                Functions                                ###
###                                                                         ###
###############################################################################

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
    
    canon_lp = CanonLiveView()

    while True:
        # Timer()

        canon_lp.GrabImage()

        canon_lp.data.PopulateImage()

        canon_lp.data.Overlay()

        cv2.imshow("live view", canon_lp.data.image)
        k = cv2.waitKey(100)

        if k == 27 or k == ord('x'): break

        elif k == ord(' '):
            # Save image for OCR
            canon_lp.Take_RAW_Monochrome()

        elif k == ord('q'):
            # Save Preview image
            f = open("temp.jpg", "wb")
            f.write(canon_lp.data.jpeg)
            f.close()

        # Timer()

    canon_lp.Cleanup()
