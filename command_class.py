# Class for command structure

class Command(object):
	
	def __init__(self,pattern_str,transform_rules_files,template_folder):
		self.pattern_str = pattern_str
		self.transform_rules_files = transform_rules_files
		self.template_folder = template_folder

	# Read transformation rules from file
	# and apply them to putput
	#def transform(output):
