#!/usr/bin/env python3


# main for instrument controller define in module
from .ebenchDps import run
# from ebenchDps import run

from absl import app, flags, logging
from absl.flags import FLAGS

# Run time configurations of instrument controller
flags.DEFINE_string('port', "/dev/ttyUSB0", "MODBUS device port")


def _main( _argv ):
    logging.set_verbosity(FLAGS.debug)
    logging.info( "FLAGS.port={}".format(FLAGS.port))
    menuController = run(
        _argv
        , port=FLAGS.port          # pass run time configuration parameters to controller
        , captureDir=FLAGS.captureDir
        , recordingDir=FLAGS.recordingDir
        , outputTemplate=FLAGS.outputTemplate 
    )
    menuController.close()


def main():
    try:
        app.run(_main)
    except SystemExit:
        pass
    
    
if __name__ == '__main__':
    main()
