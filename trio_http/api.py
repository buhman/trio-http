import abc
import ssl
import json
from functools import partial

import h11
import trio

import event


async def tls_connect(server_hostname, tcp_port):
    tcp_stream = await trio.open_tcp_stream(server_hostname, tcp_port)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_stream = trio.SSLStream(transport_stream=tcp_stream,
                                ssl_context=ssl_context,
                                server_hostname=server_hostname,
                                https_compatible=True)

    await ssl_stream.do_handshake()

    return ssl_stream
    return tcp_stream


async def send_events(connection: h11.Connection,
                      stream: trio.abc.Stream,
                      *http_events: event.HTTPEvent):
    for event in http_events:
        data = connection.send(event)
        if data is None:
            # the event was a ConnectionClosed
            await stream.aclose()
        else:
            await stream.send_all(data)


async def receive_events(connection: h11.Connection,
                         stream: trio.abc.Stream):
    while True:
        event = connection.next_event()
        if event is h11.NEED_DATA:
            data = await stream.receive_some(4096)
            connection.receive_data(data)
        else:
            yield event

        if type(event) is h11.EndOfMessage:
            break

def data_collector(data_factory=bytearray):
    data = data_factory()
    def collect(chunk=None):
        if chunk is not None:
            data.extend(chunk)
        return data
    return collect


async def client_factory(server_hostname, port):
    connection = h11.Connection(our_role=h11.CLIENT)
    stream = await tls_connect(server_hostname, port)

    async def make_request(request, data):
        await send_events(connection, stream,
                          request,
                          data,
                          h11.EndOfMessage())

        collect = data_collector()
        response = None

        async for event in receive_events(connection, stream):
            if type(event) is h11.Response:
                response = event
            elif type(event) is h11.Data:
                collect(event.data)
            elif type(event) is h11.EndOfMessage:
                pass
            else:
                raise NotImplementedError(type(event))

        print(connection.our_state, connection.their_state)
        if connection.our_state == h11.DONE and connection.their_state == h11.DONE:
            connection.start_next_cycle()

        data = collect()
        return response, data

    return make_request


async def log_thingy():
    token = os.environ['HEC_TOKEN']
    #make_request = await client_factory("localhost", 8088)
    #make_request = await client_factory("input-prd-p-blwd8d7v2wrj.cloud.splunk.com", 8088)
    make_request = await client_factory("requestbin.fullcontact.com", 443)

    request = h11.Request(method="POST",
                          target="/1j5i1id1",
                          headers=[
                              #("host", "input-prd-p-blwd8d7v2wrj.cloud.splunk.com"),
                              ("host", "requestbin.fullcontact.com"),
                              ("accept", "application/json"),
                              ("content-type", "application/json"),
                              ("authorization", f"Splunk {token}"),
                              ("content-length", "51"),
                          ])

    while True:
        import time
        event = {
            # time
            # host
            # source
            # index
            "sourcetype": "mysourcetype",
            "event": int(time.time())
        }
        data = h11.Data(data=json.dumps(event).encode('utf-8'))

        response, data = await make_request(request, data)
        print(response.status_code, data)

        await trio.sleep(200)


trio.run(log_thingy)
