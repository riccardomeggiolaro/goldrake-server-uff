# ==============================================================
# = Module......: md_dgt1					   =
# = Description.: Interfaccia di pesatura dgt1			   =
# = Author......: Riccardo Meggiolaro				   =
# = Last rev....: 0.0002					   =
# -------------------------------------------------------------=
# 0.0002 : Implementato....
# 0.0001 : Creazione del modulo
# ==============================================================

# ==== Dati necessari nel file .json dentro setup per la corretta funzione del modulo
		# "dgt1": {
		#	 "serialport": {
		#		 "name": "/dev/ttyS0",
		#		 "speed": 19200,
		#		 "time_read": 1
		#	 },
		#	 "division": 1,
		# 	  "min_weight": 5,
		#	 "max_weight": 50000,
		#	 "maintaine_session_realtime": true, # setta se dopo ogni singolo comando diretto verso la pesa deve ripartire il realtime ai automatico
		#	 "diagnostic_has_priority_than_realtime": true
		# },
# ==============================================================

# ==== LIBRERIE DA IMPORTARE ===================================
import lb_log
import serial
from serial import SerialException
import re
import lb_config
from typing import Callable, Union, Optional
import inspect
import time
import copy
from pydantic import BaseModel, validator
import re
# ==============================================================

class SerialPort(BaseModel):
	baudrate: int = 19200
	serial_port_name: str
	timeout: int = 1
	node: Optional[str] = None

class Tcp(BaseModel):
    ip: str
    port: str
    timeout: int
    node: Optional[str] = None

class SetupWeigher(BaseModel):
	max_weight: int
	min_weight: int
	division: int
	maintaine_session_realtime_after_command: bool = True
	diagnostic_has_priority_than_realtime: bool = True

# ==== FUNZIONI RICHIAMABILI DA MODULI ESTERNI =================
# funzione che inizializza delle globali, la seriale e ottiene i dati della pesa
def initialize(connection: Union[SerialPort, Tcp], setup: SetupWeigher):
	lb_log.info("initialize")
	global conn
	global response
	global diagnostic
	global serialport
	global config
	global CLASS_CONNECTION
	try:
		# inizializzazione della conn
		try_connection(connection=connection)
		if wait_for_conn_ready():
			config = {
				"setup": setup.dict(),
				"connection": connection.dict()
			}
			if isinstance(connection, SerialPort):
				CLASS_CONNECTION = SerialPort
			elif isinstance(connection, Tcp):
				CLASS_CONNECTION = Tcp
			# ottenere firmware e nome del modello
			write("VER") # scrivo comando VER
			response = read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				response_decode = decode_read(response)
				values = response_decode.split(",")
				# se il numero di sottostringhe è 3 assegna i valori all'oggetto diagnostic
				if len(values) == 3:
					diagnostic["firmware"] = values[1].lstrip()
					diagnostic["model_name"] = values[2].rstrip()
				# se il numero di sottostringhe non è 3 manda errore
				else:
					raise ValueError("Firmware and model name not found")
			# se non ottiene la risposta o la lunghezza della stringa non è 12 manda errore
			else:
				lb_log.info(response)
				raise ValueError("Content of read serial not correct")
			# ottenere numero conn
			write("SN") # scrivo comando SN
			response = read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				response_decode = decode_read(response)
				response_decode = response_decode.replace("SN: ", "")
				diagnostic["serial_number"] = response_decode
			# se non ottiene la risposta o la lughezza della stringa non è 13 manda errore
			else:
				raise ValueError("Serial number was not found")
			# controllo se ho ottenuto firmware, nome modello e numero conn
			if diagnostic["firmware"] and diagnostic["model_name"] and diagnostic["serial_number"]:
				diagnostic["status"] = 200 # imposto status della pesa a 200 per indicare che è accesa
				lb_log.info("------------------------------------------------------")
				lb_log.info("INITIALIZATION")
				lb_log.info("INFOSTART: " + "Accensione con successo")
				lb_log.info("FIRMWARE: " + diagnostic["firmware"]) 
				lb_log.info("MODELNAME: " + diagnostic["model_name"])
				lb_log.info("SERIALNUMBER: " + diagnostic["serial_number"])
				lb_log.info("------------------------------------------------------")
		else:
			lb_log.error("Serial port not ready after initialization.")
			raise SerialException()
	except SerialException as e:
		lb_log.error(f"SerialException: {e}")
		diagnostic["status"] = 301
		return diagnostic["status"] != 301
	except ValueError as e:
		lb_log.error(f"ValueError: {e}")
		lb_log.error(response)
		diagnostic["status"] = 305
		return diagnostic["status"] != 301
	except Exception as e:
		lb_log.error(f"Exception: {e}")
		diagnostic["status"] = 301	
	return diagnostic["status"] != 301 # ritorno True o False in base se status della pesa è 200

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
def setAction(
	cb_realtime: Callable[[dict], any] = None, 
	cb_diagnostic: Callable[[dict], any] = None, 
	cb_weighing: Callable[[dict], any] = None, 
	cb_tare_ptare_zero: Callable[[str], any] = None):
	global pesa_real_time
	global diagnostic
	global weight
	global ok_value
	global callback_realtime
	global callback_diagnostics
	global callback_weighing
	global callback_tare_ptare_zero
	try:
		check_cb_realtime = checkCallbackFormat(cb_realtime) # controllo se la funzione cb_realtime è richiamabile
		if check_cb_realtime: # se è richiamabile assegna alla globale callback_realtime la funzione passata come parametro
			callback_realtime = lambda: cb_realtime(pesa_real_time) 
		check_cb_diagnostic = checkCallbackFormat(cb_diagnostic) # controllo se la funzione cb_diagnostic è richiamabile
		if check_cb_diagnostic: # se è richiamabile assegna alla globale callback_diagnostics la funzione passata come parametro
			callback_diagnostics = lambda: cb_diagnostic(diagnostic)
		check_cb_weighing = checkCallbackFormat(cb_weighing) # controllo se la funzione cb_weighing è richiamabile
		if check_cb_weighing: # se è richiamabile assegna alla globale callback_weighing la funzione passata come parametro
			callback_weighing = lambda: cb_weighing(weight)
		check_cb_tare_ptare_zero = checkCallbackFormat(cb_tare_ptare_zero) # controllo se la funzione cb_tare_ptare_zero è richiamabile
		if check_cb_tare_ptare_zero: # se è richiamabile assegna alla globale callback_tare_ptare_zero la funzione passata come parametro
			callback_tare_ptare_zero = lambda: cb_tare_ptare_zero(ok_value)
	except Exception as e:
		lb_log.error(e)

# funzione per impostare la diagnostica continua
def diagnsotics():
	return setModope("DIAGNOSTICS")

# funzione per impostare il peso in tempo reale
def realTime():
	return setModope("REALTIME")	

# funzione per eseguire la pesata
def weighing(data_assigned: any=None):
	return setModope("WEIGHING", data_assigned=data_assigned)

# funzione per eseguire la tara
def tare():
	return setModope("TARE")

# funzione per eseguire la preset tara
def presetTare(presettare: int):
	return setModope("PRESETTARE", presettare)

# funzione per resettare la tara
def resetTare():
	return setModope("PRESETTARE", presettare=0)

# funzione per azzerare il peso
def zero():
	return setModope("ZERO")

# funzione per non chiamare più niente
def stopCommand():
	return setModope("")

def getConfig():
	global diagnostic
	global config

	data = copy.copy(config)
	data["status"] = diagnostic["status"]

	return data

def is_initializated_successfully():
	global diagnostic
	return diagnostic["status"] == 200

def status_connection_weigher():
	return diagnostic["status"]

def deleteConfig():
	try:
		global conn
		global config
		global diagnostic
		global modope
		global modope_to_execute
		diagnostic["status"] = 301
		time.sleep(1)
		if isinstance(conn, serial.Serial) and conn.is_open:
			modope = ""
			modope_to_execute = ""
			conn.flush()
			conn.close()
		conn = None
		config = {
			"setup": {
				"max_weight": None,
				"min_weight": None,
				"division": None,
				"maintaine_session_realtime_after_command": True,
				"diagnostic_has_priority_than_realtime": True
			},
			"connection": {}
		}
		return True
	except:
		return False
# ==============================================================

# ==== FUNZIONI RICHIAMABILI DENTRO IL MODULO ==================
# comando da mandare alla pesa
def write(cmd):
	global conn
	global config
	if config["connection"]["node"] and config["connection"]["node"] is not None:
		cmd = config["connection"]["node"] + cmd
	command = (cmd + chr(13)+chr(10)).encode()
	conn.write(command)

def read():
	global conn
	read = conn.readline()
	return read

def decode_read(read):
	global config
	decode = read.strip().decode('utf-8', errors='ignore').replace("\r\n", "").strip()
	if config["connection"]["node"] and config["connection"]["node"] is not None:
		decode = decode.replace(config["connection"]["node"], "", 1)
	return decode

def try_connection(connection: Union[SerialPort, Tcp]):
	global conn
	if isinstance(conn, serial.Serial) and conn.is_open:
		conn.flush()
		conn.close()
	if isinstance(connection, SerialPort):
		conn = serial.Serial(port=connection.serial_port_name, baudrate=connection.baudrate, timeout=connection.timeout)
	elif isinstance(connection, Tcp):
		pass

def flush():
	global conn
	if isinstance(conn, serial.Serial) and conn.is_open:
		conn.flush()
	elif isinstance(connection, Tcp):
		pass    

# controlla se la callback è eseguibile, se si la esegue
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

# controlla se session_real_time è uguale a True allora setta mododpe_to_execute a REALTIME per mantenere la sessione
def maintaineSessionRealTime():
	global modope_to_execute
	global config
	if config["setup"]["maintaine_session_realtime_after_command"]:
		modope_to_execute = "REALTIME"

# setta il modope_to_execute
def setModope(mod: str, presettare: int = None, data_assigned: any = None):
	global modope
	global preset_tare
	global pesa_real_time
	global conn
	global modope_to_execute
	global diagnostic
	global weight
	global diagnostic
	global config

	if diagnostic["status"] in [301, 305, 307] and mod != "REALTIME" and mod != "DIAGNOSTICS" and mod != "":
		return diagnostic["status"]
	commands = ["TARE", "ZERO", "RESETTARE", "PRESETTARE", "WEIGHING"]
	# se passo una stringa vuota imposta a stringa vuota il comando da eseguire dopo, quindi non verranno più eseguiti comandi diretti sulla pesa
	if mod == "":
		modope_to_execute = "" # imposta a stringa vuota
		return 100 # ritorna il successo
	# se passo DIAGNOSTICS lo imposto come comando da eseguire, se c'era qualsiasi altro comando viene sovrascritto perchè la diagnostica ha la precedenza
	elif mod == "DIAGNOSTICS":
		modope_to_execute = mod # imposto la diagnostica
		return 100 # ritorno il successo
	# se passo REALTIME
	if mod == "REALTIME":
		# se il comando in esecuzione o il comando che dovrà essere eseguito è la diagnostica ed ha la priorità ritorno errore
		if modope_to_execute == "DIAGNOSTICS" and config["setup"]["diagnostic_has_priority_than_realtime"]:
			return 400
		modope_to_execute = mod # se non si è verificata nessuna delle condizioni imposto REALTIME come comando da eseguire
		return 100 # ritorno il successo
	# se il mod passato è un comando diretto verso la pesa ("TARE", "ZERO", "RESETTARE", "PRESETTARE", "WEIGHING")
	elif mod in commands:
		# controllo se il comando attualmente in esecuzione in loop è DIAGNOSTICS e se si ritorno errore
		if modope == "DIAGNOSTICS":
			return 400
		# controllo se c'è qualche comando diretto verso la pesa attualmente in esecuzione e se si ritorno errore
		elif modope in commands:
			return 429
		# controllo che il comando attualmente in esecuzione in loop sia REALTIME
		elif modope == "REALTIME":
			# controllo che anche il comando da eseguire sia impostato a REALTIME per assicurarmi che non sia cambiato
			if modope_to_execute == "REALTIME":
				# se passo PRESETTARE
				if mod == "PRESETTARE" and mod:
					# controllo che la presettare passata sia un numero e maggiore o uguale di 0
					if str(presettare).isdigit() and int(presettare) >= 0:
						preset_tare = presettare # imposto la presettare
					else:
						return 500 # ritorno errore se la presettare non era valida
				# se passo WEIGHING
				elif mod == "WEIGHING":
					# controllo che il peso sia maggiore o uguale al peso minimo richiesto
					if pesa_real_time["gross_weight"] != "" and pesa_real_time["status"] == "ST" and int(pesa_real_time["gross_weight"]) >= config["setup"]["min_weight"] and int(pesa_real_time["gross_weight"]) <= config["setup"]["max_weight"]:
						weight["data_assigned"] = data_assigned
					else:
						return 500 # ritorno errore se il peso non era valido
				modope_to_execute = mod # se tutte le condizioni sono andate a buon fine imposto il mod passato come comando da eseguire
				return 100 # ritorno il successo
			elif modope_to_execute == "DIAGNOSTICS":
				return 400
			elif modope_to_execute in commands:
				return 429
	# se il comando passato non è valido ritorno errore
	else:
		return 404

# aspetta un massimo di tot secondi per controllare e ritornare se la conn sia aperta 
def wait_for_conn_ready(max_attempts=5, delay_seconds=1):
	global conn
	for _ in range(max_attempts):
		if isinstance(conn, serial.Serial) and conn.is_open:
			return True
		time.sleep(delay_seconds)
	return False

# funzione che si occupa di scrivere sulla conn
def command():
	global modope
	global response
	global pesa_real_time
	global diagnostic
	global valore_alterno
	global preset_tare
	global modope_to_execute
	modope = modope_to_execute # modope assume il valore di modope_to_execute, che nel frattempo può aver cambiato valore tramite le funzioni richiambili dall'esterno
	# in base al valore del modope scrive un comando specifico nella conn
	if modope == "DIAGNOSTICS":
		if valore_alterno == 1: # se valore alterno uguale a 1 manda MVOL per ottnere determinati dati riguardanti la diagnostica
			write("MVOL")
		elif valore_alterno == 2: # altrimenti se valore alterno uguale a 2 manda RAZF per ottnere altri determinati dati riguardanti la diagnostica
			write("RAZF")		
			valore_alterno = 0 # imposto valore uguale a 0
		valore_alterno = valore_alterno + 1 # incremento di 1 il valore alterno
	elif modope == "REALTIME":
		write("RALL")
	elif modope == "WEIGHING":
		write("PID")
		modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		maintaineSessionRealTime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
	elif modope == "TARE":
		write("TARE")
		modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		maintaineSessionRealTime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
	elif modope == "PRESETTARE":
		write("TMAN" + str(preset_tare))
		preset_tare = 0
		modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		maintaineSessionRealTime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
	elif modope == "ZERO":
		write("ZERO")
		modope_to_execute = "" # setto modope_to_execute a stringa vuota per evitare che la stessa funzione venga eseguita anche nel prossimo ciclo
		maintaineSessionRealTime() # eseguo la funzione che si occupa di mantenere la sessione del peso in tempo reale in base a come la ho settata
# ==============================================================

# ==== MAINPRGLOOP =============================================
# funzione che scrive e legge in loop conn e in base alla stringa ricevuta esegue funzioni specifiche
def mainprg():
	global diagnostic
	global response
	global pesa_real_time
	global conn
	global weight
	global ok_value
	global initializated
	global modope
	global callback_realtime
	global callback_diagnostics
	global callback_weighing
	global callback_tare_ptare_zero
	global just_send_message_failed_reconnection
	global modope_to_execute
	global serialport
	global config
	global CLASS_CONNECTION
	while lb_config.g_enabled:
		if diagnostic["status"] == 200:
			command() # eseguo la funzione command() che si occupa di scrivere il comando sulla pesa in base al valore del modope_to_execute nel momento in cui ho chiamato la funzione
			response = read()
			if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
				response_decode = decode_read(response)
				split_seriale = response_decode.split(",") # creo un array di sotto stringhe splittando la risposta per ogni virgola
				length_split_seriale = len(split_seriale) # ottengo la lunghezza dell'array delle sotto stringhe
				length_seriale = len(response_decode) # ottengo la lunghezza della stringa della risposta
				######### Se in esecuzione peso in tempo reale ######################################################################
				if modope == "REALTIME":
					# Controlla formato stringa del peso in tempo reale, se corretta aggiorna oggetto e chiama callback
					if length_split_seriale == 10 and length_seriale == 63:
						nw = (re.sub('[KkGg\x00\n]', '', split_seriale[2]).lstrip())
						gw = (re.sub('[KkGg\x00\n]', '', split_seriale[3]).lstrip())
						t = (re.sub('[KkGg\x00\n]', '', split_seriale[4]).lstrip())
						pesa_real_time["status"] = split_seriale[0]
						pesa_real_time["type"] = "GS" if t == "0" else "NT"
						pesa_real_time["net_weight"] = nw
						pesa_real_time["gross_weight"] = gw
						pesa_real_time["tare"] = t
						pesa_real_time["unite_misure"] = split_seriale[2][-2:]
					# Se formato stringa del peso in tempo reale non corretto, manda a video errore
					else:
						lb_log.error(f"Received string format does not comply with the REALTIME function: {response_decode}")
					diagnostic["vl"] = ""
					diagnostic["rz"] = ""
					callCallback(callback_realtime) # chiamo callback
				######### Se in esecuzione la diagnostica ###########################################################################
				elif modope == "DIAGNOSTICS":
					# Controlla formato stringa della diagnostica, se corretta aggiorna oggetto e chiama callback
					if length_split_seriale == 4 and length_seriale == 19:
						pesa_real_time["status"] = "diagnostics in progress"
						if split_seriale[1] == "VL":
							diagnostic["vl"] = str(split_seriale[2]).lstrip() + " " + str(split_seriale[3])
						elif split_seriale[1] == "RZ":
							diagnostic["rz"] = str(split_seriale[2]).lstrip() + " " + str(split_seriale[3])
					# Se formato stringa della diagnostica non corretto, manda a video errore
					else:
						lb_log.error(f"Received string format does not comply with the DIAGNOSTICS function: {response_decode}")
					pesa_real_time["status"] = "D"
					pesa_real_time["type"] = ""
					pesa_real_time["net_weight"] = ""
					pesa_real_time["gross_weight"] = ""
					pesa_real_time["tare"] = ""
					pesa_real_time["unite_misure"] = ""
					callCallback(callback_diagnostics) # chiamo callback
				######### Se in esecuzione pesata pid ###############################################################################
				elif modope == "WEIGHING":
					# Controlla formato stringa pesata pid, se corretta aggiorna oggetto
					if length_split_seriale == 5 and (length_seriale == 48 or length_seriale == 38):
						gw = (re.sub('[KkGg\x00\n]', '', split_seriale[2]).lstrip())
						t = (re.sub('[PTKkGg\x00\n]', '', split_seriale[3])).lstrip()
						nw = str(int(gw) - int(t))
						weight["weight_executed"]["net_weight"] = nw
						weight["weight_executed"]["gross_weight"] = gw
						weight["weight_executed"]["tare"] = t
						weight["weight_executed"]["unite_misure"] = split_seriale[2][-2:]
						weight["weight_executed"]["pid"] = split_seriale[4]
						weight["weight_executed"]["bil"] = split_seriale[1]
						weight["weight_executed"]["status"] = split_seriale[0]
					# Se formato stringa pesata pid non corretto, manda a video errore e setta oggetto a None
					else:
						lb_log.error(f"Received string format does not comply with the WEIGHING function: {response_decode}")
					callCallback(callback_weighing) # chiamo callback
					weight["weight_executed"]["net_weight"] = ""
					weight["weight_executed"]["gross_weight"] = ""
					weight["weight_executed"]["tare"] = ""
					weight["weight_executed"]["unite_misure"] = ""
					weight["weight_executed"]["pid"] = ""
					weight["weight_executed"]["bil"] = ""
					weight["weight_executed"]["status"] = ""
					weight["data_assigned"] = None
				######### Se in esecuzione tara, preset tara o zero #################################################################
				elif modope in ["TARE", "PRESETTARE", "ZERO"]:
					# Controlla formato stringa, se corretto aggiorna ok_value
					if length_seriale == 2 and response == "OK":
						ok_value = response
					# Se formato stringa non valido setto ok_value a None
					else:
						lb_log.error(f"Received string format does not comply with the function {modope}: {response_decode}")			
					if modope == "TARE":
						pesa_real_time["status"] = "T"
					elif modope == "PRESETTARE":
						pesa_real_time["status"] = "PT"						
					elif modope == "ZERO":
						pesa_real_time["status"] = "Z"
					callCallback(callback_tare_ptare_zero) # chiamo callback
					ok_value = "" # Risetto ok_value a stringa vuota
				######### Se non è arrivata nessuna risposta ################################
			if not response:
				diagnostic["vl"] = ""
				diagnostic["rz"] = ""
				pesa_real_time["status"] = ""
				pesa_real_time["type"] = ""
				pesa_real_time["net_weight"] = ""
				pesa_real_time["gross_weight"] = ""
				pesa_real_time["tare"] = ""
				pesa_real_time["unite_measure"] = ""
				weight["weight_executed"]["net_weight"] = ""
				weight["weight_executed"]["gross_weight"] = ""
				weight["weight_executed"]["tare"] = ""
				weight["weight_executed"]["unite_misure"] = ""
				weight["weight_executed"]["pid"] = ""
				weight["weight_executed"]["bil"] = ""
				weight["weight_executed"]["status"] = ""
				weight["data_assigned"] = None
				ok_value = ""
				# Se il modope è settato a vuoto perchè è stato voluto che non ci fosse nessuna azione in esecuzione e lo stato non è a 301
				if modope == "":
					diagnostic["status"] = 307 # Setta lo stato a 400, ovvero che non c'è nessuna azione in esecuzione però la conn funziona
					lb_log.info(f"No data read from serial because set modope at void, so it's no possible check the conn, value of modope => '{modope}'")
				else:
					if isinstance(conn, serial.Serial):
						diagnostic["status"] = 305
					else:
						diagnostic["status"] = 301
					if modope == "REALTIME":
						pesa_real_time["status"] = diagnostic["status"]
						callCallback(callback_realtime) # chiamo callback
						pesa_real_time["status"] = ""
					elif modope == "DIAGNOSTICS":
						callCallback(callback_diagnostics) # chiamo callback
					elif modope == "WEIGHING":
						weight["status"] = diagnostic["status"]
						callCallback(callback_weighing)
						weight["status"] = ""
					elif modope in ["TARE", "PTARE", "ZERO"]:
						ok_value = diagnostic["status"]
						callCallback(callback_tare_ptare_zero)
						ok_value = ""
		# se lo stato della pesa è 301 e initializated è uguale a True prova a ristabilire una connessione con la pesa
		elif diagnostic["status"] == 301 or diagnostic["status"] == 305 or diagnostic["status"] == 307:
			if modope == "REALTIME":
				pesa_real_time["status"] = diagnostic["status"]
				callCallback(callback_realtime) # chiamo callback
				pesa_real_time["status"] = ""
			elif modope == "DIAGNOSTICS":
				callCallback(callback_diagnostics) # chiamo callback
			if diagnostic["status"] == 305:
				connection = CLASS_CONNECTION(**config["connection"])
				setup = SetupWeigher(**config["setup"])
				initialize(connection, setup)
			elif diagnostic["status"] == 307:
				if modope_to_execute in ["REALTIME", "DIAGNOSTICS"]:
					diagnostic["status"] = 200
				else:
					write("DINT2710") # scrive un comando sulla pesa
					response = read()
					if response: # se legge la risposta e la lunghezza della stringa è di 12 la splitta per ogni virgola
						response_decode = decode_read(response)
						flush()
					else:
						diagnostic["status"] = 305
		time.sleep(0.1)
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
	global conn
	if isinstance(conn, serial.Serial) and conn.is_open:
		conn.flush()
		conn.close()

# ==== INIT ====================================================
# funzione che dichiara tutte le globali
def init():
	lb_log.info("init")
	global conn
	global response
	global diagnostic
	global pesa_real_time
	global weight
	global ok_value
	global modope
	global modope_to_execute
	global valore_alterno
	global callback_realtime
	global callback_diagnostics
	global callback_weighing
	global callback_tare_ptare_zero
	global preset_tare
	global initializated
	global just_send_message_failed_reconnection
	global config
	global NAME_MODULE
	global TYPE_MODULE
	global TYPE_CONNECTION
	global CLASS_CONNECTION
	global CLASS_SETUP

	conn = None
	response = ""
	pesa_real_time = {
		"status": "",
		"type": "",
		"net_weight": "", 
		"gross_weight": "", 
		"tare": "",
		"unite_measure": ""
		}
	diagnostic = {
		"status": 301,
		"firmware": "",
		"model_name": "",
		"serial_number": "",
		"vl": "",
		"rz": ""
		}
	weight = {
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
		}
	ok_value = ""
	modope = ""
	modope_to_execute = ""
	valore_alterno = 1
	callback_realtime = ""
	callback_diagnostics = ""
	callback_weighing = ""
	callback_tare_ptare_zero = ""
	preset_tare = 0
	initializated = False
	just_send_message_failed_reconnection = False
	config = {
		"setup": {
			"max_weight": None,
			"min_weight": None,
			"division": None,
			"maintaine_session_realtime_after_command": True,
			"diagnostic_has_priority_than_realtime": True
		},
		"connection": {}
	}
	NAME_MODULE = "dgt1"
	TYPE_MODULE = "weigher"
	TYPE_CONNECTION = "serial"
	CLASS_CONNECTION = SerialPort
	CLASS_SETUP = SetupWeigher

def info():
	global NAME_MODULE
	global TYPE_MODULE
	global TYPE_CONNECTION
	global CLASS_CONNECTION
	global CLASS_SETUP
	return {
		"name_module": NAME_MODULE,
		"type_module": TYPE_MODULE,
  		"type_connection": TYPE_CONNECTION,
		"class_connection": CLASS_CONNECTION,
		"class_setup": CLASS_SETUP
	}