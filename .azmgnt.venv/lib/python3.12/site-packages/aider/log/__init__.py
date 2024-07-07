import logging
import sys

def get_file_handler(filepath, level):
    ''' return file handler '''

    if not filepath: return
   
    format = '%(process)d - %(asctime)s - %(message)s'
    formatter = logging.Formatter(format)

    file_handler = logging.FileHandler(filepath)
    file_handler.setFormatter(formatter)

    return file_handler

def get_stream_handler(level):
    ''' return stream handler '''

    stream_handler = logging.StreamHandler(sys.stdout)
    return stream_handler

def get_logger(name='root', level='info', config=None, filepath=None):
    ''' return generic logger '''

    # logging level mapping
    level_mapping = {
        'notset': logging.NOTSET,
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }
    level = level_mapping[level]
 
    # initialize logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # add handlers
    logger.addHandler(get_stream_handler(level))
    if filepath: logger.addHandler(get_file_handler(filepath, level))

    return logger