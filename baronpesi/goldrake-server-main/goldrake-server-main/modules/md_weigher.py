# ==============================================================
# = Module......: md_dgt1					   =
# = Description.: Interfaccia di pesatura con più terminali =
# = Author......: Riccardo Meggiolaro				   =
# = Last rev....: 0.0002					   =
# ==============================================================

# ==== LIBRERIE DA IMPORTARE ===================================
import inspect
__frame = inspect.currentframe()
namefile = inspect.getfile(__frame).split("/")[-1].replace(".py", "")
import lib.lb_log as lb_log
import lib.lb_system as lb_system
import lib.lb_config as lb_config
from typing import Callable, Union, Optional, List
import time
import copy
from pydantic import BaseModel, validator
import re
from lib.lb_system import Connection, SerialPort, Tcp
from modules.md_weigher_utils.types import DataInExecution, Realtime, Diagnostic, WeightExecuted, Weight, Diagnostic, SetupWeigher
from modules.md_weigher_utils.dto import SetupWeigherDTO, ConfigurationDTO
from modules.md_weigher_utils.utils import callCallback, checkCallbackFormat
from modules.md_weigher_utils.config_weigher import ConfigWeigher
from modules.md_weigher_utils.terminals.dgt1 import Dgt1
# ==============================================================

# ==== INIT ====================================================
# funzione che dichiara tutte le globali
def init():
	lb_log.info("init")
	global config

	config = ConfigWeigher()
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
def initialize(configuration: ConfigurationDTO):
	lb_log.info("initialize")
	global config
	# inizializzazione della conn
	connected, message = False, None
	config.connection = configuration.connection
	connected, message = config.connection.try_connection()
	config.nodes = []
	config.time_between_actions = configuration.time_between_actions
	for node in configuration.nodes:
		node_dict = node.dict()
		node_dict["conn"] = config.connection
		n = Dgt1(**node_dict)
		n.initialize()
		config.nodes.append(n)
		# ottenere firmware e nome del modello
	return connected, message # ritorno True o False in base se status della pesa è 200

import json

def getConfig():
	global config
	return config.getConfig()

def deleteConfig():
	global config
	result, message = config.deleteConfig()
	return result, message

def getConnection():
	global config
	return config.getConnection()

def setConnection(connection: Union[SerialPort, Tcp]):
	global config
	deleteConnection()
	connected, connection, message = config.setConnection(connection=connection)
	return connected, connection, message

def deleteConnection():
	global config
	response = config.deleteConnection()
	return response

def getNodes():
    global config
    return config.getNodes()

def getNode(node: Union[str, None]):
	global config
	result = config.getNode(node=node)
	return result

def addNode(node: SetupWeigher):
	global config
	node_to_add = config.addNode(node=node)
	return node_to_add

def setNode(node: Union[str, None], setup: SetupWeigherDTO = {}):
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