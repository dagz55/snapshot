import configparser

def read_config(config_filepath):
    ''' To read config file '''

    config = configparser.RawConfigParser()
    config.read(config_filepath)
    return config