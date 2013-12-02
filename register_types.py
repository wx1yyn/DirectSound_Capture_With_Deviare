from win32api import *
from win32con import *
import os

tlb_path = os.path.dirname(__file__) + r"\py_deviare_test.tlb"
lock_path = os.path.dirname(__file__) + r"\.deviare_types_registered"

g_RegistryData = [[r"Interface\{0F0F0F0F-113A-4832-9104-000000000002}", "IDirectSound"],
#IDirectSound
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000002}\ProxyStubClsid", "{00020424-0000-0000-C000-000000000046}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000002}\ProxyStubClsid32", "{00020424-0000-0000-C000-000000000046}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000002}\TypeLib", "{0F0F0F0F-113A-4832-9104-000000000001}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000002}\TypeLib", "1.0", "Version"],
#IDirectSoundBuffer
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000003}", "IDirectSoundBuffer"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000003}\ProxyStubClsid", "{00020424-0000-0000-C000-000000000046}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000003}\ProxyStubClsid32", "{00020424-0000-0000-C000-000000000046}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000003}\TypeLib", "{0F0F0F0F-113A-4832-9104-000000000001}"],
[r"Interface\{0F0F0F0F-113A-4832-9104-000000000003}\TypeLib", "1.0", "Version"],
#Deviare Custom Type Library
[r"TypeLib\{0F0F0F0F-113A-4832-9104-000000000001}\1.0", "Deviare IDirectSound"],
[r"TypeLib\{0F0F0F0F-113A-4832-9104-000000000001}\1.0\0\win32", tlb_path],
[r"TypeLib\{0F0F0F0F-113A-4832-9104-000000000001}\1.0\FLAGS", "0"],
[r"TypeLib\{0F0F0F0F-113A-4832-9104-000000000001}\1.0\HELPDIR", ""]]

def WriteEntry(entry):
   path = entry[0]
   value = entry[1]
   value_name = entry[2] if len(entry) > 2 else None
   if len(entry) > 2:       
       value_name = entry[2]
       hkey = RegOpenKey(HKEY_CLASSES_ROOT, path, 0, KEY_ALL_ACCESS)
       RegSetValueEx(hkey, value_name, 0, REG_SZ, value)
   else:
       RegSetValue(HKEY_CLASSES_ROOT, path, REG_SZ, value)


def IsRegistered():
    try:
        f = open(lock_path)
        f.close()
        return True
    except:
        return False

def LockRegistration():
    f = open(lock_path, "w")
    f.close()

#Register DirectSound interfaces and our TLB:
if not IsRegistered():
    #Register
    for entry in g_RegistryData:
        WriteEntry(entry)
    LockRegistration()

