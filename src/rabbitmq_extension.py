import re
from typing import Dict

from ruxit.api.base_plugin import RemoteBasePlugin
from ruxit.api.selectors import ExplicitSelector, EntityType
from ruxit.api.topology_builder import Device

from rabbitmq_api import RabbitMQClient


class RabbitMQExtension(RemoteBasePlugin):

    def initialize(self, **kwargs):
        self.executions = -1

    def query(self, **kwargs) -> None:
        self.executions += 1

        # Step 1 - Get configuration parameters from the UI
        node_address = self.config.get("rabbitmq_node", "")
        username = self.config.get("rabbitmq_username", "guest")
        password = self.config.get("rabbitmq_password", "guest")
        queues_include = self.config.get("queues_include", ".*").split("/n")
        frequency = self.config.get("frequency", 1)

        # The user can choose the frequency of the plugin execution
        # We need this workaround (counting the number of times the query method is executed)
        if self.executions % frequency == 0:

            # This is topology, create a CUSTOM_DEVICE_GROUP
            group = self.topology_builder.create_group("Rabbit MQ Group", "Rabbit MQ Group")

            # This is a check, we are trying to connect to RabbitMQ
            rabbit = RabbitMQClient(node_address, username, password, logger=self.logger)
            try:
                _ = rabbit.cluster
                self.logger.info(f"Successfully connected to {node_address}")
            except Exception as e:
                error_message = f"Could not connect to RabbitMQ node {node_address}"
                self.results_builder.report_error_event(error_message, "RabbitMQ connection issue", entity_selector=ExplicitSelector(group.id, EntityType.CUSTOM_DEVICE_GROUP))
                self.logger.error(error_message)
                raise Exception(error_message) from e

            # This is also topology, we need to create CUSTOM_DEVICE manually
            nodes: Dict[str, Device] = {}
            for node in rabbit.nodes:
                nodes[node.name] = group.create_device(f"RabbitMQ Node {node.name}")

            # Report the queue metrics
            for queue in rabbit.queues:
                self.logger.info(f"Checking queue '{queue.name}'")
                monitor = False

                for pattern in queues_include:
                    if pattern and re.match(pattern, queue.name):
                        self.logger.info(f"Adding queue '{queue.name}' because it matched the pattern '{pattern}'")
                        monitor = True

                if monitor:
                    device = nodes.get(queue.node)
                    device.absolute("messages_ready",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_unacknowledged",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_ack",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_deliver_get",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_publish",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_redeliver",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
                    device.absolute("messages_return",  queue.messages_ready, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
