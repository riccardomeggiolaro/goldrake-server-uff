# ==============================================================
# = Module......: md_dgt1					   =
# = Description.: Interfaccia di pesatura dgt1			   =
# = Author......: Riccardo Meggiolaro				   =
# = Last rev....: 0.0002					   =
# -------------------------------------------------------------=
# 0.0002 : Implementato....
# 0.0001 : Creazione del modulo
# ==============================================================

# ==== LIBRERIE DA IMPORTARE ===================================
import inspect
__frame = inspect.currentframe()
namefile = inspect.getfile(__frame).split("/")[-1].replace(".py", "")
import lib.lb_log as lb_log
import lib.lb_system as lb_system
import lib.lb_config as lb_config
import serial
from serial import SerialException
from typing import Callable, Union, Optional, List
import inspect
import time
import copy
from pydantic import BaseModel, validator
import re
from abc import ABC, abstractmethod
import socket
# ==============================================================

# ==== FUNZIONI RICHIAMABILI DENTRO IL MODULO ==================
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

class Setup(ABC, BaseModel):
	@abstractmethod
	def write(self, cmd):
		pass

	@abstractmethod
	def read(self):
		pass

	@abstractmethod
	def decode_read(self, read):
		pass
 
class SetupWeigherOptional(BaseModel):
	max_weight: Optional[int] = None
	min_weight: Optional[int] = None
	division: Optional[int] = None
	maintaine_session_realtime_after_command: Optional[bool] = None
	diagnostic_has_priority_than_realtime: Optional[bool] = None
	node: Optional[Union[str, None]] = "undefined"

	@validator('max_weight', 'min_weight', 'division', pre=True, always=True)
	def check_positive(cls, v):
		if v is not None and v < 1:
			raise ValueError('Value must be greater than or equal to 1')
		return v

	@validator('node', pre=False, always=True)
	def check_format_setup(cls, v, values, **kwargs):
		global config
		node_just_exist = [n for n in config.nodes if n.node == v]
		if len(node_just_exist) > 0:
			raise ValueError(f"{v} just assigned")
		return v

class SetupWeigher(Setup):
	max_weight: int
	min_weight: int
	division: int
	maintaine_session_realtime_after_command: bool = True
	diagnostic_has_priority_than_realtime: bool = True
	node: Optional[str] = None

	def write(self, cmd):
		global config
		try:
			if self.node and self.node is not None:
				cmd = self.node + cmd
			config.connection.write(cmd=cmd)
		except AttributeError:
			pass

	def read(self):
		global config
		status, read, error = config.connection.read()
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
		global config
		config.connection.flush()

	def is_connected(self):
		global config
		config.connection.is_open()

class SetupWeigherConfig(SetupWeigher):
	pesa_real_time: Realtime = Realtime(**{
		"status": "",
		"type": "",
		"net_weight": "", 
		"gross_weight": "", 
		"tare": "",
		"unite_measure": ""
	})
	diagnostic: Diagnostic = Diagnostic(**{
		"status": 301,
		"firmware": "",
		"model_name": "",
		"serial_number": "",
		"vl": "",
		"rz": ""
	})
	weight: Weight = Weight(**{
		"weight_executed": {
			"net_weight": "",
			"gross_weight": "",
			"tare": "",
			"unite_misure": "",
			"pid": "",
			"bil": "",
			"status": ""
		},
		"data_assigned": None
	})
	ok_value: str = ""
	modope: str = ""
	modope_to_execute: str = ""
	valore_alterno: int = 1
	preset_tare: int = 0
	just_send_message_failed_reconnection: bool = False
	callback_realtime: str = ""
	callback_diagnostics: str = ""
	callback_weighing: str = ""
	callback_tare_ptare_zero: str = ""
	data_in_execution: DataInExecution = DataInExecution(**{
		"customer": None,
		"supplier": None,
		"plate": None,
		"vehicle": None,
		"material": None
	})

	def deleteDataInExecution(self):
		self.data_in_execution = DataInExecution(**{
			"customer": None,
			"supplier": None,
			"plate": None,
			"vehicle": None,
			"material": None
		})

	def setDataInExecution(self, data: DataInExecution):
		for key, value in data:
			if value is None:
				continue
			elif value == "undefined":
				self.data_in_execution.setAttribute(key=key, value=None)
			else:
				self.data_in_execution.setAttribute(key, value)

	def maintaineSessionRealtime(self):
		if self.maintaine_session_realtime_after_command:
			self.modope_to_execute = "REALTIME"

	def setAction(self,
		cb_realtime: Callable[[dict], any] = None, 
		cb_diagnostic: Callable[[dict], any] = None, 
		cb_weighing: Callable[[dict], any] = None, 
		cb_tare_ptare_zero: Callable[[str], any] = None):
		check_cb_realtime = checkCallbackFormat(cb_realtime) # controllo se la funzione cb_realtime è richiamabile
		if check_cb_realtime: # se è richiamabile assegna alla globale callback_realtime la funzione passata come parametro
			self.callback_realtime = lambda: cb_realtime(self.pesa_real_time) 
		check_cb_diagnostic = checkCallbackFormat(cb_diagnostic) # controllo se la funzione cb_diagnostic è richiamabile
		if check_cb_diagnostic: # se è richiamabile assegna alla globale callback_diagnostics la funzione passata come parametro
			self.callback_diagnostics = lambda: cb_diagnostic(self.diagnostic)
		check_cb_weighing = checkCallbackFormat(cb_weighing) # controllo se la funzione cb_weighing è richiamabile
		if check_cb_weighing: # se è richiamabile assegna alla globale callback_weighing la funzione passata come parametro
			self.callback_weighing = lambda: cb_weighing(self.weight)
		check_cb_tare_ptare_zero = checkCallbackFormat(cb_tare_ptare_zero) # controllo se la funzione cb_tare_ptare_zero è richiamabile
		if check_cb_tare_ptare_zero: # se è richiamabile assegna alla globale callback_tare_ptare_zero la funzione passata come parametro
			self.callback_tare_ptare_zero = lambda: cb_tare_ptare_zero(self.ok_value)

	def setSetup(self, setup: SetupWeigherOptional):
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
		return {
			"max_weight": self.max_weight,
			"min_weight": self.min_weight,
			"division": self.division,
			"maintaine_session_realtime_after_command": self.maintaine_session_realtime_after_command,
			"diagnostic_has_priority_than_realtime": self.diagnostic_has_priority_than_realtime,
			"node": self.node
		}

	# setta il modope_to_execute
	def setModope(self, mod: str, presettare: int = 0, data_assigned: Union[DataInExecution, int] = None):
		if mod in ["VER", "SN", "DINT2710"]:
			self.modope_to_execute = mod
			return 100
		if self.diagnostic.status in [301, 305, 307] and mod != "REALTIME" and mod != "DIAGNOSTICS" and mod != "":
			return self.diagnostic.status
		commands = ["TARE", "ZERO", "RESETTARE", "PRESETTARE", "WEIGHING"]
		# se passo una stringa vuota imposta a stringa vuota il comando da eseguire dopo, quindi non verranno più eseguiti comandi diretti sulla pesa
		if mod == "":
			self.modope_to_execute = "" # imposta a stringa vuota
			return 100 # ritorna il successo
		# se passo DIAGNOSTICS lo imposto come comando da eseguire, se c'era qualsiasi altro comando viene sovrascritto perchè la diagnostica ha la precedenza
		elif mod == "DIAGNOSTICS":
			self.modope_to_execute = mod # imposto la diagnostica
			return 100 # ritorno il successo
		# se passo REALTIME
		if mod == "REALTIME":
			# se il comando in esecuzione o il comando che dovrà essere eseguito è la diagnostica ed ha la priorità ritorno errore
			if self.modope_to_execute == "DIAGNOSTICS" and self.diagnostic_has_priority_than_realtime:
				return 400
			self.modope_to_execute = mod # se non si è verificata nessuna delle condizioni imposto REALTIME come comando da eseguire
			return 100 # ritorno il successo
		# se il mod passato è un comando diretto verso la pesa ("TARE", "ZERO", "RESETTARE", "PRESETTARE", "WEIGHING")
		elif mod in commands:
			# controllo se il comando attualmente in esecuzione in loop è DIAGNOSTICS e se si ritorno errore
			if self.modope == "DIAGNOSTICS":
				return 400
			# controllo se c'è qualche comando diretto verso la pesa attualmente in esecuzione e se si ritorno errore
			elif self.modope in commands:
				return 429
			# controllo che il comando attualmente in esecuzione in loop sia REALTIME
			elif self.modope == "REALTIME":
				# controllo che anche il comando da eseguire sia impostato a REALTIME per assicurarmi che non sia cambiato
				if self.modope_to_execute == "REALTIME":
					# se passo PRESETTARE
					if mod == "PRESETTARE" and mod:
						# controllo che la presettare passata sia un numero e maggiore o uguale di 0
						if str(presettare).isdigit() and int(presettare) >= 0:
							self.preset_tare = presettare # imposto la presettare
						else:
							return 500 # ritorno errore se la presettare non era valida
					# se passo WEIGHING
					elif mod == "WEIGHING":
						# controllo che il peso sia maggiore o uguale al peso minimo richiesto
						if self.pesa_real_time.gross_weight != "" and self.pesa_real_time.status == "ST" and int(self.pesa_real_time.gross_weight) >= self.min_weight and int(self.pesa_real_time.gross_weight) <= self.max_weight:
							self.weight.data_assigned = data_assigned
							lb_log.info(data_assigned)
						else:
							return 500 # ritorno errore se il peso non era valido
					self.modope_to_execute = mod # se tutte le condizioni sono andate a buon fine imposto il mod passato come comando da eseguire
					return 100 # ritorno il successo
				elif self.modope_to_execute == "DIAGNOSTICS":
					return 400
				elif self.modope_to_execute in commands:
					return 429
		# se il comando passato non è valido ritorno errore
		else:
			return 404

	def command(self):
		global config
		self.modope = self.modope_to_execute # modope assume il valore di modope_to_execute, che nel frattempo può aver cambiato valore tramite le funzioni richiambili dall'esterno
		# in base al valore del modope scrive un comando specifico nella conn
		if self.modope == "DIAGNOSTICS":
			if self.valore_alterno == 1: # se valore alterno uguale a 1 manda MVOL per ottnere determinati dati riguardanti la diagnostica
				self.write("MVOL")
			elif self.valore_alterno == 2: # altrimenti se valore alterno uguale a 2 manda RAZF per ottnere altri determinati dati riguardanti la diagnostica
				self.write("RAZF")		
				self.valore_alterno = 0 # imposto valore uguale a 0
			self.valore_alterno = self.valore_alterno + 1 # incremento di 1 il valore alterno
		elif self.modope == "REALTIME":
			self.write("RALL")
		elif self.modope == "DINT2710":
			self.write("DINT2710")
		elif self.modope == "WEIGHING":
			self.write("PID")
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
			self.maintaineSessionRealtime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
		elif self.modope == "TARE":
			self.write("TARE")
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
			self.maintaineSessionRealtime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
		elif self.modope == "PRESETTARE":
			self.write("TMAN" + str(self.preset_tare))
			self.preset_tare = 0
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
			self.maintaineSessionRealtime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
		elif self.modope == "ZERO":
			self.write("ZERO")
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
			self.maintaineSessionRealtime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
		elif self.modope == "VER":
			self.write("VER")
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		elif self.modope == "SN":
			self.write("SN")
			self.modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		elif self.modope == "DINT2710":
			self.write("DINT2710") # scrive un comando sulla pesa
			self.modope_to_execute = ""
		return self.modope

	def is_open(self):
		global config
		status = config.connection.is_open()
		lb_log.info(status)
		if not status:
			lb_log.info("Non è aperta")
			status, error_message = config.connection.try_connection()
			return status
		return True

	def initialize(self):
		try:
			self.setModope("VER")
			self.command()
			response = self.read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				# lb_log.info(response)
				values = response.split(",")
				# se il numero di sottostringhe è 3 assegna i valori all'oggetto diagnostic
				if len(values) == 3:
					self.diagnostic.firmware = values[1].lstrip()
					self.diagnostic.model_name = values[2].rstrip()
				# se il numero di sottostringhe non è 3 manda errore
				else:
					raise ValueError("Firmware and model name not found")
			# se non ottiene la risposta o la lunghezza della stringa non è 12 manda errore
			else:
				# lb_log.info(response)
				raise ConnectionError("No response get")
			# ottenere numero conn
			self.setModope("SN")
			self.command()
			response = self.read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				value = response.replace("SN: ", "")
				self.diagnostic.serial_number = value
			# se non ottiene la risposta o la lughezza della stringa non è 13 manda errore
			else:
				raise ConnectionError("SN No response get")
			# controllo se ho ottenuto firmware, nome modello e numero conn
			if self.diagnostic.firmware and self.diagnostic.model_name and self.diagnostic.serial_number:
				self.diagnostic.status = 200 # imposto status della pesa a 200 per indicare che è accesa
				self.setModope("DINT2710")
				lb_log.info("------------------------------------------------------")
				lb_log.info("INITIALIZATION")
				lb_log.info("INFOSTART: " + "Accensione con successo")
				lb_log.info("NODE: " + self.node)
				lb_log.info("FIRMWARE: " + self.diagnostic.firmware) 
				lb_log.info("MODELNAME: " + self.diagnostic.model_name)
				lb_log.info("SERIALNUMBER: " + self.diagnostic.serial_number)
				lb_log.info("------------------------------------------------------")
		except ValueError as e:
			self.diagnostic.status = 305
			lb_log.info(e)
		except ConnectionError as e:
			self.diagnostic.status = 301
			lb_log.info(e)
		return {
			"max_weight": self.max_weight,
			"min_weight": self.min_weight,
			"division": self.division,
			"maintaine_session_realtime_after_command": self.maintaine_session_realtime_after_command,
			"diagnostic_has_priority_than_realtime": self.diagnostic_has_priority_than_realtime,
			"node": self.node
		}

	def main(self):
		if self.diagnostic.status in [200, 307]:
			self.command() # eseguo la funzione command() che si occupa di scrivere il comando sulla pesa in base al valore del modope_to_execute nel momento in cui ho chiamato la funzione
			response = self.read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				split_response = response.split(",") # creo un array di sotto stringhe splittando la risposta per ogni virgola
				length_split_response = len(split_response) # ottengo la lunghezza dell'array delle sotto stringhe
				length_response = len(response) # ottengo la lunghezza della stringa della risposta
				######### Se in esecuzione peso in tempo reale ######################################################################
				if self.modope == "REALTIME":
					# Controlla formato stringa del peso in tempo reale, se corretta aggiorna oggetto e chiama callback
					if length_split_response == 10 and length_response == 63:
						nw = (re.sub('[KkGg\x00\n]', '', split_response[2]).lstrip())
						gw = (re.sub('[KkGg\x00\n]', '', split_response[3]).lstrip())
						t = (re.sub('[KkGg\x00\n]', '', split_response[4]).lstrip())
						self.pesa_real_time.status = split_response[0]
						self.pesa_real_time.type = "GS" if t == "0" else "NT"
						self.pesa_real_time.net_weight = nw
						self.pesa_real_time.gross_weight = gw
						self.pesa_real_time.tare = t
						self.pesa_real_time.unite_measure = split_response[2][-2:]
					# Se formato stringa del peso in tempo reale non corretto, manda a video errore
					else:
						pass
						# lb_log.error(f"Received string format does not comply with the REALTIME function: {response}")
						# lb_log.error(length_split_response)
						# lb_log.error(length_response)
					self.diagnostic.vl = ""
					self.diagnostic.rz = ""
					callCallback(self.callback_realtime) # chiamo callback
				######### Se in esecuzione la diagnostica ###########################################################################
				elif self.modope == "DIAGNOSTICS":
					# Controlla formato stringa della diagnostica, se corretta aggiorna oggetto e chiama callback
					if length_split_response == 4 and length_response == 19:
						self.pesa_real_time.status = "diagnostics in progress"
						if split_response[1] == "VL":
							self.diagnostic.vl = str(split_response[2]).lstrip() + " " + str(split_response[3])
						elif split_response[1] == "RZ":
							self.diagnostic.rz = str(split_response[2]).lstrip() + " " + str(split_response[3])
					# Se formato stringa della diagnostica non corretto, manda a video errore
					else:
						pass
						# lb_log.error(f"Received string format does not comply with the DIAGNOSTICS function: {response}")
					self.pesa_real_time.status = "D"
					self.pesa_real_time.type = ""
					self.pesa_real_time.net_weight = ""
					self.pesa_real_time.gross_weight = ""
					self.pesa_real_time.tare = ""
					self.pesa_real_time.unite_measure = ""
					callCallback(self.callback_diagnostics) # chiamo callback
				######### Se in esecuzione pesata pid ###############################################################################
				elif self.modope == "WEIGHING":
					# Controlla formato stringa pesata pid, se corretta aggiorna oggetto
					if length_split_response == 5 and (length_response == 48 or length_response == 38):
						gw = (re.sub('[KkGg\x00\n]', '', split_response[2]).lstrip())
						t = (re.sub('[PTKkGg\x00\n]', '', split_response[3])).lstrip()
						nw = str(int(gw) - int(t))
						self.weight.weight_executed.net_weight = nw
						self.weight.weight_executed.gross_weight = gw
						self.weight.weight_executed.tare = t
						self.weight.weight_executed.unite_misure = split_response[2][-2:]
						self.weight.weight_executed.pid = split_response[4]
						self.weight.weight_executed.bil = split_response[1]
						self.weight.weight_executed.status = split_response[0]
					# Se formato stringa pesata pid non corretto, manda a video errore e setta oggetto a None
					else:
						pass
						# lb_log.error(f"Received string format does not comply with the WEIGHING function: {response}")
					callCallback(self.callback_weighing) # chiamo callback
					self.weight.weight_executed.net_weight = ""
					self.weight.weight_executed.gross_weight = ""
					self.weight.weight_executed.tare = ""
					self.weight.weight_executed.unite_misure = ""
					self.weight.weight_executed.pid = ""
					self.weight.weight_executed.bil = ""
					self.weight.weight_executed.status = ""
					self.weight.data_assigned = None
				######### Se in esecuzione tara, preset tara o zero #################################################################
				elif self.modope in ["TARE", "PRESETTARE", "ZERO"]:
					# Controlla formato stringa, se corretto aggiorna ok_value
					if length_response == 2 and response == "OK":
						self.ok_value = response
					# Se formato stringa non valido setto ok_value a None
					else:
						pass
						# lb_log.error(f"Received string format does not comply with the function {self.modope}: {response}")			
					if self.modope == "TARE":
						self.pesa_real_time.status = "T"
					if self.modope == "PRESETTARE":
						self.pesa_real_time.status = "PT"						
					elif self.modope == "ZERO":
						self.pesa_real_time.status = "Z"
					callCallback(self.callback_tare_ptare_zero) # chiamo callback
					self.ok_value = "" # Risetto ok_value a stringa vuota
				######### Se non è arrivata nessuna risposta ################################
				elif self.modope == "DINT2710":
					if length_response == 2 and response == "OK":
						lb_log.info(response)
				else:
					self.diagnostic.status = 301
			if not response:
				self.diagnostic.vl = ""
				self.diagnostic.rz = ""
				self.pesa_real_time.status = ""
				self.pesa_real_time.type = ""
				self.pesa_real_time.net_weight = ""
				self.pesa_real_time.gross_weight = ""
				self.pesa_real_time.tare = ""
				self.pesa_real_time.unite_measure = ""
				self.weight.weight_executed.net_weight = ""
				self.weight.weight_executed.gross_weight = ""
				self.weight.weight_executed.tare = ""
				self.weight.weight_executed.unite_misure = ""
				self.weight.weight_executed.pid = ""
				self.weight.weight_executed.bil = ""
				self.weight.weight_executed.status = ""
				self.weight.data_assigned = None
				self.ok_value = ""
				self.diagnostic.status = 301
				if self.modope == "WEIGHING":
					self.weight.status = self.diagnostic.status
					callCallback(self.callback_weighing)
					self.weight.status = ""
				elif self.modope in ["TARE", "PTARE", "ZERO"]:
					self.ok_value = self.diagnostic.status
					callCallback(self.callback_tare_ptare_zero)
					self.ok_value = ""
				elif self.modope == "REALTIME":
					self.pesa_real_time.status = self.diagnostic.status
					callCallback(self.callback_realtime) # chiamo callback
					self.pesa_real_time.status = ""
		# se lo stato della pesa è 301 e initializated è uguale a True prova a ristabilire una connessione con la pesa
		else:
			if self.diagnostic.status in [305, 301]:
				self.initialize()
				self.flush()

class Connection(BaseModel):
	def try_connection(self):
		return False, ConnectionError('No connection set')
	
	def flush(self):
		return False, ConnectionError('No connection set')

	def close(self):
		return False, ConnectionError('No connection set')

	def write(self, cmd):
		return False, ConnectionError('No connection set')

	def read(self):
		return False, None, ConnectionError('No connection set')

	def decode_read(self, read):
		return False, None, ConnectionError('No connection set')

	def is_open(self):
		return False, None, ConnectionError('No connection set')

class SerialPort(Connection):
	baudrate: int = 19200
	serial_port_name: str
	timeout: int = 1

	@validator('baudrate', 'timeout', pre=True, always=True)
	def check_positive(cls, v):
		if v is not None and v < 1:
			raise ValueError('Value must be greater than or equal to 1')
		return v

	@validator('serial_port_name', pre=True, always=True)
	def check_format(cls, v):
		if v is not None:
			result, message = lb_system.exist_serial_port(v)
			if result is False:
				raise ValueError(message)
			result, message = lb_system.enable_serial_port(v)
			if result is False:
				raise ValueError(message)
			result, message = lb_system.serial_port_not_just_in_use(v)
			if result is False:
				raise ValueError(message)
		return v

	def try_connection(self):
		status = True
		error_message = None
		try:
			global conn
			if isinstance(conn, serial.Serial) and conn.is_open:
				conn.flush()
				conn.close()
			conn = serial.Serial(port=self.serial_port_name, baudrate=self.baudrate, timeout=self.timeout)
		except SerialException as e:
			status = False
			error_message = e
			# lb_log.error(f"SerialException on try connection: {error_message}")
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.error(f"AttributeError on try connection: {error_message}")
		except TypeError as e:
			status = False
			error_message = e
			# lb_log.error(f"TypeError on try connection: {error_message}")
		return status, error_message

	def flush(self):
		global conn
		status = True
		error_message = None
		try:
			if isinstance(conn, serial.Serial) and conn.is_open:
				conn.flush()
		except SerialException as e:
			status = False
			error_message = e
			# lb_log.error(f"SerialException on flush: {error_message}")
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.error(f"AttributeError on flush: {error_message}")
		return status, error_message

	def close(self):
		global conn
		status = False
		error_message = None
		try:
			if isinstance(conn, serial.Serial) and conn.is_open:
				conn.flush()
				conn.close()
				conn = None
				status = True
		except SerialException as e:
			status = False
			error_message = e
			# lb_log.error(f"SerialException on close: {error_message}")
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.error(f"AttributeError on close: {error_message}")
		except TypeError as e:
			status = False
			error_message = e
			# lb_log.error(f"TypeError on close: {error_message}")
		return status, error_message

	def write(self, cmd):
		status = True
		error_message = None
		try:
			global conn
			status = False
			if isinstance(conn, serial.Serial) and conn.is_open:
				command = (cmd + chr(13)+chr(10)).encode()
				conn.write(command)
			else:
				raise SerialException()
		except SerialException as e:
			status = False
			error_message = e
			# lb_log.error(f"SerialException on write: {error_message}")
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.error(f"AttributeError on write: {error_message}")
		except TypeError as e:
			status = False
			error_message = e
			# lb_log.error(f"TypeError on write: {error_message}")
		return status, error_message

	def read(self):
		status = True
		message = None
		error_message = None
		try:
			global conn
			read = None
			if isinstance(conn, serial.Serial) and conn.is_open:
				message = conn.readline()
			else:
				raise SerialException()
		except SerialException as e:
			status = False
			error_message = e
			# lb_log.error(f"SerialException on read: {error_message}")
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.error(f"AttributeError on read: {error_message}")
		except TypeError as e:
			status = False
			error_message = e
			# lb_log.error(f"TypeError on read: {error_message}")
		return status, message, error_message

	def decode_read(self, read):
		status = True
		message = None
		error_message = None
		try:
			message = read.decode('utf-8', errors='ignore').replace("\r\n", "").strip()
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.info(read)
			# lb_log.error(f"AttributeError on decode read: {error_message}")
		return status, message, error_message

class Tcp(Connection):
	ip: str
	port: int
	timeout: float

	@validator('port', pre=True, always=True)
	def check_positive(cls, v):
		if v is not None and v < 1:
			raise ValueError('Value must be greater than or equal to 1')
		return v
	
	@validator('ip', pre=True, always=True)
	def check_format(cls, v):
		parts = v.split(".")
		if len(parts) == 4:
			for p in parts:
				if not p.isdigit():
					raise ValueError('Ip must contains only number and')
			return v
		else:
			raise ValueError('Ip no valid')

	def is_open(self):
		try:
			global conn
			if isinstance(conn, socket.socket) and conn.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
				return True
			lb_log.info("No")
			return False
		except socket.error:
			lb_log.info("No")
			return False

	def try_connection(self):
		status = True
		error_message = None
		try:
			global conn
			if self.is_open():
				conn.close()
			conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			conn.setblocking(False)
			conn.settimeout(self.timeout)
			# establish connection with server
			conn.connect((self.ip, self.port))
		except socket.error as e:
			status = False
			error_message = e
			# lb_log.error(f"Socket error on try connection: {error_message}")
		return status, error_message

	def flush(self):
		global conn
		status = True
		error_message = None
		try:
			buffer = b""			
			# Ricevi i dati finché ce ne sono
			while True:
				try:
					data = conn.recv(5000)  # Ricevi fino a 1024 byte alla volta
					if not data:
						break  # Se non ci sono più dati nel buffer, esci dal ciclo
					# Accumula i dati ricevuti nel buffer
					buffer += data
					lb_log.info(buffer)
				except BlockingIOError as e:
					break
		except socket.error as e:
			status = False
			error_message = e
		return status, error_message

	def close(self):
		global conn
		status = False
		error_message = None
		try:
			self.flush()
			conn.close()
			status = True
		except socket.error as e:
			status = False
			error_message = e
			# lb_log.error(f"Socket error on close: {error_message}")
		return status, error_message

	def write(self, cmd):
		status = True
		error_message = None
		try:
			global conn
			status = False
			command = (cmd + chr(13)+chr(10)).encode()
			conn.sendall(command[:1024])
		except socket.error as e:
			status = False
			error_message = e
			lb_log.error(f"Socket error on write: {error_message}")
		return status, error_message

	def read(self):
		global conn
		status = False
		message = None
		error_message = None
		try:
			message = conn.recv(1024)
			status = True
		except BlockingIOError as e:
			status = False
			error_message = e
		except socket.error as e:
			status = False
			error_message = e
			# lb_log.error(f"Socket error on write: {error_message}")
		return status, message, error_message

	def decode_read(self, read):
		status = True
		message = None
		error_message = None
		try:
			message = read.decode('utf-8', errors='ignore').replace("\r\n", "").strip()
		except AttributeError as e:
			status = False
			error_message = e
			# lb_log.info(read)
			# lb_log.error(f"AttributeError on decode read: {error_message}")
		return status, message, error_message

class Configuration(BaseModel):
	nodes: List[SetupWeigher] = []
	connection: Union[SerialPort, Tcp, Connection, None] = None
	time_between_actions: Union[int, float]

	@validator('connection', pre=True, always=True)
	def check_connection(cls, v):
		if v is None:
			return Connection(**{})
		return v

class ConfigWeigher():
	global conn

	nodes: List[SetupWeigherConfig] = []
	connection: Union[SerialPort, Tcp, Connection] = Connection(**{})
	time_between_actions: Union[int, float]

	def __init__(self):
		conn = self.connection

	def getConfig(self):
		return {
			"connection": self.connection.dict(),
			"nodes": [node.dict() for node in self.nodes],
			"time_between_actions": self.time_between_actions
		}

	def deleteConfig(self):
		result, message = False, None
		if len(config.nodes) > 0 or config.connection is not None:
			result, message = True, None
			try:
				self.connection.close()
				self.connection = None
			except AttributeError as e:
				message = e
			self.nodes = []
		return result, message

	def setConnection(self, connection: Union[SerialPort, Tcp]):
		connected, message = False, None
		self.deleteConnection()
		self.connection = connection
		connected, message = self.connection.try_connection()
		for node in self.nodes:
			node.initialize()
		return connected, self.connection.dict(), message

	def deleteConnection(self):
		response = True
		try:
			self.connection.close()
			self.connection = Connection(**{})
			conn = self.connection
		except AttributeError as e:
			response = False
		return response

	def getNode(self, node: Union[str, None]):
		result = None
		data = [n for n in self.nodes if n.node == node]
		if len(data) > 0:
			result = data[0].dict()
		return result

	def addNode(self, node: SetupWeigher):
		node_to_add = node.dict()
		n = SetupWeigherConfig(**node_to_add)
		if self.connection is not None:
			n.initialize()
		self.nodes.append(n)
		return node_to_add

	def setNode(self, node: Union[str, None], setup: SetupWeigherOptional):
		node_found = [n for n in self.nodes if n.node == node]
		response = None
		if len(node_found) is not 0:
			response = node_found[0].setSetup(setup)
			if node_found[0].diagnostic == 301 and self.connection is not None:
				node_found[0].initialize()
		return response

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

# controlla se la callback è eseguibile, se si la esegue
# controlla se la callback è eseguibile, se si la esegu
def callCallback(callback):
	if callable(callback):
		callback()

# controlla se il formato della callback è giusto, ovvero se è richiamabile e se ha 1 solo parametro
def checkCallbackFormat(callback):
	if callable(callback):
		signature = inspect.signature(callback)
		num_params = len(signature.parameters)
		if num_params == 1:
			return True
	return False
# ==============================================================

# ==== INIT ====================================================
# funzione che dichiara tutte le globali
def init():
	lb_log.info("init")
	global config
	global conn

	config = ConfigWeigher()
	conn = config.connection
# ==============================================================

# ==== MAINPRGLOOP =============================================
# funzione che scrive e legge in loop conn e in base alla stringa ricevuta esegue funzioni specifiche
def mainprg():
	global config
	while lb_config.g_enabled:
		for node in config.nodes:
			time_start = time.time()
			node.main()
			time_end = time.time()
			time_execute = time_end - time_start
			timeout = max(0, config.time_between_actions - time_execute)
			time.sleep(timeout)
# ==============================================================

# ==== START ===================================================
# funzione che fa partire il modulo
def start():
	lb_log.info("start")
	mainprg() # fa partire la funzione che scrive e legge la conn in loop
	lb_log.info("end")
	# se la globale conn è di tipo conn ed è aperta la chiude
# ==============================================================

def stop():
	global config
	result = config.deleteConnection()
	lb_log.info(f"Result {result}")

# ==== FUNZIONI RICHIAMABILI DA MODULI ESTERNI =================
def initialize(configuration: Configuration):
	lb_log.info("initialize")
	global config
	# inizializzazione della conn
	connected, message = False, None
	config.connection = configuration.connection
	connected, message = config.connection.try_connection()
	config.nodes = []
	config.time_between_actions = configuration.time_between_actions
	for node in configuration.nodes:
		n = SetupWeigherConfig(**node.dict())
		n.initialize()
		config.nodes.append(n)
		# ottenere firmware e nome del modello
	return connected, message # ritorno True o False in base se status della pesa è 200

def getConfig():
	global config
	return config.getConfig()

def deleteConfig():
	global config
	result, message = config.deleteConfig()
	return result, message

def getConnection():
	global config
	data = config.connection.dict()
	return data

def setConnection(connection: Union[SerialPort, Tcp]):
	global config
	connected, connection, message = config.setConnection(connection=connection)
	return connected, connection, message

def deleteConnection():
	global config
	response = config.deleteConnection()
	return response

def getNode(node: Union[str, None]):
	global config
	result = config.getNode(node=node)
	return result

def addNode(node: SetupWeigher):
	global config
	node_to_add = config.addNode(node=node)
	return node_to_add

def setNode(node: Union[str, None], setup: SetupWeigherOptional = {}):
	global config
	response = config.setNode(node=node, setup=setup)
	return response

def deleteNode(node: Union[str, None]):
	global config
	response = config.deleteNode(node=node)
	return response

def setTimeBetweenActions(time: Union[int, float]):
    global config
    config.time_between_actions = time
    return config.time_between_actions

def getDataInExecution(node: Union[str, None]):
	global config
	result = config.getDataInExecution(node=node)
	return result

def setDataInExecution(node: Union[str, None], data_in_execution: DataInExecution):
	global config
	result = config.setDataInExecutions(node=node, data_in_execution=data_in_execution)
	return result

def deleteDataInExecution(node: Union[str, None]):
	global config
	result = config.deleteDataInExecution(node=node)
	return result

# Funzione per settare le funzioni di callback
# I parametri possono essere omessi o passati come funzioni che hanno un solo parametro come
# 	1) REALTIME 
# 			{
# 				"status": "Pesa scollegata", 
# 				"type": "",
# 				"net_weight": "", 
# 				"gross_weight": "", 
# 				"tare": "",
# 				"unite_measure": ""
# 			}
# 	2) DIAGNOSTICS
# 			{
#	 			"status": "Pesa scollegata",
# 				"firmware": "",
# 				"model_name": "",
# 				"serial_number": "",
# 				"vl": "",
# 				"rz": ""
# 			}
# 	3) WEIGHING
# 			{
# 				"net_weight": "",
# 				"gross_weight": "",
# 				"tare": "",
# 				"unite_misure": "",
# 				"pid": "",
# 				"bil": "",
# 				"status": ""
#	 		}
#   4) OK
#		   string

# funzione per impostare la diagnostica continua
# DIAGNOSTICS, REALTIME, WEIGHING, TARE, PRESETTARE, ZERO
def setModope(node: Union[str, None], modope, presettare=0, data_assigned = None):
	global config
	status, status_modope, command_execute = config.setModope(node=node, modope=modope, presettare=presettare, data_assigned=data_assigned)
	return status, status_modope, command_execute

def setActionNode(node: Union[str, None], cb_realtime: Callable[[dict], any] = None, cb_diagnostic: Callable[[dict], any] = None, cb_weighing: Callable[[dict], any] = None, cb_tare_ptare_zero: Callable[[str], any] = None):
	global config
	config.setActionNode(node=node, cb_realtime=cb_realtime, cb_diagnostic=cb_diagnostic, cb_weighing=cb_weighing, cb_tare_ptare_zero=cb_tare_ptare_zero)

def setAction(cb_realtime: Callable[[dict], any] = None, cb_diagnostic: Callable[[dict], any] = None, cb_weighing: Callable[[dict], any] = None, cb_tare_ptare_zero: Callable[[str], any] = None):
	global config
	config.setAction(cb_realtime=cb_realtime, cb_diagnostic=cb_diagnostic, cb_weighing=cb_weighing, cb_tare_ptare_zero=cb_tare_ptare_zero)
# ==============================================================