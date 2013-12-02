from py_deviare_objects import *
from py_deviare_wavtools import *
import ctypes

#Globals
g_Listener = None
g_ISoundBuffer_Hooked = False
g_ISound_Hooked = False
g_Target_Process = ''
g_Handlers = []
g_BuffersData = dict()
g_UsePolling = False

#Constants
VT_ISOUND_CREATE = 3
VT_ISBUFFER_GETPOS = 4
VT_ISBUFFER_INIT = 10
VT_ISBUFFER_SETFORMAT = 14
VT_ISBUFFER_UNLOCK = 19
S_OK = 0
DS_OK = 0
IDSOUND_ID = "{0F0F0F0F-113A-4832-9104-000000000002}"
IDSOUNDBUFFER_ID = "{0F0F0F0F-113A-4832-9104-000000000003}"

#Storage class
class BufferData(object):
    def __init__(self, address = 0, buffer_size = 0):
        self.buffer_address = address
        self.buffer_size = buffer_size
        self.chunks = []

#Inherit class to recieve DirectSound events:
class Listener(object):
    def OnBufferCreated(self, buffer_id, is_primary, flags, buffer_size):
        print "Sound buffer created: ", is_primary, " ", buffer_id

    def OnBufferInit(self, buffer_id, wave_format_ex):
        print "Sound buffer initialized"

    def OnBufferWritten(self, buffer_id, wav_data):
        print "Sound buffer written"

    def RaiseBufferWritten(self, buffer_id, chunk_list):
        for chunk in chunk_list:
            if (chunk == None):
                continue
            self.OnBufferWritten(buffer_id, chunk)

#Hook IDirectSoundBuffer Init, Unlock, SetFormat, GetCurrentPosition
def HookISoundBuffer(proc, vt):
    global g_ISoundBuffer_Hooked
    global g_Handlers
    if (g_ISoundBuffer_Hooked):
        return
    table = [[IDSOUNDBUFFER_ID, vt, VT_ISBUFFER_UNLOCK, CALL_DEFAULT, DSBufferUnlockHandler],
             [IDSOUNDBUFFER_ID, vt, VT_ISBUFFER_INIT, CALL_AFTER, DSBufferInitHandler],
             [IDSOUNDBUFFER_ID, vt, VT_ISBUFFER_SETFORMAT, CALL_AFTER, DSBufferSetFormatHandler],
             [IDSOUNDBUFFER_ID, vt, VT_ISBUFFER_GETPOS, CALL_AFTER, DSBufferGetPositionHandler]]
    for ti in table:
        h = HookMember(proc, ti[0], ti[1], ti[2], ti[3], ti[4])
        g_Handlers.append(h)
    g_ISoundBuffer_Hooked = True

#Hook IDirectSound CreateBuffer
def HookISound(proc_name, vt):
    global g_ISound_Hooked
    global g_Handlers
    if (g_ISound_Hooked):
        return
    h = HookMember(proc_name, IDSOUND_ID, vt, VT_ISOUND_CREATE, CALL_AFTER, DSoundCreateBufferHandler)
    g_Handlers.append(h)
    g_ISound_Hooked = True

#IDirectSoundBuffer::GetCurrentPosition handler
class DSBufferGetPositionHandler(HookHandler):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.__last_pos = None
        self.__proc_mem = None
        self.__dump_ix = 0

    def PyFunctionCalled(self, proc, ci, rc):
        if (not g_UsePolling):
            return
        if self.__proc_mem == None:
            self.__proc_mem = proc.RawMemory
        pms = ci.Params
        pThis = pms.Item(0).Value
        pos_read = self.__read_pointer(pms.Item(1))
        pos_write = self.__read_pointer(pms.Item(2))
        self.__update_pointers(pThis, pos_read, pos_write)

    def __update_pointers(self, buffer_id, pos_read, pos_write):
        global g_Listener
        global g_BuffersData
        #Init last_pos with the current write pointer
        curr_pos = pos_write

        if self.__last_pos == None:
            self.__last_pos = curr_pos
            return
        last_pos = self.__last_pos

        #Skip if nothing was written
        if curr_pos == last_pos:
            return

        dsbuffers = g_BuffersData
        if (not dsbuffers.has_key(buffer_id)):
            print "unable to update buffer data: %X" %(buffer_id)
            return
        base_ptr = dsbuffers[buffer_id].buffer_address
        buffer_size = dsbuffers[buffer_id].buffer_size

        #Calc necesary chunks:
        chunk_sz = (buffer_size >> 5)
        assert(chunk_sz > 0)
        chunk_mx = buffer_size/chunk_sz
        #Skip small changes in offsets
        if abs(curr_pos - last_pos) < chunk_sz:
            return

        chunk_ix = last_pos / chunk_sz
        chunk_ex = curr_pos / chunk_sz
        chunk_rg = None
        if chunk_ex > chunk_ix:
            chunk_rg = range(chunk_ix, chunk_ex)
        else:
            r1 = range(chunk_ix, chunk_mx)
            r2 = range(chunk_ex)
            r1.extend(r2)
            chunk_rg = r1
        
        #Read chunks
        for ix in chunk_rg:
            mem = self.__proc_mem
            ptr = base_ptr + (ix * chunk_sz)
            wave = ReadBuffer(mem, ptr, chunk_sz)
            dsbuffers[buffer_id].chunks.append(wave)

        #Flush the cache
        chunks = dsbuffers[buffer_id].chunks
        if len(chunks) > buffer_size/chunk_sz - 1:
           g_Listener.RaiseBufferWritten(buffer_id, chunks)
           dsbuffers[buffer_id].chunks = []
            
        #Store last offset
        self.__last_pos = curr_pos


    def __read_pointer(self, pm):
        ret = None
        pm = pm.CastTo("int*")
        if (pm.Value != 0):
           pm = pm.Evaluated
           ret = pm.Value
        return ret

#IDirectSoundBuffer::Initialize handler
class DSBufferInitHandler(HookHandler):

   def PyFunctionCalled(self, proc, ci, rc):
      global g_Listener
      pm = ci.Params.Item(2)
      pm = pm.CastTo("LPCDSBUFFERDESC")
      pm = pm.Evaluated
      pm = pm.Fields.Item(4) # LPWAVEFORMATEX
      if (pm.Value == 0):
          return
      pm = pm.Evaluated
      raw_mem = pm.RawMemory
      buffer = ReadBuffer(raw_mem, 0, pm.Size)
      wf = WaveFormatEx.Create(buffer)
      if (wf != None):
          g_Listener.OnBufferInit(buffer_id, wf)

#IDirectSoundBuffer::SetFormat handler
class DSBufferSetFormatHandler(HookHandler):

   def PyFunctionCalled(self, proc, ci, rc):
      global g_Listener
      pms = ci.Params
      buffer_id = pms.Item(0).Value
      pm = pms.Item(1)
      pm = pm.CastTo("LPCWAVEFORMATEX")
      pm = pm.Evaluated
      buffer = ReadBuffer(pm.RawMemory, 0, pm.Size)
      wf = WaveFormatEx.Create(buffer)
      if (wf != None):
          g_Listener.OnBufferInit(buffer_id, wf)

#IDirectSoundBuffer::Unlock handler            
class DSBufferUnlockHandler(HookHandler):
   def __init__(self):
       super(self.__class__, self).__init__()
       self.proc_mem = None
       self.calls = dict()

   def PyFunctionCalled(self, proc, ci, rc):
      global g_Listener
      global g_BuffersData
      global g_UsePolling

      cookie = ci.Cookie
      pms = ci.Params
      buffer_id = pms.Item(0).Value
      
      #Store buffer address and size:
      if g_UsePolling:
         buffer_1 = pms.Item(1).Value
         buffer_1_len = pms.Item(2).Value
         dsbuffers = g_BuffersData 
         if (not dsbuffers.has_key(buffer_id) ):
             #On the first call the full buffer is referenced
             dsbuffers[buffer_id] = BufferData(buffer_1, buffer_1_len)
         return
      
      if (ci.HookFlags == CALL_BEFORE):
         buffer_1 = pms.Item(1).Value
         buffer_1_len = pms.Item(2).Value
         buffer_2 = pms.Item(3).Value
         buffer_2_len = pms.Item(4).Value

         raw_mem = proc.RawMemory
         cache_1 = ReadBuffer(raw_mem, buffer_1, buffer_1_len)
         cache_2 = ReadBuffer(raw_mem, buffer_2, buffer_2_len)
         self.calls[cookie] = [ cache_1, cache_2 ]
      else:
         ret = ci.ReturnValue
         call_data = self.calls.pop(cookie, None)
         if (ret == DS_OK) and (call_data != None):
            g_Listener.RaiseBufferWritten(buffer_id, [call_data[0], call_data[1]])

#IDirectSound::CreateSoundBuffer
class DSoundCreateBufferHandler(HookHandler):
    def PyFunctionCalled(self, proc, ci, rc):
        if (ci.ReturnValue != S_OK):
            return

        #Read Settings:
        is_primary = True
        waveFormat = None
        pm = ci.Params.Item(1)
        pm = pm.CastTo("LPCDSBUFFERDESC") #pm.Evaluated
        pm = pm.Evaluated
        flags = pm.Fields.Item(1).Value # dwFlags
        buffer_size = pm.Fields.Item(2).Value #
        pm = pm.Fields.Item(4) # LPWAVEFORMATEX
        if (pm.Value != 0):
            pm = pm.Evaluated
            raw_mem = pm.RawMemory
            buffer = ReadBuffer(raw_mem, 0, pm.Size)
            wf = WaveFormatEx.Create(buffer)
            waveFormat = wf
            is_primary = False
        
        #Get buffer 'id'
        pms =  ci.Params
        pm = pms.Item(2) #DirectSoundBuffer**
        pm = pm.CastTo("int*")                   
        pm = pm.Evaluated
        buffer_id = pm.Value

        #Hook ISoundBuffer
        pm = pm.CastTo("int*")                   
        pm = pm.Evaluated
        vt = pm.Value
        HookISoundBuffer(proc.Name, vt)

        #Report Event:
        g_Listener.OnBufferCreated(buffer_id, is_primary, flags, buffer_size)
        if (waveFormat != None):
            g_Listener.OnBufferInit(buffer_id, waveFormat)

#dsound.dll!CreateDirectSound() handler
class DSoundHandler(HookHandler):
    def PyFunctionCalled(self, proc, ci, rc):
        retVal = ci.ReturnValue
        if (retVal != S_OK): #success from DirectSoundCreate
            return

        pms = ci.Params
        pm = pms.Item(1).Evaluated
        pm = pm.CastTo("int*")
        pm = pm.Evaluated
        vt = pm.Value
        HookISound(proc.Name, vt)

#Load directsound and find vtables to use in remote process:
def FindAndHookVTables(proc_name):
    helper = ctypes.windll.DeviareDirectSoundHelper
    vt_IS = helper.GetISoundVTable()
    vt_ISB = helper.GetISoundBufferVTable()
    if (vt_IS == 0 or vt_ISB == 0):
        print "Failed to obtain DirectSound vtables"
        return
    HookISound(proc_name, vt_IS)
    HookISoundBuffer(proc_name, vt_ISB)

#Hook Interfaces as they are discovered:
def HookOnDemand(proc_name):
    h = HookProcess(proc_name, "dsound.dll!DirectSoundCreate", CALL_AFTER, DSoundHandler)
    g_Handlers.append(h)
    h = HookProcess(proc_name, "dsound.dll!DirectSoundCreate8", CALL_AFTER, DSoundHandler)
    g_Handlers.append(h)

## Hook direct sound and start monitoring
def run_dispatch(proc_name, listener = Listener(), use_polling = False):
    assert( issubclass(listener.__class__, Listener) )
    global g_Handlers
    global g_Target_Process
    global g_Listener
    global g_UsePolling

    g_Target_Process = proc_name
    g_Listener = listener
    g_UsePolling = use_polling

    #This is a faster way to intercept calls right away. If this is not working for you,
    #comment this call and use the one below
    FindAndHookVTables(proc_name)

    #HookOnDemand(proc_name)
