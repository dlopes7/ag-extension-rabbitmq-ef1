from typing import List
import logging

import requests

default_logger = logging.getLogger(__name__)
default_logger.setLevel(logging.INFO)


class Queue:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('name')
        self.node = raw_json.get('node')
        self.state = raw_json.get('state')
        self.vhost = raw_json.get('vhost', "/")

        self.messages_ready = raw_json.get('messages_ready', 0)
        self.messages_unacknowledged = raw_json.get('messages_unacknowledged', 0)
        self.consumers = raw_json.get('consumers', 0)

        self.messages_publish = 0
        self.messages_deliver_get = 0
        self.messages_ack = 0
        self.messages_redeliver = 0
        self.messages_return = 0

        if 'message_stats' in raw_json:
            self.messages_publish = raw_json.get('message_stats').get('publish', 0)
            self.messages_redeliver = raw_json.get('message_stats').get('redeliver', 0)
            self.messages_deliver_get = raw_json.get('message_stats').get('deliver_get', 0)
            self.messages_return = raw_json.get('message_stats').get('return_unroutable', 0)
            self.messages_ack = raw_json.get('message_stats').get('ack', 0)

        # print(pprint.pformat(raw_json))

    def __repr__(self):
        return f'Queue({self.name}@{self.node})'


class Node:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('name')
        self.mem_used = raw_json.get('mem_used', 0) / raw_json.get('mem_limit', 1) * 100
        self.fd_used = raw_json.get('fd_used', 0) / raw_json.get('fd_total', 1) * 100
        self.sockets_used = raw_json.get('sockets_used', 0) / raw_json.get('sockets_total', 1) * 100
        self.procs_used = raw_json.get('proc_used', 0) / raw_json.get('proc_total', 1) * 100
        self.disk_free = raw_json.get('disk_free', 10 ** 12)
        self.ip = None

    def __repr__(self):
        return f'Node({self.name})'


class Connection:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('name')
        self.state = raw_json.get('state')  # running, blocked
        self.node = raw_json.get('node')

    def __repr__(self):
        return f'Connection({self.name})'


class Channel:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('name')
        self.state = raw_json.get('state')  # flow
        self.node = raw_json.get('node')

    def __repr__(self):
        return f'Channel({self.name})'


class Exchange:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('name')
        self.type = raw_json.get('type')

    def __repr__(self):
        return f'Exchange({self.name} - {self.type})'


class Consumer:
    def __init__(self, raw_json: dict):
        self.consumer_tag = raw_json.get('consumer_tag')

    def __repr__(self):
        return f'Consumer({self.consumer_tag})'


class Listener:
    def __init__(self, raw_json: dict):
        self.node = raw_json.get("node")
        self.protocol = raw_json.get("protocol")
        self.ip_address = raw_json.get("ip_address")
        self.port = raw_json.get("port")

    def __repr__(self):
        return f'Listener({self.node}:{self.port} ({self.protocol}))'


class Cluster:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get('cluster_name')
        self.node = raw_json.get('node')
        self.rabbitmq_version = raw_json.get('rabbitmq_version')
        self.erlang_version = raw_json.get('erlang_version')

        self.messages_ready = raw_json.get('queue_totals').get('messages_ready', 0)
        self.messages_unacknowledged = raw_json.get('queue_totals').get('messages_unacknowledged', 0)
        self.listeners: List[Listener] = [Listener(listener) for listener in raw_json.get("listeners", [])]

        message_stats = raw_json.get('message_stats', {})

        self.ack = message_stats.get('ack', 0)
        self.unack = message_stats.get('deliver_no_ack', 0)
        self.deliver_get = message_stats.get('deliver_get', 0)
        self.publish = message_stats.get('publish', 0)
        self.redeliver = message_stats.get('redeliver', 0)
        self.return_unroutable = message_stats.get('return_unroutable', 0)


    def __repr__(self):
        return f'Cluster({self.name}) - v{self.rabbitmq_version}'


class VirtualHost:
    def __init__(self, raw_json: dict):
        self.name = raw_json.get("name")
        self.messages = raw_json.get("messages", 0)
        self.messages_ready = raw_json.get("messages_ready", 0)
        self.messages_unacknowledged = raw_json.get("messages_unacknowledged", 0)
        self.description = raw_json.get("description")

    def __repr__(self):
        return f'VirtualHost({self.name}) - {self.messages}'


class RabbitMQClient:

    def __init__(self, address: str, username: str, password: str, logger=default_logger):
        self.logger = logger
        self.auth = (username, password)

        self.base_url = address.rstrip("/")

    def make_request(self, url, method='GET'):
        r = requests.request(method, url, auth=self.auth, timeout=30, verify=False)
        if r.status_code >= 300:
            self.logger.error(f'RabbitMQClient - Got {r} while calling "{url}"')
        else:
            return r.json()

    @property
    def virtual_hosts(self) -> List[VirtualHost]:
        url = f'{self.base_url}/api/vhosts'
        return [VirtualHost(raw_json) for raw_json in self.make_request(url)]


    @property
    def queues(self) -> List[Queue]:
        url = f'{self.base_url}/api/queues'
        return [Queue(raw_json) for raw_json in self.make_request(url)]

    @property
    def nodes(self) -> List[Node]:
        url = f'{self.base_url}/api/nodes'
        return [Node(raw_json) for raw_json in self.make_request(url)]

    @property
    def connections(self):
        url = f'{self.base_url}/api/connections'
        return [Connection(raw_json) for raw_json in self.make_request(url)]

    # @property
    # def node_status(self):
    #     url = f'{self.base_url}/api/healthchecks/node'
    #     return self.make_request(url).get('status', None)

    @property
    def channels(self):
        url = f'{self.base_url}/api/channels'
        return [Channel(raw_json) for raw_json in self.make_request(url)]

    @property
    def consumers(self):
        url = f'{self.base_url}/api/consumers'
        return [Consumer(raw_json) for raw_json in self.make_request(url)]

    @property
    def exchanges(self):
        url = f'{self.base_url}/api/exchanges'
        return [Exchange(raw_json) for raw_json in self.make_request(url)]

    @property
    def cluster(self):
        url = f'{self.base_url}/api/overview'
        return Cluster(self.make_request(url))


def main():
    c = RabbitMQClient('localhost', 15672, 'guest', 'guest')

    print(c.cluster)

    for queue in c.queues:
        print(queue.name, queue.state)

    for node in c.nodes:
        print(node)

    for conn in c.connections:
        print(conn)

    for channel in c.channels:
        print(channel)

    for vhost in c.virtual_hosts:
        print(vhost)


if __name__ == '__main__':
    main()






