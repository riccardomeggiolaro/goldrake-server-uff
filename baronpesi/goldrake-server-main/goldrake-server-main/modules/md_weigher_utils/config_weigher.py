from lib.lb_system import Connection, SerialPort, Tcp
from typing import List, Union, Callable
from modules.md_weigher_utils.dto import SetupWeigherDTO
from modules.md_weigher_utils.types import DataInExecution, SetupWeigher
from modules.md_weigher_utils.terminals.dgt1 import Dgt1
import lib.lb_log as lb_log
from modules.md_weigher_utils.utils import terminalsClasses

class ConfigWeigher():
	nodes: List[SetupWeigher] = []
	connection: Union[SerialPort, Tcp, Connection] = Connection(**{})
	time_between_actions: Union[int, float]

	def getConfig(self):
		conn = self.connection.copy().dict()
		nodes_dict = []
		for node in self.nodes:
			n = node.getSetup()
			nodes_dict.append(n)
		if "conn" in conn:
			del conn["conn"]
		return {
			"connection": conn,
			"nodes": nodes_dict,
			"time_between_actions": self.time_between_actions
		}

	def deleteConfig(self):
		result, message = False, None
		if len(self.nodes) > 0 or self.connection is not None:
			result, message = True, None
			try:
				self.connection.close()
				self.connection = None
			except AttributeError as e:
				message = e
			self.nodes = []
		return result, message

	def getConnection(self):
		conn = self.connection.copy().dict()
		if "conn" in conn:
			del conn["conn"]
		return conn

	def setConnection(self, connection: Union[SerialPort, Tcp]):
		connected, message = False, None
		self.deleteConnection()
		self.connection = connection
		connected, message = self.connection.try_connection()
		for node in self.nodes:
			node.initialize()
		conn = self.connection.copy()
		del conn.conn
		return connected, conn, message

	def deleteConnection(self):
		response = True
		try:
			i = 0
			for node in self.nodes:
				self.nodes[i].close_connection()
				i += 1
			self.connection.close()
			self.connection = Connection(**{})
		except AttributeError as e:
			response = False
		return response

	def getNodes(self):
		nodes_dict = []
		for node in self.nodes:
			n = node.getSetup()
			nodes_dict.append(n)
		return nodes_dict

	def getNode(self, node: Union[str, None]):
		result = None
		data = [n for n in self.nodes if n.node == node]
		if len(data) > 0:
			result = data[0].getSetup()
		return result

	def addNode(self, node: SetupWeigherDTO):
		node_to_add = node.dict()
		node_to_add["conn"] = self.connection
		terminalClass = [terminal for terminal in terminalsClasses if terminal["terminal"] == node.terminal]			
		n = terminalClass[0]["class"](**node_to_add)
		if self.connection is not None:
			n.initialize()
		self.nodes.append(n)
		return n.getSetup()

	def setNode(self, node: Union[str, None], setup: SetupWeigherDTO):
		node_found = [n for n in self.nodes if n.node == node]
		result = None
		if len(node_found) is not 0:
			result = node_found[0].setSetup(setup)
			if node_found[0].diagnostic == 301 and self.connection is not None:
				node_found[0].initialize()
		return result

	def deleteNode(self, node: Union[str, None]):
		node_found = [n for n in self.nodes if n.node == node]
		response = False
		if len(node_found) is not 0:
			self.nodes.remove(node_found[0])
			response = True
		return response

	def getDataInExecution(self, node: Union[str, None]):
		result = None
		data = [n for n in self.nodes if n.node == node]
		if len(data) > 0:
			result = data[0].data_in_execution.dict()
		return result

	def setDataInExecutions(self, node: Union[str, None], data_in_execution: DataInExecution):
		result = None
		node_found = [n for n in self.nodes if n.node == node]
		if len(node_found) > 0:
			node_found[0].setDataInExecution(data=data_in_execution)
			result = node_found[0].data_in_execution.dict()
		return result

	def deleteDataInExecution(self, node: Union[str, None]):
		result = None
		data = [n for n in self.nodes if n.node == node]
		if len(data) > 0:
			data[0].deleteDataInExecution()
			result = data[0].data_in_execution.dict()
		return result

	def setModope(self, node: Union[str, None], modope, presettare=0, data_assigned = None):
		node_found = [n for n in self.nodes if n.node == node]
		status, status_modope, command_execute = False, None, False
		if len(node_found) is not 0:
			status = True
			status_modope = node_found[0].setModope(mod=modope, presettare=presettare, data_assigned=data_assigned)
			command_execute = status_modope == 100
		return status, status_modope, command_execute

	def setActionNode(
		self,
		node: Union[str, None],
		cb_realtime: Callable[[dict], any] = None, 
		cb_diagnostic: Callable[[dict], any] = None, 
		cb_weighing: Callable[[dict], any] = None, 
		cb_tare_ptare_zero: Callable[[str], any] = None):
		node_found = [n for n in self.nodes if n.node == node]
		if len(node_found) > 0:
			node_found[0].setAction(
				cb_realtime=cb_realtime,
				cb_diagnostic=cb_diagnostic,
				cb_weighing=cb_weighing,
				cb_tare_ptare_zero=cb_tare_ptare_zero
			)

	def setAction(
		self,
		cb_realtime: Callable[[dict], any] = None, 
		cb_diagnostic: Callable[[dict], any] = None, 
		cb_weighing: Callable[[dict], any] = None, 
		cb_tare_ptare_zero: Callable[[str], any] = None):
		for node in self.nodes:
			node.setAction(
				cb_realtime=cb_realtime,
				cb_diagnostic=cb_diagnostic,
				cb_weighing=cb_weighing,
				cb_tare_ptare_zero=cb_tare_ptare_zero
			)