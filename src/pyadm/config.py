import configparser
from pathlib import Path

config = configparser.ConfigParser()
config_file = Path.home() / ".config/pyadm/pyadm.conf"
config.read(config_file)
