# -*- coding: utf-8 -*-
import sys, os, subprocess, tempfile

def printHelp():
    print("                                                                                                                               ")    
    print("DESCRIPTION:                                                                                                                   ")
    print(" The HANA Dump Viewer helps analyzing SAP HANA dumps. It creates .dot files out of trace files. These .dot files can be viewed ")
    print(" in e.g. http://www.webgraphviz.com/. See also SAP Note 2491748.                                                              ")
    print("                                                                                                                               ")
    print("INPUT ARGUMENTS:                                                                                                               ")
    print("         *** DOT OPTIONS ***                                                                                                   ")
    print(" -md     make dot file(s) [true/false], create dot file(s) from the dump file(s), default: true                                ")
    print(" -pt     plot threads [true/false], show threads in the .dot file, default: false                                              ")
    print(" -fl     function length [int], how many characters the stack function should include, if negative everything until the        ")
    print("         first '(' will be included, note this might also influence how a stack box is identified (if -if = true), default: -1 ")
    print(" -if     id by function [true/false], true: a stack box will be identified based on its stack function                         ")
    print("                                      false: a stack box will be identified based on its hexagonal ID number                   ")
    print("         default: true  (i.e. by default function calls with different hexagonal ID number will only be shown by one box)      ")
    print(" -rh     remove hex [true/false], true: remove string '+0x___' (where the _s could be any character until a space) from the    ")
    print("         stack function, note this will influence how a stack box is identified if -fl is large enough, default: true          ")
    print(" -ps     plot stack IDs [true/false], show the hexagonal ID in the boxes (cannot be true if -if is true), default: false       ")
    print("         *** INDEXMANAGER WAIT DOT GRAPH ***                                                                                   ")
    print(" -mw     make wait dot graph [true/false], creates, an indexmanager_waitgraph_<dump file name>.dot file which is simply the    ")
    print("         content of the [INDEXMANAGER_WAITGRAPH] section in the dump file, default: false                                      ")  
    print("         *** VIEW OPTIONS ***                                                                                                  ")
    print(" -mv     make views [true/false], creates, in the <output directory, see -od>/VIEWS_<dump file name>/ a <view name>.csv file   ")
    print("         for all views under the [STATISTICS] section in the dump file, default: false                                         ")     
    print("         *** INPUT ***                                                                                                         ")
    print(" -nd     number indexserver dumpfiles from cdtrace to create .dot files for (cannot be used together with -df), default: 0     ")
    print(" -dt     dump type, the names of the dumpfiles used from cdtrace have to include this string, e.g. rte, crashdump, oom, etc.,  ")
    print("         this flag can only be used together with -nd, default: '' (i.e. all indexserver trace files)                          ")
    print(" -df     list of full path names of trace files with section STACK_SHORT, each trace file name, seperated by only a comma,     ")
    print("         will be used to create a .dot file, that can be viewed in  http://www.webgraphviz.com/  , default: '' (not used)      ")
    print("         *** OUTPUT ***                                                                                                        ")
    print(" -od     output directory, full path of the folder where all output files will end up (if not exist it will be created),       ")
    print("         default: '/<tempdir>/hanadumpviewer_output' where <tempdir> is automatically selected based on OS, for Windows        ")
    print("         it could be e.g. C:\TEMP, and for Linux it could be e.g. /tmp                                                         ")
    print("                                                                                                                               ")    
    print("                                                                                                                               ")
    print("EXAMPLE (create .dot files for the 5 latest created indexserver trace files in cdtrace, and show the threads):                 ")
    print("  > python hanadumpviewer.py -nd 5 -pt true                                                                                    ")    
    print("                                                                                                                               ")
    print("EXAMPLE (create .dot files for the 3 latest created out of memory indexserver trace files in cdtrace):                         ")
    print("  > python hanadumpviewer.py -nd 5 -dt oom                                                                                     ")    
    print("                                                                                                                               ")
    print("EXAMPLE (specify one trace file and choose to show the threads):                                                               ")
    print("  > python hanadumpviewer.py -df indexserver_ls80010.30003.rtedump.20170515-084744.019134.oom.trc -pt true                     ")
    print("                                                                                                                               ")
    print("EXAMPLE (create dot files from two trace files without showing the threads):                                                   ")
    print("  > python hanadumpviewer.py -df indexserver_ls80010.30003.rtedump.oom.trc,indexserver_mo-fc8d991e0.30003.rtedump.trc          ")
    print("                                                                                                                               ")
    print(" KNOWN ISSUES:                                                                                                                 ")
    print(" * Does not support threads from Data Tiering (TODO)                                                                           ")
    print("                                                                                                                               ")
    print("AUTHOR: Christian Hansen                                                                                                       ")
    print("                                                                                                                               ")
    print("                                                                                                                               ")
    os._exit(1)

######################## DEFINE CLASSES ##################################
class StackThread:
    def __init__(self, threadId, threadType):
        self.id = threadId
        self.type = threadType
        self.lines = []
        self.isException = False
    def add_line(self, line):
        self.lines.append(line)
    def printThread(self):
        if self.isException:
            print "Exception ID: ", self.id, "  Exception Reason: ", self.type, "  Stack Lines:\n"
        else:
            print "Thread ID: ", self.id, "  Thread Type: ", self.type, "  Stack Lines:\n"
        print self.lines
        
        
class DotLine:
    def __init__(self, dotNumber, stackThreadId, function, idByFunction = False):
        self.dotNumber = dotNumber
        self.stackThreadId = stackThreadId  # if stack: hexagonal stack id, if thread: thread id
        if '_ZN' in function:   #fix uggly _ZN lines 
            function = function.split('ER')[0].strip('_ZNK').strip('_ZN')
            function = "".join(["::" if char.isdigit() else char for char in function])
            function = function.replace('::::','::').strip('::')
        self.function = function
        self.parentDotNumbers = []  
        self.usedByThreads = []
        self.isThread = False
        self.isException = False
        self.idByFunction = idByFunction
        self.red_scale = ['#ffffff', '#ffebeb', '#ffd8d8', '#ffc4c4', '#ffb1b1', '#ff9d9d', '#ff8989', '#ff7676', '#ff6262', '#ff4e4e', '#ff3b3b', '#ff2727', '#ff1414', '#ff0000']
    def getID(self):
        if self.isThread:
            return self.stackThreadId
        elif self.idByFunction:
            return self.function
        return self.stackThreadId
    def add_parent(self, parentDotNumber):
        self.parentDotNumbers.append(parentDotNumber)
    def add_parent_if_not_listed(self, parentDotNumber):
        if not parentDotNumber in self.parentDotNumbers:
            self.add_parent(parentDotNumber)
    def add_thread(self, usedByThread):
        self.usedByThreads.append(usedByThread)
    def add_thread_if_not_listed(self, usedByThread):
        if not usedByThread in self.usedByThreads:
            self.add_thread(usedByThread)
    def color(self, maxNbrThreads = 1):
        if self.isThread:
            return '#00ffff'  #cyan
        if self.isException:
            return '#ffa500'  #orange
        return self.red_scale[ int(float(len(self.usedByThreads)) / float(maxNbrThreads) * (len(self.red_scale)-1)) ]  
    def setIsThread(self, isThread):
        self.isThread = isThread
        self.testThreadType()
    def setIsException(self, isException):
        self.isException = isException
        self.testThreadType()
    def testThreadType(self):
        if self.isThread and self.isException:
            print "ERROR: Something Went Wrong: A DotLine can only be either a normal thread or a exception thread."
            os._exit(1)
    def printDotLine(self):
        if self.isThread:            
            print "Dot Line Number: ", self.dotNumber, "  Thread ID: ", self.stackThreadId, "  Thread Type: ", self.function, "  Parent Dot Numbers:", self.parentDotNumbers
        elif self.isException:
            print "Dot Line Number: ", self.dotNumber, "  Exception ID: ", self.stackThreadId, "  Exception Reason: ", self.function, "  Parent Dot Numbers:", self.parentDotNumbers
        else:
            print "Dot Line Number: ", self.dotNumber, "  Stack ID: ", self.stackThreadId, "  Code Function: ", self.function, "  Parent Dot Numbers:", self.parentDotNumbers
        
######################## DEFINE FUNCTIONS ################################

def is_integer(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def findDotLineNumber(searchId, dotLines):
    for dotLine in dotLines:
        if not dotLine.isThread:
            if searchId == dotLine.getID():
                return dotLine.dotNumber
    return -1

def checkAndConvertBooleanFlag(boolean, flagstring):     
    boolean = boolean.lower()
    if boolean not in ("false", "true"):
        print "INPUT ERROR: ", flagstring, " must be either 'true' or 'false'. Please see --help for more information."
        os._exit(1)
    boolean = True if boolean == "true" else False
    return boolean
    
def cdtrace():
    command_run = subprocess.check_output(['/bin/bash', '-i', '-c', "alias cdtrace"])
    pieces = command_run.strip("\n").strip("alias cdtrace=").strip("'").strip("cd ").split("/")
    path = ''
    for piece in pieces:
        if piece[0] == '$':
            piece = (subprocess.check_output(['/bin/bash', '-i', '-c', "echo "+piece])).strip("\n")
        path = path + '/' + piece + '/' 
    return path
   
#def readStackLines(dumpfile):    
#    inStack = False
#    stackLines = []
#    try:
#        with open(dumpfile, 'r') as fin:
#            for line in fin:
#                if not inStack and '[STACK_SHORT]' in line and 'Local' in line:
#                    inStack = True
#                if inStack and '[OK]' in line:
#                    inStack = False
#                if inStack:
#                    stackLines.append(line)
#    except:
#        print "ERROR: The file "+dumpfile+" could not be opened."
#        os._exit(1)
#    if not stackLines:
#        print "WARNING: The file "+dumpfile+" has no short stack section."
#    return stackLines
    
def readSectionLines(dumpfile, section):
    if section[0] != '[' and section[-1] != ']':
        print "ERROR: section does not start and end with square brackets."
        os._exit(1)
    inSection = False
    sectionLines = []
    try:
        with open(dumpfile, 'r') as fin:
            for line in fin:
                if not inSection and section in line and 'Local' in line:
                    inSection = True
                if inSection and '[OK]' in line:
                    inSection = False
                if inSection:
                    sectionLines.append(line)
    except:
        print "ERROR: The file "+dumpfile+" could not be opened."
        os._exit(1)
    if not sectionLines:
        print "WARNING: The file "+dumpfile+" has no "+section+" section."
    return sectionLines
    
def createThreads(stackLines):
    inThread = False
    threads = []
    nNormalThreads = 0
    nExceptThreads = 0
    for line in stackLines:
        threadStart = '[thr=' in line and not 'inactive' in line
        exceptStart = 'Allocation failed' in line
        threadStop = line == '--\n' or ('exception' in line and 'no.' in line)
        exceptStop = line == '\n' or line == '--\n'
        exceptFirst = 'exception throw location' in line
        if not inThread and (threadStart or exceptStart):
            inThread = True
            if threadStart:
                threadId = line.split('[thr=')[1].split(']: ')[0]
                threadType = line.split(']: ')[1].split(' at')[0]
                nNormalThreads += 1
            else: 
                threadId = str(nExceptThreads)
                threadType = line.strip(' ').replace('$','').replace('\n','') #aka reason
                nExceptThreads += 1
            thread = StackThread(threadId, threadType)
            if exceptStart:
                thread.isException = True
            threads.append(thread)
        elif inThread and (threadStop or exceptStop):
            inThread = False
        elif inThread and not exceptFirst:
            if not ' in ' in line:
                print "ERROR: Something went wrong, in thread the line should here be a normal stack line, i.e. include ' in ', line = \n", line
                os._exit(1)       
            threads[len(threads)-1].add_line(line)
    if not threads:
        print "ERROR: No threads were created"
        os._exit(1)
    return [threads, nNormalThreads, nExceptThreads]
            
def splitStackLine(stackLine, functionLength, removeHexFromFunction):
    splitter = ' in unsigned long ' if ' in unsigned long ' in stackLine else ' in '
    stackLineId = stackLine.split(splitter)[0].strip(' ').split(' ')[1]
    stackLineFunction = stackLine.split(splitter)[1].strip(' ')
    if functionLength < 0:
        stackLineFunction = stackLineFunction.split('(')[0]
    else:
        stackLineFunction = stackLineFunction[:functionLength]
        if removeHexFromFunction:
            startHex = stackLineFunction.find('+0x')
            if startHex >= 0:
                endHex = stackLineFunction[startHex:].find(' ')
                if endHex >= 0:
                    hexString = stackLineFunction[startHex:][:endHex]
                else:
                    hexString = stackLineFunction[startHex:]
                stackLineFunction = stackLineFunction.replace(hexString, '')
    stackLineFunction = stackLineFunction.replace('<','&lt;').replace('>','&gt;').strip('\n')
    return [stackLineId, stackLineFunction]

def createDotLines(threads, plot_threads, functionLength, removeHexFromFunction, id_by_function):
    dotLineNumber = 0
    dotLines = []
    maxNbrThreads = 0
    for thread in threads:
        dotLineNumberOfPrevStackLine = -1
        if plot_threads:
            dotLine = DotLine(dotLineNumber, thread.id, thread.type)
            dotLine.add_parent(dotLineNumberOfPrevStackLine)   
            dotLine.add_thread(thread.id)
            dotLine.setIsThread(not thread.isException)
            dotLine.setIsException(thread.isException)
            dotLines.append(dotLine)
            dotLineNumberOfPrevStackLine = dotLineNumber
            dotLineNumber += 1   # dotLineNumber is also the index in dotLines
        for stackLine in thread.lines:
            [stackLineId, stackLineFunction] = splitStackLine(stackLine, functionLength, removeHexFromFunction)
            searchId = stackLineFunction if id_by_function else stackLineId
            dotLineNumberWithThisDotId = findDotLineNumber(searchId, dotLines)
            if dotLineNumberWithThisDotId < 0:  #then there is no dotline from this stackline yet
                dotLine = DotLine(dotLineNumber, stackLineId, stackLineFunction, id_by_function)
                dotLine.add_parent(dotLineNumberOfPrevStackLine)
                dotLine.add_thread(thread.id)
                maxNbrThreads = max(len(dotLine.usedByThreads), maxNbrThreads)
                dotLines.append(dotLine)
                dotLineNumberOfPrevStackLine = dotLineNumber
                dotLineNumber += 1   # dotLineId is also the index in dotLines
            else:
                dotLines[dotLineNumberWithThisDotId].add_parent_if_not_listed(dotLineNumberOfPrevStackLine)
                dotLines[dotLineNumberWithThisDotId].add_thread_if_not_listed(thread.id)
                maxNbrThreads = max(len(dotLines[dotLineNumberWithThisDotId].usedByThreads), maxNbrThreads)
                dotLineNumberOfPrevStackLine = dotLineNumberWithThisDotId
    if not dotLines:
        print "ERROR: No dot lines were created"
        os._exit(1)
    if not maxNbrThreads:
        print "ERROR: maxNbrThreads = ", maxNbrThreads
        os._exit(1)
    return [dotLines, maxNbrThreads]

def writeDotFile(dotLines, maxNbrThreads, plot_threads, plot_stack_id, nNormalThreads, nExceptThreads, dumpfile, out_dir):
    #outfilename = out_dir+"/"+dumpfile.split('/')[-1]+".dot"    
    outfilename = os.path.join(out_dir,dumpfile[dumpfile.rfind(os.path.sep)+1:]+".dot")     
    dotfile = open(outfilename, "w")
    dotfile.write("digraph StackGraph {\n")
    dotfile.write("ratio=compress\n")  
    dotfile.write("rankdir=BT\n")        # maybe skipp this line
    normalThreadLegend = ''
    exceptThreadLegend = ''
    if plot_threads:
        if nNormalThreads:
            normalThreadLegend = '|{'+str(nNormalThreads)+' Normal Threads (cyan boxes)}'
        if nExceptThreads:
            exceptThreadLegend = '|{'+str(nExceptThreads)+' Exception Threads (orange boxes)}'
    dotfile.write('nlegend [shape=record,label="{{#T = Number threads executing the stack process}'+normalThreadLegend+exceptThreadLegend+'}",style=filled,fillcolor="#ffff00",fontname=sans];\n')
    for dotLine in dotLines:
        dotfile.write("nC"+str(dotLine.dotNumber)+"\n")
        if plot_threads and dotLine.isThread:
            dotfile.write('[shape=record,label="{Thread ID: '+dotLine.stackThreadId + r'\nThread Type: '+dotLine.function+'}",style=filled,fillcolor="'+dotLine.color()+'",fontname=sans];\n')
        elif plot_threads and dotLine.isException:
            dotfile.write('[shape=record,label="{Exception ID: '+dotLine.stackThreadId + r'\nReason: '+dotLine.function+'}",style=filled,fillcolor="'+dotLine.color()+'",fontname=sans];\n')
        elif not plot_threads and dotLine.parentDotNumbers[0] == -1:
            id_and_func = dotLine.function + r'\n' + dotLine.stackThreadId if plot_stack_id else dotLine.function
            dotfile.write('[shape=record,color=blue,penwidth=5,label="{'+id_and_func+ r'\n#T='+str(len(dotLine.usedByThreads))+'}",style=filled,fillcolor="'+dotLine.color(maxNbrThreads)+'",fontname=sans];\n')
        else:
            id_and_func = dotLine.function + r'\n' + dotLine.stackThreadId if plot_stack_id else dotLine.function
            dotfile.write('[shape=record,label="{'+id_and_func+ r'\n#T='+str(len(dotLine.usedByThreads))+'}",style=filled,fillcolor="'+dotLine.color(maxNbrThreads)+'",fontname=sans];\n')
    for dotLine in dotLines:
        for parentDotNumber in dotLine.parentDotNumbers:
            if not parentDotNumber == -1:
                dotfile.write('nC'+str(dotLine.dotNumber)+' -> nC'+str(parentDotNumber)+'\n')
    dotfile.write('}')
    dotfile.close()
    print "File "+outfilename+" was created"    

def makeWaitGraph(dumpfile, out_dir):
    waitLines = readSectionLines(dumpfile, '[INDEXMANAGER_WAITGRAPH]')
    waitfile = open(out_dir+'/indexmanager_waitgraph_'+dumpfile.replace('.','_')+'.dot', "w")
    for line in waitLines[1:]:
        waitfile.write(line)
    waitfile.close()

def makeViews(dumpfile, out_dir):
    view_directory = out_dir+'/VIEWS_'+dumpfile.split('/')[-1].replace('.','_')
    if not os.path.exists(view_directory):
        os.makedirs(view_directory)
    statLines = readSectionLines(dumpfile, '[STATISTICS]')
    outside_view = True
    for line in statLines:
        if outside_view:
            words = line.split(' ')
            if len(words) > 1:
                if words[1] == '-': # View starts
                    view = words[0]
                    outside_view = False        
                    viewfile = open(view_directory+'/'+view+'.csv', "w")               
        elif line.startswith("("+view+","):   # View ends
            outside_view = True
            viewfile.close()
        else:  # Inside view
             viewfile.write(line)                       

def main():
    #####################  CHECK PYTHON VERSION ###########
    if sys.version_info[0] != 2 or sys.version_info[1] != 7:
        print "VERSION ERROR: hanacleaner is only supported for Python 2.7.x. Did you maybe forget to log in as <sid>adm before executing this?"
        os._exit(1)

    #####################   DEFAULTS   ####################
    make_dots = 'true'    
    plot_threads = 'false'
    functionLength = '-1'
    id_by_function = 'true'
    removeHexFromFunction = 'true'
    plot_stack_id = 'false'
    make_wait_graph = 'false'
    make_views = 'false'
    nbrDumpFiles = '0'
    dumptype = ''    
    dumpfiles = []
    out_dir = os.path.join(tempfile.gettempdir(),"hanadumpviewer_output")
    
    #####################  CHECK INPUT ARGUMENTS #################
    if len(sys.argv) == 1:
        print "INPUT ERROR: hanadumpviewer needs input arguments. Please see --help for more information."
        os._exit(1) 
    if len(sys.argv) != 2 and len(sys.argv) % 2 == 0:
        print "INPUT ERROR: Wrong number of input arguments. Please see --help for more information."
        os._exit(1)
    for i in range(len(sys.argv)):
        if i % 2 != 0:
            if sys.argv[i][0] != '-':
                print "INPUT ERROR: Every second argument has to be a flag, i.e. start with -. Please see --help for more information."
                os._exit(1)    
    
    #####################   INPUT ARGUMENTS   ####################     
    if '-h' in sys.argv or '--help' in sys.argv:
        printHelp()
    if '-md' in sys.argv:
        make_dots = sys.argv[sys.argv.index('-md') + 1]
    if '-pt' in sys.argv:
        plot_threads = sys.argv[sys.argv.index('-pt') + 1]
    if '-fl' in sys.argv:
        functionLength = sys.argv[sys.argv.index('-fl') + 1]
    if '-if' in sys.argv:
        id_by_function = sys.argv[sys.argv.index('-if') + 1]
    if '-rh' in sys.argv:
        removeHexFromFunction = sys.argv[sys.argv.index('-rh') + 1]
    if '-ps' in sys.argv:
        plot_stack_id = sys.argv[sys.argv.index('-ps') + 1]
    if '-mw' in sys.argv:
        make_wait_graph = sys.argv[sys.argv.index('-mw') + 1]
    if '-mv' in sys.argv:
        make_views = sys.argv[sys.argv.index('-mv') + 1]
    if '-nd' in sys.argv:
        nbrDumpFiles = sys.argv[sys.argv.index('-nd') + 1]
    if '-dt' in sys.argv:
        dumptype = sys.argv[sys.argv.index('-dt') + 1]
    if '-df' in sys.argv:
        dumpfiles = [x for x in sys.argv[  sys.argv.index('-df') + 1   ].split(',')]
    if '-od' in sys.argv:
        out_dir = sys.argv[sys.argv.index('-od') + 1]

    ############# OUTPUT DIRECTORY #########
    out_dir = out_dir.replace(" ","_").replace(".","_")
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
 
    ############ CHECK AND CONVERT INPUT PARAMETERS ################
    ### make_dots, -md
    make_dots = checkAndConvertBooleanFlag(make_dots, "-md")    
    ### plot_threads, -pt
    plot_threads = checkAndConvertBooleanFlag(plot_threads, "-pt")
    ### functionLength, -fl 
    if not is_integer(functionLength):
        print "INPUT ERROR: -fl must be an integer. Please see --help for more information."
        os._exit(1)
    functionLength = int(functionLength)
    ### id_by_function, -if
    id_by_function = checkAndConvertBooleanFlag(id_by_function, "-if")
    ### removeHexFromFunction, -rh
    removeHexFromFunction = checkAndConvertBooleanFlag(removeHexFromFunction, "-rh")
    ### plot_stack_id, -ps
    plot_stack_id = checkAndConvertBooleanFlag(plot_stack_id, "-ps")
    if plot_stack_id and id_by_function:
        print "INPUT ERROR: both -ps and -if cannot be true together. Please see --help for more information"
        os._exit(1)
    ### make_wait_graph, -mw
    make_wait_graph = checkAndConvertBooleanFlag(make_wait_graph, "-mw")
    ### make_views, -mv
    make_views = checkAndConvertBooleanFlag(make_views, "-mv")
    ### nbrDumpFiles, -nd 
    if not is_integer(nbrDumpFiles):
        print "INPUT ERROR: -nd must be an integer. Please see --help for more information."
        os._exit(1)
    nbrDumpFiles = int(nbrDumpFiles)
    ### dumptype, -dt
    if dumptype and not nbrDumpFiles:
        print "INPUT ERROR: -dt can only be specified if -nd is. Please see --help for more information."
        os._exit(1)
    ### dumpfiles, -df 
    if dumpfiles and nbrDumpFiles:
        print "INPUT ERROR: -nd and -df cannot be used together. Please see --help for more information."
        os._exit(1)

    ############# DUMPFILES FROM CDTRACE ###################
    if nbrDumpFiles:
        dumpfiles = subprocess.check_output('ls '+cdtrace()+'/indexserver_*'+dumptype+'*.trc | head -'+str(nbrDumpFiles), shell=True).splitlines(1)
        dumpfiles = [dumpfile.strip('\n') for dumpfile in dumpfiles]
    
    ################ START #################
    if make_dots:    
        for dumpfile in dumpfiles:
            stackLines = readSectionLines(dumpfile, '[STACK_SHORT]')
            if stackLines:
                [threads, nNormalThreads, nExceptThreads] = createThreads(stackLines)          
                [dotLines, maxNbrThreads] = createDotLines(threads, plot_threads, functionLength, removeHexFromFunction, id_by_function)          
                writeDotFile(dotLines, maxNbrThreads, plot_threads, plot_stack_id, nNormalThreads, nExceptThreads, dumpfile, out_dir) 
    if make_wait_graph:
        for dumpfile in dumpfiles:
            makeWaitGraph(dumpfile, out_dir)
    if make_views:
        for dumpfile in dumpfiles:
            makeViews(dumpfile, out_dir)
    
              
if __name__ == '__main__':
    main()
                        

