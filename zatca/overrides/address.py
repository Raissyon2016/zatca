from frappe.contacts.doctype.address.address import Address
import frappe
from frappe import _

class CustomAddress(Address):
	
	
	def validate(self):
		super(CustomAddress,self).validate()
		if self.country=="Saudi Arabia":
			msg=_("If tha country is Saudi Arabia, then the postal code must be 5 digits.")+"</br>"
			msg+=_("Warnings will be present in the invoice in case of clearing to Zatca.")
			if len(self.pincode)!=5:
			
				frappe.msgprint(msg,_('Postal Code Error'),"red")
				
				return
				try:
					a=int(self.pincode)
				except:
					frappe.msgprint(msg,_('Postal Code Error'),"red")
	def on_update(self):
		if self.address_type=="Office" and self.links:
			if self.links[0].link_doctype=="Company":
				address_str=""
				address_str+=self.address_line1+" "+self.city+" "
				if self.pincode:
					address_str+=self.pincode+" "
				address_str+=self.country
				frappe.db.set_value("Company",self.links[0].link_name,"address",address_str)
	def after_insert(self):
		if self.address_type=="Office" and  self.links:
			if self.links[0].link_doctype=="Company":
				address_str=""
				address_str+=self.address_line1+" "+self.city+" "
				if self.pincode:
					address_str+=self.pincode+" "
				address_str+=self.country
				frappe.db.set_value("Company",self.links[0].link_name,"address",address_str)
def setup():
	try:
		comp=frappe.db.get_all("Company")
		for c in comp:
			links=frappe.get_all("Dynamic Link",filters={"link_doctype":"Company","link_name":c["name"]},fields=["parent"])
			for l in links:
				address=frappe.get_doc("Address",l["parent"])
				if address.address_type=="Office":
					address_str=""
					address_str+=address.address_line1+" "+address.city+" "
					if address.pincode:
						address_str+=address.pincode+" "
					address_str+=address.country
					frappe.db.set_value("Company",c["name"],"address",address_str)
					continue
	except:
		pass
