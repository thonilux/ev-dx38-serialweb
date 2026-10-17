import ctypes
from ctypes import wintypes
import time

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

class DCB(ctypes.Structure):
    _fields_ = [
        ('DCBlength', wintypes.DWORD),
        ('BaudRate', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('wReserved', wintypes.WORD),
        ('XonLim', wintypes.WORD),
        ('XoffLim', wintypes.WORD),
        ('ByteSize', wintypes.BYTE),
        ('Parity', wintypes.BYTE),
        ('StopBits', wintypes.BYTE),
        ('XonChar', ctypes.c_char),
        ('XoffChar', ctypes.c_char),
        ('ErrorChar', ctypes.c_char),
        ('EofChar', ctypes.c_char),
        ('EvtChar', ctypes.c_char),
        ('wReserved1', wintypes.WORD),
    ]

h = ctypes.windll.kernel32.CreateFileW(
    r"\\.\COM2",
    GENERIC_READ | GENERIC_WRITE,
    0,
    None,
    OPEN_EXISTING,
    FILE_ATTRIBUTE_NORMAL,
    None
)

if h == -1 or h == 0xFFFFFFFF:
    print("CreateFile failed:", ctypes.windll.kernel32.GetLastError())
else:
    print("CreateFile COM2 success! Handle:", h)
    dcb = DCB()
    dcb.DCBlength = ctypes.sizeof(DCB)
    if ctypes.windll.kernel32.GetCommState(h, ctypes.byref(dcb)):
        print(f"Current driver BaudRate: {dcb.BaudRate}")
    ctypes.windll.kernel32.CloseHandle(h)
