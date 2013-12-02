import win32com.client
import ctypes
import sys

#Constants
CALL_BEFORE = 2
CALL_AFTER = 4
CALL_DEFAULT = CALL_BEFORE | CALL_AFTER
HOOK_INSTALL_IMMEDIATE = 262144

#Globals
g_SpyMgr = None
g_Hooks = []

#Handler for DHookEvents
class HookHandler(object):
    def __init__(self):
        print "HookHandler created"

    #private handlers
    def OnStateChanged(self, proc, newState, oldState):
        _proc_ = win32com.client.Dispatch(proc)
        self.PyStateChanged(_proc_, newState, oldState)

    def OnFunctionCalled(self, proc, callInfo, rCall):
    	_proc_ = win32com.client.Dispatch(proc)
    	_ci_ = win32com.client.Dispatch(callInfo)
    	_rc_ = win32com.client.Dispatch(rCall)
    	self.PyFunctionCalled(_proc_, _ci_, _rc_)

    def OnRemove(self):
    	self.PyRemove()

    #Override following functions to handle events:
    def PyStateChanged(self, proc, newState, oldState):
        print "state changed: ", newState

    def PyFunctionCalled(self, proc, callInfo, rCall):
        print "function called: ", self.__hookid__

    def PyRemove(self):
        print "hook removed"

#Handler for DHooksEvents
class HooksHandler(object):
    def __init__(self):
        print "Hooks handler created"

    #private handlers
    def OnStateChanged(self, hook, proc, newState, oldState):
        _hook_ = win32com.client.Dispatch(hook)
        _proc_ = win32com.client.Dispatch(proc)
        self.PyStateChanged(_hook_, _proc_, newState, oldState)

    def OnFunctionCalled(self, hook, proc, callInfo, rCall):
        _hook_ = win32com.client.Dispatch(hook)
        _proc_ = win32com.client.Dispatch(proc)
        _ci_ = win32com.client.Dispatch(callInfo)
        _rc_ = win32com.client.Dispatch(rCall)
        self.PyFunctionCalled(_hook_, _proc_, _ci_, _rc_)

    def OnRemove(self, hook):
        _hook_ = win32com.client.Dispatch(hook)
        self.PyRemove(_hook_)

    #Override following functions to handle events:
    def PyStateChanged(self, hook, proc, newState, oldState):
        print "state changed: ", newState

    def PyFunctionCalled(self, hook, proc, callInfo, rCall):
        print "function called: ", self.__hookid__

    def PyRemove(self, hook):
        print "hook removed"

#Handler for DComputerProcessesEvents
class ProcessesHandler(object):
      def __init__(self):
          print "Process handler created"
         
      #private handlers
      def OnProcessStarted(self, repMethod, newProc):
      	_proc_ = win32com.client.Dispatch(newProc)
      	self.PyProcessStarted(repMethod, _proc_)
      
      def OnProcessTerminated(self, repMethod, deadProc):
      	_proc_ = win32com.client.Dispatch(newProc)
      	self.PyProcessTerminated(repMethod, _proc_)

      def OnProcessMonitorMatch(self, proc, condition, callInfo):
      	_ci_ = win32com.client.Dispatch(callInfo)
      	_proc_ = win32com.client.Dispatch(newProc)
      	self.PyProcessMonitorMatch(_proc_, condition, _ci_)

      #Override following functions to handle events:
      def PyProcessMonitorMatch(self, proc, condition, callInfo):
      	print "process monitor match"
      	return

      def PyProcessTerminated(self, repMethod, deadProc):
          print "process terminated"
          return

      def PyProcessStarted(self, repMethod, newProc):
          print "process started"
          return

#Output handling class
class FileTunnel(object):
    def __init__(self, prev, file):
        self.prev = prev
        self.file = file

    def write(self, line):
        self.file.write(line)
        self.prev.write(line)

#Helpers:
def PrintParams(pms):
   for i in range(pms.Count):
      pm = pms.Item(i)
      print pm.Name, ": ", pm.Value

def SaveOutput():
    cout = sys.stdout
    cerr = sys.stderr
    file = open("deviare_output.txt", "w")
    sys.stdout = FileTunnel(cout, file)
    sys.stderr = FileTunnel(cerr, file)

def ReadBuffer(proc_mem, offset, size):
   mem_address = proc_mem.Address + offset
   if (mem_address == 0) or (size == 0):
      return
   try:
      raw_mem = ctypes.c_buffer(size)
      local_ptr = ctypes.addressof(raw_mem)
      read_size = proc_mem.Read(offset, size, local_ptr)
      #print "read from memory: 0x%x (0x%X)" %(mem_address, read_size)
      return raw_mem if (read_size > 0) else ctypes.c_buffer(0)
   except:
      print "ups, cannot read buffer: 0x%x" % (mem_address), " size: ", size
      return

#Create a SpyMgr singleton
def CreateSpyMgr():
    global g_SpyMgr
    if g_SpyMgr == None:
        g_SpyMgr = win32com.client.Dispatch("Deviare.SpyMgr")
    return g_SpyMgr

#Find process by name
def GetProcess(process_name):
    spy = CreateSpyMgr()
    procs = spy.Processes
    procs.Refresh()
    target = procs.Item(process_name)
    if target == None:
        print "Process not found"
        return
    return target

#Simply hooks a process by name an connects events
def HookProcess(process_name, function_path, call_mode = CALL_DEFAULT, Klass = HookHandler):
    global g_Hooks
    spy = CreateSpyMgr()
    
    target = GetProcess(process_name)
    if target == None:
        print "Failed to install process"
        return

    hook = spy.CreateHook(function_path)
    hook.Properties = call_mode
    hook.Attach(target)
    handler = win32com.client.WithEvents(hook, Klass)
    if (handler == None):
        print "Failed to create handler"
        return

    handler.__hookid__ = process_name + ": " + function_path
    hook.Hook()
    g_Hooks.append(hook)
    return handler

#Hooks an object member function
def HookMember(process_name, interface_name, vtable, vt_index, call_mode = CALL_DEFAULT, Klass = HookHandler):
    global g_Hooks
    
    target = GetProcess(process_name)
    if (target == None):
        print "Failed to install hook"
        return
    
    spy = CreateSpyMgr()
    hook_info = spy.CreateHookInstallInfo()
    hook_info.VTableAddress = vtable
    hook_info.VtIndex = vt_index
    hook_info.DatabasePath = ":iid:" + interface_name
    
    hook = spy.CreateHook(hook_info)
    if (hook == None):
        print "Failed to install hook"
        return
    
    handler = win32com.client.WithEvents(hook, Klass)
    if (handler == None):
        print "Failed to create handler"
        return

    handler.__hookid__ = process_name + ": " + interface_name + ", ix: " + repr(vt_index)
    hook.Properties = call_mode # | HOOK_INSTALL_IMMEDIATE
    hook.Attach(target)
    hook.Hook()
    g_Hooks.append(hook)
    return handler    
                

def HookInterface(process_name, interface_name, vtable, range, call_mode = CALL_BEFORE, Klass = HookHandler):
    hooks = []
    for vt_index in range:
        h = HookMember(process_name, interface_name, vtable, vt_index, call_mode, Klass)
        hooks.append(h)
    return hooks
