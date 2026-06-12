import os
import subprocess
import time
import logging
import ctypes

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- CoreGraphics Mouse Clicker Setup ---
try:
    CG = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    kCGEventLeftMouseDown = 1
    kCGEventLeftMouseUp = 2
    kCGEventMouseMoved = 5
    kCGMouseButtonLeft = 0
    kCGHIDEventTap = 0

    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    CG.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    CG.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]

    CG.CGEventPost.restype = None
    CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    def mouseclick(posx, posy):
        # Send click
        evt_down = CG.CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, CGPoint(posx, posy), kCGMouseButtonLeft)
        CG.CGEventPost(kCGHIDEventTap, evt_down)
        time.sleep(0.01)
        evt_up = CG.CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, CGPoint(posx, posy), kCGMouseButtonLeft)
        CG.CGEventPost(kCGHIDEventTap, evt_up)
except Exception as e:
    logger.error(f"Failed to load CoreGraphics: {e}")
    def mouseclick(posx, posy):
        pass

def get_window_bounds():
    """Returns (win_x, win_y, win_w, win_h) of the Antigravity window."""
    script = """
    tell application "System Events"
        tell process "Antigravity"
            set p to position of window 1
            set s to size of window 1
            return (item 1 of p as string) & "," & (item 2 of p as string) & "," & (item 1 of s as string) & "," & (item 2 of s as string)
        end tell
    end tell
    """
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
    bounds = [int(v.strip()) for v in result.stdout.strip().split(',')]
    return bounds

def grab_visual_quota():
    """
    Automates opening Antigravity, dynamically finding the Settings pane,
    clicking Models, scrolling, and capturing screenshots.
    """
    screenshot1_path = "/tmp/agy_quota_screenshot.png"
    screenshot2_path = "/tmp/agy_quota_screenshot2.png"
    
    try:
        logger.info("1. Activating Antigravity App...")
        subprocess.run(["osascript", "-e", 'tell application "Antigravity" to activate'], check=True)
        time.sleep(1)
        
        logger.info("2. Opening Settings window (Cmd+,)...")
        subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "," using command down'], check=True)
        time.sleep(1)

        logger.info("3. Calculating dynamic window boundaries for robust UI clicking...")
        win_x, win_y, win_w, win_h = get_window_bounds()
        center_x = win_x + (win_w / 2.0)
        center_y = win_y + (win_h / 2.0)
        
        # The Settings pane is centered in the window. 
        # The Models tab is at a fixed offset relative to the center.
        models_tab_x = center_x - 340
        models_tab_y = center_y - 220
        pane_x = center_x
        pane_y = center_y

        logger.info(f" -> Window Pos: ({win_x}, {win_y}) Size: {win_w}x{win_h}")
        logger.info(f" -> Dynamic Models Tab Coordinates: X={models_tab_x}, Y={models_tab_y}")

        logger.info("4. Clicking 'Models' tab...")
        mouseclick(models_tab_x, models_tab_y)
        time.sleep(1)

        logger.info(f"5. Taking screenshot of top quotas: {screenshot1_path}")
        subprocess.run(["screencapture", "-x", screenshot1_path], check=True)
        time.sleep(0.5)

        logger.info("6. Clicking inside Models pane to focus it...")
        mouseclick(pane_x, pane_y)
        time.sleep(0.5)

        logger.info("7. Scrolling down using Page Down key...")
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 121'], check=True)
        time.sleep(0.5)
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 121'], check=True)
        time.sleep(1)

        logger.info(f"8. Taking screenshot of bottom quotas: {screenshot2_path}")
        subprocess.run(["screencapture", "-x", screenshot2_path], check=True)
        
        logger.info("\n✅ Robust Dynamic Screenshots captured successfully!")
        
        return screenshot1_path, screenshot2_path
        
    except Exception as e:
        logger.error(f"Failed to capture quota screenshots: {e}")
        return None, None

if __name__ == "__main__":
    grab_visual_quota()
