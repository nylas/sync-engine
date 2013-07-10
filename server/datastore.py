

class DataStore():

	def __init__(self):
		self.messages = {}  # message_id -> message
		self.threads = {}  # thread_id -> thread
		self.bodies = {}  # (message_id, body_index) -> body part


	def addMessage(self, message):
		print 'caching message', message.message_id
		self.messages[message.message_id] = message


	def addThread(self, thread):
		print 'caching thread', thread.thread_id
		self.threads[thread.thread_id] = thread


	def message(self, message_id):
		if not message_id in self.messages:
			return None
		return self.messages[message_id]

	def thread(self, thread_id):
		if not thread_id in self.threads:
			return None
		return self.threads[thread_id]

