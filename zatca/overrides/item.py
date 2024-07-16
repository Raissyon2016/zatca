from erpnext.stock.doctype.item.item import Item
import frappe
from frappe import _


class CustomItem(Item):
	def before_save(self):
		self.is_exempt=0
		self.is_zero_rated=0
		if self.custom_vat_category:
			type_=frappe.db.get_value("VAT category",self.custom_vat_category,"type")
			if type_=="Exempted":
				self.is_exempt=1
			elif type_=="Zero":
				self.is_zero_rated=1
