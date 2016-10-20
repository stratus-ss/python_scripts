import sys
import os.path
import logging
import colorlog
import inspect

from logging.handlers import RotatingFileHandler

# make external modules only log above warning and upper
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# define root logging strategy
root = logging.getLogger()
root.setLevel(logging.DEBUG)

####################
# define new log level for SUCCESS
SUCCESS = logging.INFO + 1
logging.addLevelName( SUCCESS, 'SUCCESS')

####################
# log on stdout
stdout_formatter = colorlog.ColoredFormatter(
        "%(asctime)s - %(log_color)s%(levelname)-7s%(reset)s %(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
                'DEBUG':    'white',
                'INFO':     'white',
                'SUCCESS':  'green',
                'WARNING':  'yellow',
                'ERROR':    'white,bg_red',
                'CRITICAL': 'white,bg_red',
        },
        secondary_log_colors={},
        style='%'
)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(stdout_formatter)
root.addHandler(ch)

####################
# also log in a dedicated log file (full date, no color)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = RotatingFileHandler('figaro_deploy.log', maxBytes=10000000, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(file_formatter)
root.addHandler(fh)

def __get_log_msg(txt):
    '''Get filename and line number where the log occurs'''
    frame = inspect.currentframe().f_back.f_back
    if frame and frame.f_back:
        frame = frame.f_back
    func = frame.f_code
    return "[%s:%s] %s" % (os.path.basename(func.co_filename), frame.f_lineno, txt)

def debug(msg):
    logging.debug(__get_log_msg(msg))

def info(msg):
    logging.info(__get_log_msg(msg))

def success(msg):
    logging.log(SUCCESS, __get_log_msg(msg))

def warning(msg):
    logging.warning(__get_log_msg(msg))

def error(msg, exit_on_error = True):
    logging.error(__get_log_msg(msg))
    if exit_on_error:
        exit(1)
    
def critical(msg):
    logging.critical(__get_log_msg(msg))
    exit(1)
