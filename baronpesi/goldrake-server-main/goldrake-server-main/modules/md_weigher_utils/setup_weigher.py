from typing import Optional
from modules.md_weigher_utils.dto import SetupWeigherDTO
from pydantic import BaseModel
from modules.md_weigher_utils.utils import connection

class SetupWeigher(BaseModel):
	max_weight: int
	min_weight: int
	division: int
	maintaine_session_realtime_after_command: bool = True
	diagnostic_has_priority_than_realtime: bool = True
	node: Optional[str] = None
	terminal: str

	def try_connection(self):
		return connection.connection.try_connection()
	
	def write(self, cmd):
		try:
			if self.node and self.node is not None:
				cmd = self.node + cmd
			connection.connection.write(cmd=cmd)
		except AttributeError:
			pass

	def read(self):
		status, read, error = connection.connection.read()
		if status:
			decode = read.decode("utf-8", errors="ignore").replace(self.node, "", 1).replace("\r\n", "")
			read = decode
		return read

	def decode_read(self, read):
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
		connection.connection.flush()

	def is_connected(self):
		connection.connection.is_open()

	def close_connection(self):
		connection.connection.close()
		connection.connection = Connection(**{})
  
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