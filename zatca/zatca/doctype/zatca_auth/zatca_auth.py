# Copyright (c) 2023, Weslati Baha Eddine and contributors
# For license information, please see license.txt

import frappe,random
from frappe.model.document import Document


class ZatcaAuth(Document):
	
	def before_insert(self):
		r="abcdefghijklmnopqrstuvwxyz0123456789"
		key="".join(random.choices(r,k=20))
		secret="".join(random.choices(r,k=20))
		self.key=key
		self.secret=secret
		if not self.expiration:
			self.expiration=frappe.utils.add_to_date(frappe.utils.now(),years=1)
		if not self.address:
			addresses=frappe.db.get_all("Dynamic Link",filters={"link_doctype":"Customer","link_name":self.customer},fields=["parent"])
			if addresses:
				self.address=addresses[0]["parent"]
				
	def on_update(self):
		if not self.address:
			addresses=frappe.db.get_all("Dynamic Link",filters={"link_doctype":"Customer","link_name":self.customer},fields=["parent"])
			if addresses:
				self.address=addresses[0]["parent"]
