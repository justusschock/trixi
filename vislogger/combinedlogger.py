from collections import defaultdict

from vislogger import AbstractLogger


def create_function(self, sub_methods):
    def surrogate_fn(*args, **kwargs):

        for sub_method in sub_methods:

            method_cntr = self.log_methods_cntr[sub_method]
            method_freq = self.log_methods_freq[sub_method]

            if "log_all" in kwargs and kwargs["log_all"] is True:
                sub_method(*args, **kwargs)
                continue

            if method_cntr % method_freq == 0:
                sub_method(*args, **kwargs)

            elif "same_as_last" in kwargs and kwargs["same_as_last"] is True:
                if method_cntr % method_freq == 1:
                    sub_method(*args, **kwargs)
                kwargs["do_not_increase"] = True

            if "do_not_increase" not in kwargs or ("do_not_increase" in kwargs and kwargs["do_not_increase"] is False):
                self.log_methods_cntr[sub_method] += 1

    return surrogate_fn


class CombinedLogger(object):
    def __init__(self, *loggers):

        self.loggers, self.frequencys = zip(*loggers)

        for logger in self.loggers:
            if not isinstance(logger, AbstractLogger):
                raise TypeError("All logger must be subclasses of the abstract visual logger.")
        for freq in self.frequencys:
            if freq < 1:
                raise ValueError("All frequencys must be at least one.")

        self.logger_methods = defaultdict(list)
        self.log_methods_cntr = defaultdict(int)
        self.log_methods_freq = defaultdict(int)

        for logger, freq in zip(self.loggers, self.frequencys):

            logger_vars = [i for i in dir(logger) if not i.startswith("__")]

            for el in logger_vars:
                if hasattr(logger, el) and callable(getattr(logger, el)):
                    self.logger_methods[el].append(getattr(logger, el))
                    self.log_methods_cntr[getattr(logger, el)] = 0
                    self.log_methods_freq[getattr(logger, el)] = freq

        for method_name, sub_methods in self.logger_methods.items():
            setattr(self, method_name, create_function(self, sub_methods))
