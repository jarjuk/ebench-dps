from ebench import Instrument
from ebench import MenuCtrl

from ebench import usage, usageCommand, menuStartRecording, menuStopRecording, menuScreenShot

from ebench import version as ebenchVersion

# wraps https://forum-raspberrypi.de/forum/thread/46324-ansteuerung-programmierbarer-stepdown-regler-dps/
from .dps_modbus import serial_ports, Serial_modbus, Import_limits, Dps5005

import os
import sys
from time import sleep
from absl import logging
import csv
from functools import reduce

# ------------------------------------------------------------------
# Usage 
CMD="ebenchDps"

SYNOPSIS="Control DPS8020 Digital Power Supply"

USAGE_TEXT = """

The tool :

- query Digital Power supply status e.g. voltage/current setpoint
- configure voltage and current setpoint
- turn output on and off
- use CSV file to generate output voltage output

"""

# ------------------------------------------------------------------
# delegation pattern

# https://gist.github.com/kkew3/2d61463397a77a898be12ac766c31c12
def delegates(method_names, to):
    def dm(method_name):
        def fwraps(self, *args, **kwargs):
            wrappedf = getattr(getattr(self, to), method_name)
            return wrappedf(*args, **kwargs)
        fwraps.__name__ = method_name
        return fwraps
    def cwraps(cls):
        for name in method_names:
            setattr(cls, name, dm(name))
        return cls
    return cwraps


@delegates( ["read", "read_block", "write", "write_block", ], to="ser")
class ModbusInstrument(Instrument):
    """Abstract class for an instrument, which can be controlled using
    modbus interface.

    Wraps 'dps_modbus.Serial_modbus' -class in property 'ser'

    """

    def __init__(self, port, addr=1, baud_rate=9600, byte_size=8):
        self.ser = Serial_modbus( port1=port, addr=addr, baud_rate=baud_rate, byte_size=byte_size)
        
    # .................................
    # properties

    @property
    def ser(self) -> Serial_modbus :
        if not hasattr(self, "_ser"):
             return None
        return self._ser

    @ser.setter
    def ser( self, ser:Serial_modbus):
        self._ser = ser

@delegates( ["read_all"
             , "function"
             , "functions"
             , "voltage_in"
             , "voltage_set"
             , "current_set"
             , "delay"
             # , "voltage"
             # , "current"
             , "version"
             # , "lock"
             # , "protect"
             , "model"
             # , "cv_cc"
             , "onoff"], to="dps") # using dps_modbus.Dps5005 class methods
class DPSApi(ModbusInstrument):
    """
    Instrument API services
    """

    def __init__(self, port:str, addr:int=1, propertiesPath = "dps8020.ini"):
        super().__init__(port=port, addr=addr)
        self.limits = Import_limits( propertiesPath )
        self.dps = Dps5005(self, self.limits)

    # .................................
    # properties

    @property
    def limits(self) -> Import_limits :
        if not hasattr(self, "_limits"):
             return None
        return self._limits

    @limits.setter
    def limits( self, limits:Import_limits):
        self._limits = limits

    @property
    def dps(self) -> Dps5005 :
        if not hasattr(self, "_dps"):
             return None
        return self._dps

    @dps.setter
    def dps( self, dps:Dps5005):
        self._dps = dps


class DPSInstrument(DPSApi):
    """
    Facade presented to user.

    """
    
    CSV_COLUMNS=["step_time", "voltage", "current"]
    
    def __init__(self, port:str):
        super().__init__(port=port)

    # ------------------------------------------------------------------
    # Genral utilities
        

    def isTrueOrFalse( self,value:str )-> bool:
        if value is None or not value: return False
        if value.upper() in [ "T", "Y", "TRUE", "ON","YES", "1", "K" ]: return True
        return False

    
    def csv2dict( self, filePath:str, delimiter=",") -> dict:
        """Slurp CSV -file in 'filePath' into dictionary mapping header
        columns to data-arrays

        :return: Dict[str,List]

        """
        with open( filePath, mode="r") as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=delimiter)
            line_count = 0
            csvDict = None
            for row in csv_reader:
                logging.debug( "csv2dict: row={}".format(row) )
                if line_count == 0:
                    csvDict = { k: [v] for k,v in row.items()}
                else:
                    for i,key in enumerate(row.keys()):
                        csvDict[key].append(row[key])
                line_count += 1
            return csvDict

    def spinner(self,value="."):
        """Output spinner 'value' indicating progress 

        """
        print( value, end="")
        sys.stdout.flush()


    # ------------------------------------------------------------------
    # User facade
    def lese(self):
        """
        Return DPS status as a JSON document with fields:

        - U_set: Voltage setpoint
        - I_set: Current setpoint
        - U_out: Output voltage display value
        - I_out: Output current display value
        - P_out: Output power  display value
        - U_in: input voltage
        - onoff: Output on/off
        - lock: Key lock
        - protect: Protection status
        - cv/cc: Constant Voltage / Constant Current status
        - on/off: switch output state
        - b_led: backligh brighness level
        - model: product model
        - version: firmware version
        
        """
        readArr = self.read_all()
        # ref. API https://www.mediafire.com/file/tw96e28oggw7dai/DPS5020_CNC_Communication__Protocol_V1.2.pdf
        # Register Map for this device
        retJson = {
            "U_set": readArr[0],
            "I_set": readArr[1],
            "U_out": readArr[2],
            "I_out": readArr[3],
            "P_out": readArr[4],
            "U_in": readArr[5],
            "lock": readArr[6],
            "protect": readArr[7],
            "cv/cc": readArr[8],
            "onoff": readArr[9],
            "b_led": readArr[10],
            "model": readArr[11],
            "version": readArr[12],
        }
        return retJson


    def set(self, U_set=None, I_set=None ):
        """Configure voltage and current setpoints on DPS. Does NOT change
         output status.

        """
        logging.info( "set: U_set={}, I_set={}".format(U_set, I_set) )
        if not not U_set and U_set is not None:
            self.voltage_set( RWaction="w", value=float(U_set))
        if not not I_set and I_set is not None:
            self.current_set( RWaction="w", value=float(I_set))
            
    def on(self):
        """Turn output on
        """
        self.onoff(RWaction="w", value=1)
        
    def off(self):
        """Turn output off
        """
        self.onoff(RWaction="w", value=0)


    def info(self):
        """
        Returns JSON document with following fields
        
        - ebenchDps: ebenchDps application version string
        - dpsModel: DPS device model number
        - dpsVersion: DPS version number
        
        """
        jsonRet = {
            "ebenchDps": version(),
            "dpsModel": self.model(),
            "dpsVersion": self.version(),
        }
        return jsonRet

    

    def csv(self, filePath:str, on:str=None, delimiter:str=","):
        """
        Control devices using csvfile (default delimiter comma=,)

        Csv file header:

        - step_time:
        - voltage:
        - current: 

        Example CSV content


        step_time,voltage,current
        2,0.5,0.1
        3,2.5,0.2
        3,3.3,0.3

        
        """
        logging.info( "csv: filePath={}".format(filePath))

        # Read filePath into dictionary
        csvDict = self.csv2dict(filePath=filePath, delimiter=",")

        # Validate data
        if csvDict is None:
            raise ValueError( "Could not read csv from filePath={}".format(filePath))
        for col in DPSInstrument.CSV_COLUMNS:
            if col not in csvDict:
                raise ValueError( "Missing column {}, expect to have columns {} in CSV file {}".format(col, DPSInstrument.CSV_COLUMNS, csvDict.keys()))

            
        # Init, Start times && Looop
        self.delay(0.0)
        self.voltage_set( "w", 0.0)
        self.current_set( "w", 0.0)

        # Turn on - unless dry run
        if self.isTrueOrFalse(on): self.on()
        
        for i,step_time in enumerate(csvDict["step_time"]):
            # We are advancing
            self.spinner()
            # One step
            self.voltage_set( "w", float(csvDict["voltage"][i]) )
            self.current_set( "w", float(csvDict["current"][i]) )
            self.delay(float(step_time))

        # No output
        return None
    
# ------------------------------------------------------------------
# Module services
        
def dpsVersion():
    versionPath = os.path.join( os.path.dirname( __file__), "..", "VERSION")
    with open( versionPath, "r") as fh:
        version = fh.read().rstrip()
    return version

def version():
    return( "ebench.version={}, ebenchDps.version={}".format(ebenchVersion(), dpsVersion()))

def ttyShow(i):
    """List tty devices found"""
    ttys = serial_ports()
    if not not i and i is not None:
        return ttys[int(i)]
    else:
        return ",".join(ttys)
    
# ------------------------------------------------------------------
# Menu
CMD_STATUS="status"
CMD_SET="set"
CMD_ON="on"
CMD_OFF="off"
CMD_CSV="csv"

# Hidden commands
CMD_SHOW_TTYS="_ttys"
CMD_INFO="_info"

ttyShowPar = {
    'i':"Index to to show"
}
setPar = {
    'U_set':"Voltage to set",
    'I_set':"Current limit to set",
}

csvPar = {
    'filePath':"Path to CSV -file",
    'on':"Switch DPS on"
}


# Initial values for menu command parameters
defaults = {
    CMD_SET : {
        "U_set": 0.0,     # default && remember
        "I_set": 0.0,     # remember last value
    },
    CMD_CSV : {
        "on": "NO",       # default is not switch on
    },
}
    
# ------------------------------------------------------------------
# Bind instrument controller classes to ebench toolset
def run( _argv
         , port:str
         , runMenu:bool = True
         , outputTemplate=None, captureDir=None, recordingDir=None ):
    """Construct DPSIntrument for controlling DPS Digital Power Supply

    :port: device address of DPS mobbus interface

    :runMenu: default True, standalone application call REPL-loop
    'menuController.mainMenu()', subMenu constructs 'menuController'
    without executing the loop

    :outputTemplate: if None(default): execute cmds/args, else (not
    None): map menu actions to strings using 'outputTemplate'

    :recordingDir: directory where interactive session recordings are
    saved to (defaults to 'FLAGS.recordingDir')

    :captureDir: directory where screenshots are made, defaults to
    'FLAGS.captureDir'

    :return: MenuCtrl (wrapping instrument)

    """

    # 'instrument' controlled by application
    logging.info( "run: contstruct DPSInstrument, port={}".format(port))
    instrument = DPSInstrument(port=port) 

    # Wrap instrument with 'MenuCtrl'
    menuController = MenuCtrl( args=_argv,instrument=instrument
                             , prompt="[q=quit,?=commands,??=help on command]"
                             , outputTemplate=outputTemplate )

    mainMenu = {
        CMD                      : MenuCtrl.MENU_SEPATOR_TUPLE,
        # Application menu 
        # CMD_GREET                : ( "Say hello", greetPar, instrument.sayHello ),
        CMD_STATUS               : ("Read DSP status", None, instrument.lese ),
        CMD_SET                  : ("Configure", setPar, instrument.set ),
        CMD_ON                   : ("Turn on", None, instrument.on ),
        CMD_CSV                  : ("CSV driver", csvPar, instrument.csv ),        
        CMD_OFF                  : ("Turn off", None, instrument.off ),

        "Util"                   : MenuCtrl.MENU_SEPATOR_TUPLE,
        MenuCtrl.MENU_REC_START  : ( "Start recording", None, menuStartRecording(menuController) ),
        MenuCtrl.MENU_REC_SAVE   : ( "Stop recording", MenuCtrl.MENU_REC_SAVE_PARAM, menuStopRecording(menuController, recordingDir=recordingDir) ),
        MenuCtrl.MENU_SCREEN     : ( "Take screenshot", MenuCtrl.MENU_SCREENSHOT_PARAM,
                                     menuScreenShot(instrument=instrument,captureDir=captureDir,prefix="Capture-" )),
        MenuCtrl.MENU_HELP       : ( "List commands", None,
                                    lambda **argV: usage(cmd=CMD, mainMenu=mainMenu, synopsis=SYNOPSIS, usageText=USAGE_TEXT)),
        MenuCtrl.MENU_HELP_CMD   : ( "List command parameters", MenuCtrl.MENU_HELP_CMD_PARAM,
                                 lambda **argV: usageCommand(mainMenu=mainMenu, **argV )),

        "Quit"                   : MenuCtrl.MENU_SEPATOR_TUPLE,
        MenuCtrl.MENU_QUIT       : MenuCtrl.MENU_QUIT_TUPLE,

        # Hidden commands
        MenuCtrl.MENU_VERSION    : ( "Output version number", None, version ),
        CMD_SHOW_TTYS            : ( "List serial devices", ttyShowPar, ttyShow ),
        CMD_INFO                 : ( "Application info", None, instrument.info ),
    }

    menuController.setMenu( menu = mainMenu, defaults = defaults)

    # Interactive use starts REPL-loop
    if runMenu: menuController.mainMenu()

    # menuController.close() call after returning from run()
    return menuController
