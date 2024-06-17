from modules.md_weigher_utils.types import Realtime, Diagnostic, Weight, DataInExecution, SetupWeigher
from modules.md_weigher_utils.utils import terminalsClasses
from typing import Callable, Union
from modules.md_weigher_utils.dto import SetupWeigherDTO
import lib.lb_log as lb_log
from modules.md_weigher_utils.utils import checkCallbackFormat, callCallback
import re

class Dgt1(SetupWeigher):
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

	# setta il modope_to_execute
	def setModope(self, mod: str, presettare: int = 0, data_assigned: Union[DataInExecution, int] = None):
		commands = ["VER", "SN", "OK"]
		direct_commands = ["TARE", "ZERO", "RESETTARE", "PRESETTARE", "WEIGHING"]
		if mod in commands:
			self.modope_to_execute = mod
			return 100
		if self.diagnostic.status in [301, 305, 307] and mod != "REALTIME" and mod != "DIAGNOSTICS" and mod != "":
			return self.diagnostic.status
		# se passo una stringa vuota imposta a stringa vuota il comando da eseguire dopo, quindi non verranno più eseguiti comandi diretti sulla pesa
		# se passo DIAGNOSTICS lo imposto come comando da eseguire, se c'era qualsiasi altro comando viene sovrascritto perchè la diagnostica ha la precedenza
		if mod == "DIAGNOSTICS":
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
		elif mod in direct_commands:
			# controllo se il comando attualmente in esecuzione in loop è DIAGNOSTICS e se si ritorno errore
			if self.modope == "DIAGNOSTICS":
				return 400
			# controllo se c'è qualche comando diretto verso la pesa attualmente in esecuzione e se si ritorno errore
			elif self.modope in commands or self.modope in direct_commands:
				return 405
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
				elif self.modope_to_execute in commands or self.modope_to_execute in direct_commands:
					return 405
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
		elif self.modope == "OK":
			self.write("DINT2710") # scrive un comando sulla pesa
			self.modope_to_execute = "OK"
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
				self.setModope("OK")
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
				elif self.modope == "OK":
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

terminalsClasses.append({
	"terminal": "dgt1",
	"class": Dgt1
})