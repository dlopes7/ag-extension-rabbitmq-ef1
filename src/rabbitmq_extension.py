import re
from typing import Optional, Dict

from ruxit.api.base_plugin import RemoteBasePlugin
from ruxit.api.selectors import ExplicitSelector, EntityType
from ruxit.api.topology_builder import Device

from rabbitmq_api import RabbitMQClient, Cluster


class RabbitMQExtension(RemoteBasePlugin):

    def initialize(self, **kwargs):
        self.executions = -1
        self.metrics_cache = {}

    def query(self, **kwargs) -> None:
        self.executions += 1
        node_addresses = self.config.get("rabbitmq_nodes", "").split("\n")
        username = self.config.get("rabbitmq_username", "guest")
        password = self.config.get("rabbitmq_password", "guest")
        queues_include = self.config.get("queues_include", ".*").split("/n")
        queues_ignore = self.config.get("queues_ignore", "").split("/n")

        frequency = self.config.get("frequency", 1)

        if self.executions % frequency == 0:
            cluster_name = self.config.get("cluster_name")
            group = self.topology_builder.create_group(cluster_name, cluster_name)

            rabbit: Optional[RabbitMQClient] = None
            cluster: Optional[Cluster] = None

            for node_address in node_addresses:
                rabbit = RabbitMQClient(node_address, username, password, logger=self.logger)
                try:
                    cluster = rabbit.cluster
                    self.logger.info(f"Successfully connected to {node_address}")
                    break
                except Exception as e:
                    error_message = f"Could not connect to {node_address}: {e}"
                    self.results_builder.report_custom_info_event(error_message, "RabbitMQ connection issue with one node", entity_selector=ExplicitSelector(group.id, EntityType.CUSTOM_DEVICE_GROUP))
                    self.logger.warning(error_message)

            if cluster is None:
                error_message = f"Could not connect to any nodes, the list was: {node_addresses}"
                self.results_builder.report_error_event(error_message, "RabbitMQ connection issue with all nodes", entity_selector=ExplicitSelector(group.id, EntityType.CUSTOM_DEVICE_GROUP))
                self.logger.error(error_message)
                return

            nodes: Dict[str, Device] = {}
            for node in rabbit.nodes:
                nodes[node.name] = group.create_device(f"RabbitMQ Node {node.name}")

            for queue in rabbit.queues:
                monitor = False

                for pattern in queues_include:
                    if pattern and re.match(pattern, queue.name):
                        self.logger.info(f"Adding queue '{queue.name}' because it matched the pattern '{pattern}'")
                        monitor = True

                for pattern in queues_ignore:
                    if pattern and re.match(pattern, queue.name):
                        self.logger.info(f"Removing queue '{queue.name}' because it matched the pattern '{pattern}'")
                        monitor = False
                        break

                if monitor:
                    device = nodes.get(queue.node)

                    metrics: Dict[str, bool] = {
                        "messages_unacknowledged": False,
                        "messages_ready": False,
                        "messages_ack": True,
                        "messages_deliver_get": True,
                        "messages_publish": True,
                        "messages_redeliver": True,
                        "messages_return": True,
                    }

                    for metric, delta in metrics.items():
                        value = getattr(queue, metric)
                        if delta:
                            metric_id = f"{queue.name}_{queue.vhost}_{metric}"
                            if metric_id in self.metrics_cache:
                                value = value - self.metrics_cache[metric_id]
                                self.metrics_cache[metric_id] = getattr(queue, metric)
                            else:
                                self.metrics_cache[metric_id] = value
                                continue

                        if self.config.get(f"collect_{metric}"):
                            device.absolute(metric,  value, dimensions={"VirtualHost": queue.vhost, "Queue": queue.name})
