class Helper:
    def __init__(self):
        pass

    @staticmethod
    def print_data(data, prefix=''):
        """Pretty-print nested dictionary data recursively."""
        for key, value in data.items():
            if isinstance(value, dict):
                Helper.print_data(value, prefix + key + ' ')
            else:
                print(f"{prefix}{key.replace('_', ' ').capitalize()}: {value}")