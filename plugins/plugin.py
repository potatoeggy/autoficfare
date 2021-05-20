import abc
import configparser

class Plugin(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, config: configparser.ConfigParser):
        self.config = config
    

    @abc.abstractmethod
    def post_add_hook(self, old_metadata: dict, new_metadata: dict):
        return