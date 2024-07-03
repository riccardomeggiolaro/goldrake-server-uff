from modules.md_weigher_utils.types import SetupWeigher
from modules.md_weigher_utils.types import Realtime, Diagnostic, Weight, DataInExecution
from modules.md_weigher_utils.utils import checkCallbackFormat
from typing import Callable, Union

class BasicTerminal(SetupWeigher):
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

	def getDataInExecution(self):
		return self.data_in_execution.dict()

	def setDataInExecution(self, data: DataInExecution):
		for key, value in data:
			if value is None:
				continue
			elif value == "undefined":
				self.data_in_execution.setAttribute(key=key, value=None)
			else:
				self.data_in_execution.setAttribute(key, value)
		return self.getDataInExecution()

	def deleteDataInExecution(self):
		self.data_in_execution = DataInExecution(**{
			"customer": None,
			"supplier": None,
			"plate": None,
			"vehicle": None,
			"material": None
		})
		return self.getDataInExecution()

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

	# functions to overwrite
 
	def command(self):
    		pass

	def initialize(self):
		pass

	def main(self):
		pass