import inspect

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

# {
#     "terminal": None,
#     "class": None
# }
terminalsClasses = []