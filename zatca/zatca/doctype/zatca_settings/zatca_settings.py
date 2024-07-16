# Copyright (c) 2023, Weslati Baha Eddine and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document

class ZatcaSettings(Document):
	def before_save(self):
		if self.sn:
			sn=self.sn
			if sn[:2]!="1-" or  "|2-" not in sn or  "|3-" not in sn or "1-|2-" in sn:
				frappe.throw(_("Serial number must be in the format \"1-EGS provider name |2-version |3-serial number\""))
			
