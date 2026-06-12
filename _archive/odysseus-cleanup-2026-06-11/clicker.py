import ctypes
import time
import sys

# Load CoreGraphics
CG = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

# Define constants
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGMouseButtonLeft = 0
kCGHIDEventTap = 0

class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

def mouseEvent(type, posx, posy):
    CG.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    CG.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    
    CG.CGEventPost.restype = None
    CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    
    theEvent = CG.CGEventCreateMouseEvent(None, type, CGPoint(posx, posy), kCGMouseButtonLeft)
    CG.CGEventPost(kCGHIDEventTap, theEvent)

def mouseclick(posx, posy):
    mouseEvent(kCGEventLeftMouseDown, posx, posy)
    time.sleep(0.1)
    mouseEvent(kCGEventLeftMouseUp, posx, posy)

if __name__ == '__main__':
    x = float(sys.argv[1])
    y = float(sys.argv[2])
    print(f"Clicking at {x}, {y}")
    mouseclick(x, y)
