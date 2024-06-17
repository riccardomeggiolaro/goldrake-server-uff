from typing import Optional, Union
from pydantic import BaseModel, validator
from lib.lb_system import Connection, SerialPort, Tcp
from modules.md_weigher_utils.dto import SetupWeigherDTO

class DataInExecution(BaseModel):
	customer: Optional[str] = None
	supplier: Optional[str] = None
	plate: Optional[str] = None
	vehicle: Optional[str] = None
	material: Optional[str] = None
	
	def setAttribute(self, key, value):
		if hasattr(self, key):
			setattr(self, key, value)

class Realtime(BaseModel):
	status: str
	type: str
	net_weight: str 
	gross_weight: str
	tare: str
	unite_measure: str
	
class Diagnostic(BaseModel):
	status: int
	firmware: str
	model_name: str
	serial_number: str
	vl: str
	rz: str

class WeightExecuted(BaseModel):
	net_weight: str
	gross_weight: str
	tare: str
	unite_misure: str
	pid: str
	bil: str
	status: str

class Weight(BaseModel):
	weight_executed: WeightExecuted
	data_assigned: Optional[Union[DataInExecution, int]] = None

class SetupWeigher(BaseModel):
	max_weight: int
	min_weight: int
	division: int
	maintaine_session_realtime_after_command: bool = True
	diagnostic_has_priority_than_realtime: bool = True
	node: Optional[str] = None
	terminal: str

	conn: Union[Connection, SerialPort, Tcp]
	
	def write(self, cmd):
		try:
			if self.node and self.node is not None:
				cmd = self.node + cmd
			self.conn.write(cmd=cmd)
		except AttributeError:
			pass

	def read(self):
		global config
		status, read, error = self.conn.read()
		if status:
			decode = read.decode("utf-8", errors="ignore").replace(self.node, "", 1).replace("\r\n", "")
			read = decode
		return read

	def decode_read(self, read):
		global config
		decode = read
		try:
			decode = read.decode('utf-8', errors='ignore')
		except:
			pass
		try:
			decode = decode.strip()
			if self.node and self.node is not None:
				decode = decode.replace(self.node, "", 1)
		except:
			pass
		return decode

	def flush(self):
		self.conn.flush()

	def is_connected(self):
		self.conn.is_open()

	def close_connection(self):
		self.conn.close()
		self.conn = Connection(**{})
  
	def getSetup(self):
		return {
			"node": self.node,
			"max_weight": self.max_weight,
			"min_weight": self.min_weight,
			"division": self.division,
			"maintaine_session_realtime_after_command": self.maintaine_session_realtime_after_command,
			"diagnostic_has_priority_than_realtime": self.diagnostic_has_priority_than_realtime,
			"terminal": self.terminal
		}

	def setSetup(self, setup: SetupWeigherDTO):
		if setup.max_weight is not None:
			self.max_weight = setup.max_weight
		if setup.min_weight is not None:
			self.min_weight = setup.min_weight
		if setup.division is not None:
			self.division = setup.division
		if setup.maintaine_session_realtime_after_command is not None:
			self.maintaine_session_realtime_after_command = setup.maintaine_session_realtime_after_command
		if setup.diagnostic_has_priority_than_realtime is not None:
			self.diagnostic_has_priority_than_realtime = setup.diagnostic_has_priority_than_realtime
		if setup.node != "undefined":
			self.node = setup.node
		return self.getSetup()