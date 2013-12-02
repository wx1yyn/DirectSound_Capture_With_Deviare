import py_deviare_directsound
import py_deviare_wavtools
import py_deviare_objects
import ctypes

WAV_PATH = r".\deviare_capture"

#Globals
g_Listener = None
g_FileCount = 0

def GetFilePath():
    global g_FileCount
    path = WAV_PATH + repr(g_FileCount) + ".wav"
    g_FileCount = g_FileCount + 1
    return path

#Direct Sound Event Listener
class DSoundListener(py_deviare_directsound.Listener):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.__waves = dict()
        self.__buffer = None
        self.__prev_read = None
        self.__prev_write = None

    def OnBufferCreated(self, buffer_id, is_primary, flags, buffer_size):
        wave = py_deviare_wavtools.WaveFile()
        self.__waves[buffer_id] = wave

    def OnBufferInit(self, buffer_id, wfx):
        if not self.__waves.has_key(buffer_id):
            #We have not created this buffer, ignore it
            return
        wave = self.__waves[buffer_id]
        wave.initialize(GetFilePath(), wfx)

    def OnBufferWritten(self, buffer_id, wav_data):
        if not self.__waves.has_key(buffer_id):
            #We have not created this buffer, ignore it
            return
        wave = self.__waves[buffer_id]
        wave.write(wav_data)

    def CloseWaves(self):
        for wave in self.__waves.values():
            wave.close()

#Run
def run_test():
    global g_Listener
    g_Listener = DSoundListener()

    print "** Deviare Direct Sound Capture **"
    proc = raw_input("Enter complete process name: ")
    proc = proc.lower()
    use_polling = (proc == 'skype.exe')
    py_deviare_directsound.run_dispatch(proc, g_Listener, use_polling)

    #Keep alive until user request close
    ctypes.windll.user32.MessageBoxA(0, 'Select OK to stop recording', 'Deviare DirectSound Capture', 0)

    #Close wavs now
    g_Listener.CloseWaves()



