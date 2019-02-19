import abc

import h11


class HTTPEvent(metaclass=abc.ABCMeta):
    pass


HTTPEvent.register(h11.Request)
HTTPEvent.register(h11.InformationalResponse)
HTTPEvent.register(h11.Response)
HTTPEvent.register(h11.Data)
HTTPEvent.register(h11.EndOfMessage)
HTTPEvent.register(h11.ConnectionClosed)
