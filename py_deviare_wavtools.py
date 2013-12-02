import ctypes
import threading

#Constants
MMIO_ALLOCBUF = 65536
MMIO_CREATE = 4096
MMIO_READWRITE = 2
MMIO_CREATERIFF = 32
MMIO_DIRTY = 268435456
MMIO_FINDCHUNK = 16
NULL = 0
SEEK_SET = 3
WAVE_FORMAT_PCM = 1

#Alias
winmm = ctypes.windll.winmm

#Autolock
class AutoLock(object):
    lock = None
    def __init__(self, lock):
        assert(lock != None)
        self.lock = lock
        self.lock.acquire()
    def __del__(self):
        self.lock.release()

#Structure
class Structure(ctypes.Structure):
    _pack_ = 1
    def __repr__(self):
        '''Print the fields'''
        res = []
        for field in self._fields_:
            res.append('%s=%s' % (field[0], repr(getattr(self, field[0]))))
        return self.__class__.__name__ + '(' + ', '.join(res) + ')'

    def ptr(self):
        return ctypes.addressof(self)

    def Create(Klass, cbuffer):
        return Klass.from_buffer(cbuffer)
    Create = classmethod(Create)


#WAVEFORMATEX
class WaveFormatEx(Structure):
    _fields_ = [("wFormatTag", ctypes.c_short),
                ("nChannels", ctypes.c_short),
                ("nSamplesPerSec", ctypes.c_int),
                ("nAvgBytesPerSec", ctypes.c_int),
                ("nBlockAlign", ctypes.c_short),
                ("wBitsPerSample", ctypes.c_short),
                ("cbSize", ctypes.c_short)]

#MMCKINFO
class MmCkInfo(Structure):
    _fields_ = [("ckid", ctypes.c_char*4),
                ("cksize", ctypes.c_int),
                ("fccType", ctypes.c_char*4),
                ("dwDataOffset", ctypes.c_int),
                ("dwFlags", ctypes.c_int)]

#MMIOINFO
class MmioInfo(Structure):
    _fields_ = [("dwFlags", ctypes.c_int),
                ("fccIOProc", ctypes.c_char*4),
                ("pIOProc", ctypes.c_void_p), #LPMMIOPROC
                ("wErrorRet", ctypes.c_uint),
                ("hTask", ctypes.c_void_p), #HTASK
                ("cchBuffer", ctypes.c_long),
                ("pchBuffer", ctypes.c_void_p), #HPSTR
                ("pchNext", ctypes.c_void_p), #HPSTR
                ("pchEndRead", ctypes.c_void_p), #HPSTR
                ("pchEndWrite", ctypes.c_void_p), #HPSTR
                ("lBufOffset", ctypes.c_long),
                ("lDiskOffset", ctypes.c_long),
                ("adwInfo", ctypes.c_int*4),
                ("dwReserved", ctypes.c_int*2),
                ("hmmio", ctypes.c_void_p)] #HMMIO

#Class to write wav files
class WaveFile(object):
    hmmio = None #mmio handle
    lock = None
    ck_root = None
    ck_child = None
    mmio_info = None
    file_path = None
    wave_format = None

    def __init__(self):
        self.lock = threading.Lock()
        self.mmio_info = MmioInfo()
        self.ck_child = MmCkInfo()
        self.ck_root = MmCkInfo()

    def __del__(self):
        self.close()

    def __repr__(self):
        me = self.__class__.__name__
        res = []
        for item in self.__dict__:
            a = getattr(self, item)
            res.append( "%s=%s" %(item, repr(a)))
        return me + ':\n *' + '\n *'.join(res)

    def initialize(self, file_path, wave_format):
        assert(file_path != '' and issubclass(wave_format.__class__, WaveFormatEx))
        AutoLock(self.lock)
        self.file_path = file_path
        self.wave_format = wave_format

    def close(self):
        AutoLock(self.lock)
        if (self.hmmio == None):
            return
        hmmio = self.hmmio
        ck_child = self.ck_child
        ck_root = self.ck_root

        #Ascend from child
        ret = winmm.mmioAscend(hmmio, ck_child.ptr(), 0)
        assert(ret == 0)

        #Ascend from root
        ret = winmm.mmioAscend(hmmio, ck_root.ptr(), 0)
        assert(ret == 0)
        
        #Close
        winmm.mmioClose(hmmio, 0)
        self.hmmio = None
        print "Wav closed: ", self.file_path
        #done

    def write(self, cdata):
        if (ctypes.sizeof(cdata) == 0):
            return
        AutoLock(self.lock)

        #open on first write
        if (self.hmmio == None):
            self.__open()
        assert(self.hmmio != None)

        #write
        hmmio = self.hmmio
        sz = ctypes.sizeof(cdata)
        ptr = ctypes.addressof(cdata)
        ret = winmm.mmioWrite(hmmio, ptr, sz)
        assert(ret == sz)
        #print "Wav written: %i %s" %(sz, self.file_path)

    ## Private Functions ##
    def __open(self):
        AutoLock(self.lock)
        assert(self.hmmio == None)

        hmmio = winmm.mmioOpenA(self.file_path, NULL, MMIO_ALLOCBUF | MMIO_READWRITE | MMIO_CREATE)
        assert(hmmio != NULL)
        self.hmmio = hmmio

        #Write header
        self.__write_header(self.wave_format)
        print "Wav opened: ", self.file_path

    def __write_header(self, wave_format):
        AutoLock(self.lock)
        assert(self.hmmio)
        hmmio = self.hmmio
        ck_root = self.ck_root
        ck_child = self.ck_child
        mmio_info = self.mmio_info
        
        #Wave chunk
        ck_root.fccType = 'WAVE'
        ret = winmm.mmioCreateChunk(hmmio, ck_root.ptr(), MMIO_CREATERIFF)
        assert(ret == 0)

        #Format chunk
        ck_child.ckid = 'fmt '
        ck_child.cksize = ctypes.sizeof(WaveFormatEx)-ctypes.sizeof(ctypes.c_short) # sizeof(PCMWAVEFORMAT)
        ret = winmm.mmioCreateChunk(hmmio, ck_child.ptr(), 0)
        assert(ret == 0)

        #Write format data
        sz = ctypes.sizeof(wave_format)
        if (wave_format.wFormatTag != WAVE_FORMAT_PCM):
            sz = sz + wave_format.cbSize
        ret = winmm.mmioWrite(hmmio, wave_format.ptr(), sz)
        assert(ret == sz)

        #Back to root
        ret = winmm.mmioAscend(hmmio, ck_child.ptr(), 0)
        assert(ret == 0)
        
        #Data chunk
        ck_child.ckid = "data"
        ck_child.cksize = 0
        ret = winmm.mmioCreateChunk(self.hmmio, ck_child.ptr(), 0)
        assert(ret == 0)
        #done
