class Helper():
    
    def __init__(self):
        pass

                
    def print_data(data):
        def print_data(d, prefix=''):
            for key, value in d.items():
                if isinstance(value, dict):
                    print_data(value, prefix + key + ' ')
                else:
                    print(f"{prefix}{key.replace('_', ' ').capitalize()}: {value}")
        print_data(data)