#!/cygdrive/c/Python27_32/python
"""
    TODO: - Add event callbacks to monitor camera status (could improve
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
import argparse
import cv2
import ctypes
import numpy as np
import os
import sys
import time

# Try to reduce the clutter in this script
import canon_helpers as c_hlp # Our helpers
from canon_errors import * # EDSDK Errors from the errors header
from canon_types import * # EDSDK Types from the types header

###############################################################################
###                                                                         ###
###                             Global Variables                            ###
###                                                                         ###
###############################################################################
cwd    = os.getcwd() + '\\'
depth  = 3    # Color image so 3 channels
height = 2848 # Height and Width are the image format set in the camera;
IM_DIR = "C:\\Code\\Records\\images\\"
live   = False # use as an indicator for the live stream window to indicate live
width  = 4272 # These values are the maximum for the Canon Rebel Xsi

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

            self.av  = 0
            self.iso = 0
            self.tv  = 0

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

            # User Controls
            cv2.rectangle(self.image, (0,0), (200,100), (0,0,0), -1)

            cv2.putText( self.image,
                         "(a,q) ISO = %s" % iso[self.iso],
                         ( 5, 20 ),
                         cv2.FONT_HERSHEY_PLAIN,
                         1,
                         (255,255,255) )

            cv2.putText( self.image,
                         "(s,w) Aperture = %s" % av[self.av],
                         ( 5, 40 ),
                         cv2.FONT_HERSHEY_PLAIN,
                         1,
                         (255,255,255) )

            cv2.putText( self.image,
                         "(d,e) Shutter = %s" % tv[self.tv],
                         ( 5, 60 ),
                         cv2.FONT_HERSHEY_PLAIN,
                         1,
                         (255,255,255) )

            if live:
                cv2.circle( self.image,
                            ( self.width-20, 20 ),
                            10,
                            (0,255,0),
                            -1 )


class CanonLiveView():

    def __init__(self):

        self.buffer_size = ctypes.c_ulonglong( depth * width * height )
        self.camera      = ctypes.c_void_p(None)
        self.data        = LivePreviewImage()
        self.device      = ctypes.c_uint(0)
        self.image_ref   = ctypes.c_void_p(None)
        self.out_buffer  = ctypes.c_void_p(None)
        self.stream      = ctypes.c_void_p(None)

        self.prop_iso    = ctypes.c_uint()
        self.prop_av     = ctypes.c_uint()
        self.prop_tv     = ctypes.c_uint()

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
        status = edsdk_dll.EdsSetPropertyData(
                    self.camera,
                    eds_typ["kEdsPropID_Evf_OutputDevice"],
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

    def DownloadImage(self):
        count    = ctypes.c_ulonglong(0)
        DCIM     = False
        dir_item = ctypes.c_void_p()
        volume   = ctypes.c_void_p()

        status = edsdk_dll.EdsGetChildCount( self.camera, ctypes.byref(count) )
        self.Error("Get Camera count", status)

        status = edsdk_dll.EdsGetChildAtIndex( self.camera,
                                               0,
                                               ctypes.byref(volume) )
        self.Error("Get Volume", status)

        status = edsdk_dll.EdsGetChildCount( volume, ctypes.byref(count) )
        self.Error("Get Volume count", status)

        for i in range(count.value):

            dir_item_info = EdsDirectoryItemInfo()

            status = edsdk_dll.EdsGetChildAtIndex( volume,
                                                   i,
                                                   ctypes.byref(dir_item) )
            self.Error("Get Child at Index %i"%i, status)

            status = edsdk_dll.EdsGetDirectoryItemInfo(
                        dir_item,
                        ctypes.byref(dir_item_info) )
            self.Error("Get Item Info", status)

            if dir_item_info.isFolder == 1 and \
               dir_item_info.szFileName == "DCIM":
                DCIM = True
                break

        if not DCIM:
            self.Error( "DCIM folder not found on camera.",0x40 )
            return -1

        # The idea is to download the last image taken
        while True:
            status = edsdk_dll.EdsGetChildCount( dir_item, ctypes.byref(count) )
            self.Error( "Get %s count (%i)" % ( dir_item_info.szFileName,
                                                count.value ),
                        status)

            if count.value == 0:
                self.Error( "No image found on camera.", 0x22 )
                return -1

            child_item = ctypes.c_void_p()
            child_item_info = EdsDirectoryItemInfo()

            status = edsdk_dll.EdsGetChildAtIndex( dir_item,
                                                   (count.value - 1),
                                                   ctypes.byref(child_item) )
            self.Error("Get File at Index %i"%i, status)

            status = edsdk_dll.EdsGetDirectoryItemInfo(
                        child_item,
                        ctypes.byref(child_item_info) )
            self.Error("Get Item Info (%s)"%child_item_info.szFileName, status)

            if child_item_info.isFolder == 0:
                file_item = child_item
                file_item_info = child_item_info
                break

            else:
                dir_item = child_item

        file_stream = ctypes.c_void_p(None)
        status = edsdk_dll.EdsCreateFileStream(
                        IM_DIR + file_item_info.szFileName,
                        1,#eds_typ["kEdsFileCreateDisposition_CreateAlways"],
                        2,#eds_typ["kEdsAccess_ReadWrite"],
                        ctypes.byref(file_stream) )
        self.Error("Create File Stream", status)

        status = edsdk_dll.EdsDownload( file_item,
                                        ctypes.c_ulonglong(file_item_info.size),
                                        file_stream )
        self.Error("Download image", status)

        status = edsdk_dll.EdsDownloadComplete( file_item )
        self.Error("Download Complete", status)

        # Verify file is downloaded locally
        if os.path.isfile( cwd + file_item_info.szFileName ):
            # delete the file on the camera
            status = edsdk_dll.EdsDeleteDirectoryItem( file_item )
            self.Error("Delete remote file",status)

        status = edsdk_dll.EdsRelease( file_item )
        self.Error("Release file item",status)

        status = edsdk_dll.EdsRelease( file_stream )
        self.Error("Release file stream",status)

    def Error(self, msg, error):
        if error != 0 or c_hlp.verbose:
            c_hlp.ProcessError( msg, error, eds_err )

    def GetDCIMFolder(self):
        count    = ctypes.c_ulonglong(0)
        DCIM     = None
        dir_item = ctypes.c_void_p()
        volume   = ctypes.c_void_p()

        status = edsdk_dll.EdsGetChildCount( self.camera, ctypes.byref(count) )
        self.Error("Get Camera count", status)

        status = edsdk_dll.EdsGetChildAtIndex( self.camera,
                                               0,
                                               ctypes.byref(volume) )
        self.Error("Get Volume", status)

        status = edsdk_dll.EdsGetChildCount( volume, ctypes.byref(count) )
        self.Error("Get Volume count", status)

        for i in range(count.value):

            dir_item_info = EdsDirectoryItemInfo()

            status = edsdk_dll.EdsGetChildAtIndex( volume,
                                                   i,
                                                   ctypes.byref(dir_item) )
            self.Error("Get Child at Index %i"%i, status)

            status = edsdk_dll.EdsGetDirectoryItemInfo(
                        dir_item,
                        ctypes.byref(dir_item_info) )
            self.Error("Get Item Info", status)

            if dir_item_info.szFileName == "DCIM":
                DCIM = dir_item
                status = edsdk_dll.EdsRelease(dir_item)
                self.Error("Release of dir_item error", status)
                dir_item = None
                break

        return DCIM

    def GrabImage(self):
        if self.stream.value != None:
            status = edsdk_dll.EdsCreateEvfImageRef(
                        self.stream,
                        ctypes.byref( self.image_ref ) )
            if status != 0: self.Error("Create image reference", status)

        if self.image_ref.value != None:
            status = edsdk_dll.EdsDownloadEvfImage(self.camera, self.image_ref)
            # self.Error("Download image", status)

        status = edsdk_dll.EdsGetPointer( self.stream,
                                          ctypes.byref( self.out_buffer ) )
        # self.Error("Get Pointer to Output Buffer", status)

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
        status = edsdk_dll.EdsGetPropertyData(
                    self.camera,
                    eds_typ["kEdsPropID_Evf_OutputDevice"],
                    0,
                    ctypes.sizeof(self.device),
                    ctypes.byref(self.device) )
        self.Error("Check output device state", status)

        if self.device.value == 0: # Output device wasn't the computer
            self.device = ctypes.c_uint( eds_typ["kEdsEvfOutputDevice_PC"] )
            status = edsdk_dll.EdsSetPropertyData(
                        self.camera,
                        eds_typ["kEdsPropID_Evf_OutputDevice"],
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

        # Get the ISO setting
        status = edsdk_dll.EdsGetPropertyData( self.camera,
                                               eds_typ["kEdsPropID_ISOSpeed"],
                                               0,
                                               ctypes.sizeof(self.prop_iso),
                                               ctypes.byref(self.prop_iso) )
        status_msg = "Get ISO setting: %s" % \
                                           iso[iso_v.index(self.prop_iso.value)]
        self.Error(status_msg, status)
        self.data.iso = iso_v.index(self.prop_iso.value)

        # Get the Av setting
        status = edsdk_dll.EdsGetPropertyData( self.camera,
                                               eds_typ["kEdsPropID_Av"],
                                               0,
                                               ctypes.sizeof(self.prop_av),
                                               ctypes.byref(self.prop_av) )
        status_msg = "Get Aperture setting: %s" % \
                                              av[av_v.index(self.prop_av.value)]
        self.Error(status_msg, status)
        self.data.av = av_v.index(self.prop_av.value)

        # Get the Tv setting
        status = edsdk_dll.EdsGetPropertyData( self.camera,
                                               eds_typ["kEdsPropID_Tv"],
                                               0,
                                               ctypes.sizeof(self.prop_tv),
                                               ctypes.byref(self.prop_tv) )
        status_msg = "Get Shutter setting: %s" % \
                                              tv[tv_v.index(self.prop_tv.value)]
        self.Error(status_msg, status)
        self.data.tv = tv_v.index(self.prop_tv.value)

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
        prop = ctypes.c_uint( eds_typ["EdsImageQuality_LR"] )
        out = ctypes.c_uint(0)
        status = edsdk_dll.EdsGetPropertyData(
                    self.camera,
                    eds_typ["kEdsPropID_ImageQuality"],
                    0,
                    ctypes.sizeof(out),
                    ctypes.byref(out) )

        if out.value != prop.value:
            status = edsdk_dll.EdsSetPropertyData(
                        self.camera,
                        eds_typ["kEdsPropID_ImageQuality"],
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

        self.DownloadImage()

    def UpdateSetting(self, setting, value):
        """ Update settings on the camera. Intended for ISO Speed, Aperture,
            Shutter Speed. """
        prop = ctypes.c_uint( value )
        status = edsdk_dll.EdsSetPropertyData(
                        self.camera,
                        setting,
                        0,
                        ctypes.sizeof(prop),
                        ctypes.byref(prop) )

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
    # parser.add_argument( "-d",
    #                      nargs   = '*',
    #                      action  = "store",
    #                      default = [],
    #                      dest    = "depths",
    #                      help    = "The depth(s) to view." )

    parser.add_argument( "--debug",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "debug",
                         help    = "Run in debug mode." )

    # parser.add_argument( "DIR",
    #                      action  = "store",
    #                      default = "",
    #                      help    = "The directory of images to process." )

    parser.add_argument( "-v",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "verbose",
                         help    = "Make this script a chatterbox." )

    args = parser.parse_args()

    c_hlp.debug   = args.debug
    c_hlp.verbose = args.verbose

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
        live = not live

        canon_lp.GrabImage()

        canon_lp.data.PopulateImage()

        canon_lp.data.Overlay()

        out_image = cv2.resize( canon_lp.data.image,
                                None, fx=4, fy=4,
                                interpolation=cv2.INTER_NEAREST )

        cv2.imshow( "live view", out_image )
        k = cv2.waitKey(100)

        if k == 27 or k == ord('x'): break

        elif k == ord(' '):
            # Save image for OCR
            canon_lp.Take_RAW_Monochrome()

        elif k == ord('m'):
            # Save Preview image
            f = open("temp.jpg", "wb")
            f.write(canon_lp.data.jpeg)
            f.close()

        elif k == ord('a'):
            # Decrease ISO
            canon_lp.data.iso -= 1
            if canon_lp.data.iso < 0:
                canon_lp.data.iso = 0
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_ISOSpeed"], 
                                        iso_v[canon_lp.data.iso] )

        elif k == ord('q'):
            # Increase ISO
            canon_lp.data.iso += 1
            if canon_lp.data.iso >= len(iso):
                canon_lp.data.iso = len(iso) - 1
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_ISOSpeed"],
                                        iso_v[canon_lp.data.iso] )

        elif k == ord('s'):
            # Decrease Aperture
            canon_lp.data.av -= 1
            if canon_lp.data.av < 0:
                canon_lp.data.av = 0
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_Av"], 
                                        av_v[canon_lp.data.av] )

        elif k == ord('w'):
            # Increase Aperture
            canon_lp.data.av += 1
            if canon_lp.data.av >= len(av):
                canon_lp.data.av = len(av) - 1
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_Av"],
                                        av_v[canon_lp.data.av] )

        elif k == ord('d'):
            # Decrease Shutter Speed
            canon_lp.data.tv -= 1
            if canon_lp.data.tv < 0:
                canon_lp.data.tv = 0
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_Tv"], 
                                        tv_v[canon_lp.data.tv] )

        elif k == ord('e'):
            # Increase Shutter Speed
            canon_lp.data.tv += 1
            if canon_lp.data.tv >= len(tv):
                canon_lp.data.tv = len(tv) - 1
            else:
                canon_lp.UpdateSetting( eds_typ["kEdsPropID_Tv"],
                                        tv_v[canon_lp.data.tv] )

        # Timer()

    canon_lp.Cleanup()
